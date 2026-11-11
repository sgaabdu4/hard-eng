"""Run a command in its own process group so a timeout stops every process it started."""

import fcntl
import json
import os
import re
import signal
import subprocess
import threading
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO, NamedTuple

BROKER = re.compile(
    r"^\S+ \S*/app-server-broker\.mjs serve --endpoint \S+ --cwd (.+) --pid-file \S+$"
)
COMPANION = "codex-companion.mjs"
RUNNING: set[int] = set()
STOPPED = threading.Event()
STOP_SIGNAL: list[int] = []
STARTING = threading.Lock()
INSTALLS: dict[str, bool] = {}
INSTALLED_FILE = "hard-eng-installed"
PASSED_FILE = "hard-eng-passed"
PASSED_SECONDS = 1800
INSTALL_FOLDERS = (".venv", "node_modules", ".dart_tool")


class Process(NamedTuple):
    pid: int
    parent: int
    command: str


def run_in_group(
    command: list[str],
    *,
    timeout: float | None,
    cwd: os.PathLike[str] | str | None = None,
    env: dict[str, str] | None = None,
    stdin: int | IO[str] | None = None,
    stdout: int | IO[str] | None = None,
    stderr: int | IO[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Like subprocess.run, but a timeout or interrupt kills the whole group first."""
    process: subprocess.Popen[str] | None = None
    try:
        with STARTING:
            if STOPPED.is_set():
                raise KeyboardInterrupt
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                text=True,
                start_new_session=True,
            )
            RUNNING.add(process.pid)
        out, err = process.communicate(timeout=timeout)
    except BaseException:
        if process is not None:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    finally:
        if process is not None:
            RUNNING.discard(process.pid)
    return subprocess.CompletedProcess(command, process.returncode, out, err)


def exit_when_stopped() -> None:
    """SIGTERM and SIGHUP end the process through the exit path that stops its groups."""

    def stop(number: int, _frame: object) -> None:
        STOP_SIGNAL[:] = [number]
        raise SystemExit(128 + number)

    for number in (signal.SIGTERM, signal.SIGHUP):
        if signal.getsignal(number) is not signal.SIG_IGN:
            signal.signal(number, stop)


def stop_groups() -> None:
    """An interrupt reaches only the main thread, not commands run by worker threads;
    they start no new command until `STOPPED` is cleared."""
    with STARTING:
        STOPPED.set()
        for group in RUNNING.copy():
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(group, signal.SIGKILL)


def stopped_note(code: int) -> str:
    """The text for a gate that ended because the check was stopped."""
    if code == 0 or not STOPPED.is_set():
        return ""
    cause = f" by {signal.Signals(STOP_SIGNAL[0]).name}" if STOP_SIGNAL else ""
    return f"\nThe check was stopped{cause}, so this gate was ended before it finished."


def process_table() -> list[Process]:
    output = subprocess.run(
        ["ps", "-Ao", "pid=,ppid=,command="],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows = []
    for line in output.splitlines():
        pid, parent, command = (line.split(None, 2) + [""])[:3]
        rows.append(Process(int(pid), int(parent), command))
    return rows


def start_process_scan() -> Callable[[], list[Process]]:
    found: list[list[Process] | Exception] = []

    def scan() -> None:
        try:
            found.append(process_table())
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            found.append(error)

    thread = threading.Thread(target=scan)
    thread.start()

    def result() -> list[Process]:
        thread.join()
        outcome = found[0] if found else OSError("process scan stopped")
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return result


def state_path(root: Path, name: str) -> Path:
    """A file in this checkout's own Git folder, so a linked worktree keeps its own."""
    return (
        root
        / subprocess.check_output(
            ["git", "rev-parse", "--git-path", name], cwd=root, text=True
        ).strip()
    )


@contextmanager
def check_lock_file(root: Path) -> Generator[tuple[IO[str], bool]]:
    """Open this checkout's check lock and try to take it; the flag says another check holds it."""
    with state_path(root, "hard-eng-check.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            held = True
        else:
            held = False
        yield lock, held


def lock_stamp(root: Path, key: str) -> str:
    """Size and change time of each lock file, and the install folders, in a package group's folder; its install mark holds only while they stay the same.

    A workspace root can hold the install and have no language, so the language does not pick the names."""
    from gate_config import LOCKFILES

    folder = root / key.partition(":")[2]
    found = []
    for name in sorted({name for names in LOCKFILES.values() for name in names}):
        with suppress(OSError):
            status = (folder / name).stat()
            found.append(f"{name} {status.st_size} {status.st_mtime_ns}")
    present = [name for name in INSTALL_FOLDERS if (folder / name).is_dir()]
    return "; ".join([*found, f"folders {' '.join(present)}"])


def read_installed(lock: IO[str], root: Path) -> frozenset[str]:
    """Package groups whose install passed in this checkout with the lock files of now; a bad state file counts as none."""
    INSTALLS.clear()
    try:
        saved = json.loads(Path(lock.name).with_name(INSTALLED_FILE).read_text())
    except (OSError, ValueError):
        return frozenset()
    if not isinstance(saved, dict):
        return frozenset()
    return frozenset(
        key for key, stamp in saved.items() if stamp == lock_stamp(root, key)
    )


def install_key(group: Mapping[str, object]) -> str:
    """One mark for each package group: two languages can share a folder, and each has its own install."""
    return f"{group.get('language', '')}:{group['path']}"


def note_install(key: str, role: object, failed: bool) -> None:
    if role == "lockfiles":
        INSTALLS[key] = INSTALLS.get(key, True) and not failed


def save_installed(lock: IO[str], before: frozenset[str], root: Path) -> None:
    passed = {key for key, ok in INSTALLS.items() if ok}
    after = (before | passed) - (INSTALLS.keys() - passed)
    if after != before:
        with suppress(OSError):
            Path(lock.name).with_name(INSTALLED_FILE).write_text(
                json.dumps({key: lock_stamp(root, key) for key in sorted(after)})
            )


def clean_tree(root: Path) -> tuple[str, bool] | None:
    """The commit that HEAD names and whether Git sees no change, submodules included."""
    status = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "status",
            "--porcelain=v2",
            "--branch",
            "--no-ahead-behind",
            "--ignore-submodules=none",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = status.stdout.splitlines()
    heads = [line.split()[2] for line in lines if line.startswith("# branch.oid ")]
    if status.returncode or len(heads) != 1 or not heads[0].isalnum():
        return None
    return heads[0], all(line.startswith("# ") for line in lines)


def clean_start(
    lock: IO[str], root: Path, base: str | None, plan_stage: str | None, partial: bool
) -> tuple[str, str, float] | None:
    """Remove the old pass record; give the start of a full check that may write a new one."""
    import time

    if base is None or partial or plan_stage not in (None, "Complete"):
        return None
    with suppress(OSError):
        Path(lock.name).with_name(PASSED_FILE).unlink()
    commit = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", f"{base}^{{commit}}"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    state = clean_tree(root)
    if commit.returncode or state is None or not state[1]:
        return None
    return state[0], commit.stdout.strip(), time.time()


def record_pass(
    lock: IO[str], root: Path, start: tuple[str, str, float] | None, failed: bool
) -> None:
    """A full check that passed on a clean tree and left it clean is a pass of its commit and base."""
    if start is None or failed or clean_tree(root) != (start[0], True):
        return
    record = Path(lock.name).with_name(PASSED_FILE)
    with suppress(OSError):
        temporary = record.with_name(f"{PASSED_FILE}.tmp")
        temporary.write_text(
            json.dumps({"head": start[0], "base": start[1], "time": start[2]})
        )
        temporary.replace(record)


def passed_minutes(root: Path, revision: str, base: str) -> int | None:
    """Minutes since a full check passed on this commit and base; any doubt is None."""
    import time

    try:
        saved = json.loads(state_path(root, PASSED_FILE).read_text())
        age = time.time() - saved["time"]
        if (
            saved["head"] == revision
            and saved["base"] == base
            and not isinstance(saved["time"], bool)
            and 0 <= age <= PASSED_SECONDS
        ):
            return int(age // 60)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        pass
    return None


def stop_idle_codex_brokers(table: list[Process] | None = None) -> tuple[int, int]:
    """SessionEnd alone misses killed sessions; a job's folder is not readable, so any job keeps live folders."""
    rows = process_table() if table is None else table
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row.parent, []).append(row.pid)
    jobs = any(COMPANION in row.command for row in rows)
    brokers = stopped = 0
    for row in rows:
        broker = BROKER.match(row.command)
        if broker is None:
            continue
        if jobs and Path(broker.group(1)).is_dir():
            continue
        tree: list[int] = []
        pending = [row.pid]
        while pending:
            pid = pending.pop()
            tree.append(pid)
            pending.extend(children.get(pid, []))
        for pid in tree:
            with suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGTERM)
        brokers += 1
        stopped += len(tree)
    return brokers, stopped

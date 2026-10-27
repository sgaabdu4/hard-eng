"""Run a command in its own process group so a timeout stops every process it started."""

import os
import re
import signal
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from typing import IO, NamedTuple

BROKER = re.compile(r"app-server-broker\.mjs serve .* --cwd (.+?) --pid-file ")
COMPANION = "codex-companion.mjs"
WORKER_FOLDER = re.compile(r" task-worker --cwd (.+?) --job-id ")


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
    try:
        out, err = process.communicate(timeout=timeout)
    except BaseException:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, out, err)


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


def process_folder(pid: int) -> Path | None:
    if sys.platform == "linux":
        with suppress(OSError):
            return Path(os.readlink(f"/proc/{pid}/cwd"))
        return None
    listing = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    return next(
        (Path(line[1:]) for line in listing.splitlines() if line.startswith("n")),
        None,
    )


def stop_idle_codex_brokers(table: list[Process] | None = None) -> tuple[int, int]:
    """The plugin stops a broker only on SessionEnd, which a killed session never sends."""
    rows = process_table() if table is None else table
    children: dict[int, list[int]] = {}
    for row in rows:
        children.setdefault(row.parent, []).append(row.pid)
    busy: set[Path] = set()
    for row in rows:
        if COMPANION not in row.command:
            continue
        worker = WORKER_FOLDER.search(row.command)
        folder = Path(worker.group(1)) if worker else process_folder(row.pid)
        if folder is not None:
            busy.add(folder.resolve())
    brokers = stopped = 0
    for row in rows:
        broker = BROKER.search(row.command)
        if broker is None:
            continue
        folder = Path(broker.group(1))
        if folder.is_dir() and folder.resolve() in busy:
            continue
        tree, pending = [], [row.pid]
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

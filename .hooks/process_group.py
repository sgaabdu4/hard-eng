"""Run a command in its own process group so a timeout stops every process it started."""

import os
import re
import signal
import subprocess
import threading
from collections.abc import Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import IO, NamedTuple

BROKER = re.compile(
    r"^\S+ \S*/app-server-broker\.mjs serve --endpoint \S+ --cwd (.+) --pid-file \S+$"
)
COMPANION = "codex-companion.mjs"
RUNNING: set[int] = set()
STOPPED = threading.Event()
STARTING = threading.Lock()
INTERRUPTS = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)


class Process(NamedTuple):
    pid: int
    parent: int
    command: str


@contextmanager
def held_interrupts(caught: list[int]) -> Generator[None]:
    """Record the host's interrupts while a command starts, so none lands before its group is tracked."""
    held = (
        {
            number: handler
            for number in INTERRUPTS
            if callable(handler := signal.getsignal(number))
        }
        if threading.current_thread() is threading.main_thread()
        else {}
    )
    for number in held:
        signal.signal(number, lambda signum, _frame: caught.append(signum))
    try:
        yield
    finally:
        for number, handler in held.items():
            signal.signal(number, handler)


def deliver(caught: list[int]) -> None:
    while caught:
        signal.raise_signal(caught.pop(0))


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
    caught: list[int] = []
    try:
        with STARTING, held_interrupts(caught):
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
    except BaseException:
        deliver(caught)
        raise
    try:
        deliver(caught)
        out, err = process.communicate(timeout=timeout)
    except BaseException:
        with suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    finally:
        RUNNING.discard(process.pid)
    return subprocess.CompletedProcess(command, process.returncode, out, err)


def stop_groups() -> None:
    """An interrupt reaches only the main thread, not commands run by worker threads;
    they start no new command until `STOPPED` is cleared."""
    with STARTING:
        STOPPED.set()
        for group in RUNNING.copy():
            with suppress(ProcessLookupError, PermissionError):
                os.killpg(group, signal.SIGKILL)


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

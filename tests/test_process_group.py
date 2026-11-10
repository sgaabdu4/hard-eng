import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import override
from unittest.mock import Mock

import agent_hooks
import process_group
import pytest
import update_runner
from conftest import below, gone, running, spawner
from process_group import Process, process_table, stop_idle_codex_brokers


def start(command: list[str], pid_file: Path, cwd: Path) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(command, cwd=cwd)
    deadline = time.monotonic() + 30
    while not pid_file.exists() or not pid_file.read_text():
        assert time.monotonic() < deadline, "process did not start"
        time.sleep(0.05)
    return process


BROKER_SCRIPT = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
open(sys.argv[sys.argv.index("--pid-file") + 1] + ".child", "w").write(str(child.pid))
time.sleep(60)
"""


def broker(
    tmp_path: Path, folder: Path, launcher: tuple[str, ...] = ()
) -> tuple[subprocess.Popen[bytes], Path]:
    script = tmp_path / "scripts/app-server-broker.mjs"
    script.parent.mkdir(exist_ok=True)
    script.write_text(BROKER_SCRIPT)
    pid_file = tmp_path / "broker.pid"
    command = [sys.executable, str(script), "serve", "--endpoint"]
    command += [
        "unix:/tmp/broker.sock",
        "--cwd",
        str(folder),
        "--pid-file",
        str(pid_file),
    ]
    return start([*launcher, *command], Path(f"{pid_file}.child"), tmp_path), Path(
        f"{pid_file}.child"
    )


def own_table(*roots: subprocess.Popen[bytes]) -> list[Process]:
    return below(process_table(), {root.pid for root in roots})


def ended(process: subprocess.Popen[bytes], child: Path) -> bool:
    process.wait(timeout=30)
    deadline = time.monotonic() + 30
    while running(child):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def test_stops_broker_without_a_job(tmp_path: Path) -> None:
    folder = tmp_path / "worktree"
    folder.mkdir()
    process, child = broker(tmp_path, folder)
    assert stop_idle_codex_brokers(own_table(process)) == (1, 2)
    assert ended(process, child)


def test_a_session_start_in_a_test_stops_no_broker_that_the_test_did_not_start(
    repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handover = "import subprocess, sys; subprocess.Popen(sys.argv[1:])"
    launcher, child = broker(
        tmp_path, tmp_path / "gone", (sys.executable, "-c", handover)
    )
    launcher.wait(timeout=30)
    scripts = str(tmp_path / "scripts")
    outside = [row.pid for row in process_table() if scripts in row.command]
    stop = os.kill
    sent: list[int] = []

    def record(pid: int, _signal: int) -> None:
        sent.append(pid)

    monkeypatch.setattr(update_runner, "start_update", Mock(return_value="status"))
    monkeypatch.setattr(os, "kill", record)
    try:
        agent_hooks.session_context(repository, {"session_id": "outside"})
    finally:
        for pid in (*outside, int(child.read_text())):
            stop(pid, signal.SIGKILL)
    assert outside
    assert not set(sent) & set(outside)


def start_job(tmp_path: Path) -> tuple[subprocess.Popen[bytes], Path]:
    job_pid = tmp_path / "job-child.pid"
    job = spawner(job_pid) + ["codex-companion.mjs", "task", "--cwd", "/repo", "fix it"]
    return start(job, job_pid, tmp_path), job_pid


def stop_job(job: subprocess.Popen[bytes], job_pid: Path) -> None:
    job.kill()
    job.wait(timeout=30)
    subprocess.run(["kill", job_pid.read_text()], check=False)


def test_keeps_broker_while_a_job_runs(tmp_path: Path) -> None:
    folder = tmp_path / "worktree"
    folder.mkdir()
    process, child = broker(tmp_path, folder)
    job, job_pid = start_job(tmp_path)
    try:
        assert stop_idle_codex_brokers(own_table(process, job)) == (0, 0)
        assert process.poll() is None
        assert running(child)
    finally:
        stop_job(job, job_pid)
        stop_idle_codex_brokers(own_table(process))
        assert ended(process, child)


def test_stops_broker_whose_folder_is_gone_while_a_job_runs(tmp_path: Path) -> None:
    process, child = broker(tmp_path, tmp_path / "deleted-worktree")
    job, job_pid = start_job(tmp_path)
    try:
        assert stop_idle_codex_brokers(own_table(process, job)) == (1, 2)
        assert ended(process, child)
    finally:
        stop_job(job, job_pid)


def test_job_that_quotes_a_broker_command_is_not_a_broker(tmp_path: Path) -> None:
    job_pid = tmp_path / "job-child.pid"
    quoted = "node /x/app-server-broker.mjs serve --endpoint e --cwd /gone --pid-file p"
    job = spawner(job_pid) + ["codex-companion.mjs", "task", quoted]
    companion = start(job, job_pid, tmp_path)
    try:
        assert stop_idle_codex_brokers(own_table(companion)) == (0, 0)
        assert companion.poll() is None
    finally:
        stop_job(companion, job_pid)


def test_stop_groups_kills_every_group_while_others_finish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    killed: list[int] = []

    def kill(group: int, _signal: int) -> None:
        killed.append(group)
        process_group.RUNNING.discard(102 if group == 101 else 101)

    monkeypatch.setattr(process_group, "RUNNING", {101, 102})
    monkeypatch.setattr(process_group.os, "killpg", kill)
    try:
        process_group.stop_groups()
    finally:
        process_group.STOPPED.clear()
    assert sorted(killed) == [101, 102]


def test_an_interrupt_right_after_start_still_stops_the_group(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pid_file = tmp_path / "child.pid"

    class Interrupted(set[int]):
        @override
        def add(self, pid: int) -> None:
            deadline = time.monotonic() + 30
            while not pid_file.exists() or not pid_file.read_text():
                assert time.monotonic() < deadline, "process did not start"
                time.sleep(0.05)
            raise KeyboardInterrupt

    monkeypatch.setattr(process_group, "RUNNING", Interrupted())
    with pytest.raises(KeyboardInterrupt):
        process_group.run_in_group(spawner(pid_file), timeout=60)
    assert gone(pid_file)

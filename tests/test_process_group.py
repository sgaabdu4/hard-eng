import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import running, spawner
from process_group import Process, process_table, stop_idle_codex_brokers

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX processes")


def start(command: list[str], pid_file: Path, cwd: Path) -> subprocess.Popen[bytes]:
    process = subprocess.Popen(command, cwd=cwd)
    deadline = time.monotonic() + 30
    while not pid_file.exists() or not pid_file.read_text():
        assert time.monotonic() < deadline, "process did not start"
        time.sleep(0.05)
    return process


def broker(tmp_path: Path, folder: Path) -> tuple[subprocess.Popen[bytes], Path]:
    child = tmp_path / "broker-child.pid"
    command = spawner(child) + [
        "app-server-broker.mjs",
        "serve",
        "--endpoint",
        "unix:/tmp/broker.sock",
        "--cwd",
        str(folder),
        "--pid-file",
        str(tmp_path / "broker.pid"),
    ]
    return start(command, child, tmp_path), child


def own_table(*roots: subprocess.Popen[bytes]) -> list[Process]:
    rows = process_table()
    mine = {root.pid for root in roots}
    while True:
        more = {row.pid for row in rows if row.parent in mine} - mine
        if not more:
            return [row for row in rows if row.pid in mine]
        mine |= more


def ended(process: subprocess.Popen[bytes], child: Path) -> bool:
    process.wait(timeout=30)
    deadline = time.monotonic() + 30
    while running(child):
        if time.monotonic() > deadline:
            return False
        time.sleep(0.05)
    return True


def test_stops_broker_whose_folder_is_gone(tmp_path: Path) -> None:
    process, child = broker(tmp_path, tmp_path / "deleted-worktree")
    assert stop_idle_codex_brokers(own_table(process)) == (1, 2)
    assert ended(process, child)


def test_stops_broker_without_a_job(tmp_path: Path) -> None:
    folder = tmp_path / "worktree"
    folder.mkdir()
    process, child = broker(tmp_path, folder)
    assert stop_idle_codex_brokers(own_table(process)) == (1, 2)
    assert ended(process, child)


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

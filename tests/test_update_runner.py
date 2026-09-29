"""Session start must never wait on, leak or duplicate a scaffold update."""

import fcntl
import json
import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock

import agent_hooks
import pytest
import update
import update_runner
from conftest import SOURCE, commit, git
from gate_config import JsonObject


@pytest.fixture
def installed(repository: Path) -> Path:
    marker = repository / update.SOURCE_FILE
    marker.parent.mkdir()
    marker.write_text(json.dumps({"revision": "a" * 40}))
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    commit(repository, "installed")
    return repository


@pytest.fixture
def spawned(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    record = tmp_path / "worker.txt"
    worker = tmp_path / "worker"
    worker.write_text(
        "#!/bin/sh\n"
        "echo worker output\n"
        f'echo "$(ps -o pgid= -p $$ | tr -d " ") $$ $*" > {record}\n'
    )
    worker.chmod(0o755)
    monkeypatch.setattr(update_runner.sys, "executable", str(worker))
    return record


def worker_record(record: Path) -> list[str]:
    deadline = time.monotonic() + 10
    while not record.is_file() or not record.read_text().endswith("\n"):
        assert time.monotonic() < deadline, "no detached worker started"
        time.sleep(0.05)
    return record.read_text().split()


@pytest.fixture
def held_lock(installed: Path) -> Generator[None]:
    with update_runner.lock_file(installed).open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def test_start_detaches_worker_without_inherited_pipes(
    installed: Path, spawned: Path
) -> None:
    message = update_runner.start_update(installed)
    group, process, *arguments = worker_record(spawned)
    assert group == process
    assert arguments == [str(SOURCE / ".hooks/hard-eng.py"), "update"]
    assert (installed / update_runner.LOG_FILE).read_text() == "worker output\n"
    assert message.startswith("Hard Eng update started in the background")
    assert message.endswith("Last update result: none recorded yet")
    (installed / update_runner.RESULT_FILE).write_text("earlier: Updated Hard Eng\n")
    assert update_runner.start_update(installed).endswith(
        "Last update result: earlier: Updated Hard Eng"
    )


@pytest.mark.usefixtures("held_lock")
def test_running_update_is_reported_not_duplicated(
    installed: Path, spawned: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    message = update_runner.start_update(installed)
    assert message.startswith("A Hard Eng update is already running")
    assert not (installed / update_runner.LOG_FILE).exists()
    assert not spawned.exists()
    installer = Mock()
    monkeypatch.setattr(update, "update", installer)
    assert update_runner.run_update(installed) == 0
    installer.assert_not_called()
    assert not (installed / update_runner.RESULT_FILE).exists()
    with pytest.raises(update_runner.UpdateRunning):
        update_runner.locked_update(installed, repair=True)


@pytest.mark.usefixtures("held_lock")
def test_stop_waits_for_running_update_instead_of_rerunning_setup(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update, "latest_verified", Mock(return_value="b" * 40))
    with pytest.raises(ValueError, match="still running in the background"):
        update.require_current(installed)


def test_unavailable_update_is_reported_without_a_worker(
    repository: Path, spawned: Path
) -> None:
    message = update_runner.start_update(repository)
    assert not (repository / update_runner.LOG_FILE).exists()
    assert not spawned.exists()
    assert message == (
        "Hard Eng update result: Automatic update unavailable: "
        "this checkout has no installed source revision."
    )


def test_update_removes_candidates_left_by_a_killed_update(
    installed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leaked = tmp_path / "hard-eng-update-killed"
    kept = tmp_path / "hard-eng-scaffold-check-running/candidate"
    for candidate in (leaked / "candidate", kept):
        git(installed, "worktree", "add", "-q", "--detach", str(candidate))
    monkeypatch.setattr(update, "update", Mock(return_value="No newer revision."))
    assert update_runner.locked_update(installed) == "No newer revision."
    listing = git(installed, "worktree", "list", "--porcelain")
    assert "hard-eng-update-killed" not in listing and not leaked.exists()
    assert str(kept) in listing


def test_interrupted_update_stops_its_processes_and_records_failure(
    installed: Path, tmp_path: Path
) -> None:
    child = tmp_path / "child.pid"
    worker = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                "import subprocess, sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(SOURCE / '.hooks')!r}); "
                "import update, update_runner; "
                "update.update = lambda root, repair=False: subprocess.run("
                f"['sh', '-c', 'sleep 60 & echo $! > {child}; wait'], check=True); "
                "raise SystemExit(update_runner.run_update(Path.cwd()))"
            ),
        ],
        cwd=installed,
        start_new_session=True,
    )
    deadline = time.monotonic() + 30
    while not child.is_file() or not child.read_text().strip():
        assert time.monotonic() < deadline and worker.poll() is None
        time.sleep(0.05)
    worker.terminate()
    assert worker.wait(timeout=30) == 0
    sleeper = int(child.read_text())
    deadline = time.monotonic() + 10
    while subprocess.run(["kill", "-0", str(sleeper)], check=False).returncode == 0:
        assert time.monotonic() < deadline, "update left a child process running"
        time.sleep(0.05)
    result = (installed / update_runner.RESULT_FILE).read_text()
    assert "Hard Eng update failed: interrupted by signal 15" in result
    assert not update_runner.update_running(installed)


def test_update_commit_is_not_counted_as_session_work(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_runner, "start_update", Mock(return_value="started"))
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    payload: JsonObject = {"session_id": "known"}
    other = installed / ".hard-eng/sessions/other.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"base": "c" * 40}))
    agent_hooks.session_context(installed, payload)
    (installed / ".hooks/update.py").write_text("updated = True\n")
    commit(installed, "Update Hard Eng")
    update_runner.rebase_sessions(installed)
    assert "no code checks were run" in str(agent_hooks.completion(installed, payload))
    assert json.loads(other.read_text())["base"] == "c" * 40
    os.remove(installed / ".hooks/update.py")
    assert agent_hooks.completion(installed, payload)["decision"] == "block"

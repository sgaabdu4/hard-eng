"""`release_canary.py`: which releases need a try on installed projects, and what it publishes."""

import fcntl
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import release_canary


def test_only_changes_to_installed_files_need_a_canary_run() -> None:
    assert not release_canary.needs_canary(
        ["README.md", "release_canary.py", "features/x/PLAN.md", "docs/a.md"]
    )
    for installed in (
        ".hooks/update.py",
        "setup.py",
        "AGENTS.md",
        ".agents/skill-sources/building-flutter-apps",
        ".github/workflows/hard-eng.yml",
    ):
        assert release_canary.needs_canary(["README.md", installed])


def test_published_status_names_no_project() -> None:
    """The source repository is public; most installed projects are private."""
    results = {
        "owner/private-app": (True, "update and check passed"),
        "owner/other-app": (False, "check failed; log /cache/owner__other-app.log"),
    }
    text = release_canary.status_text(results)
    assert text == "1 of 2 installed projects passed"
    assert "owner" not in text


def test_a_run_that_finds_no_project_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty search must not certify a release."""
    posted: list[str] = []
    replies = {"rev-parse": "a" * 40, "diff": ".hooks/update.py"}

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return replies.get(command[1], "")

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append(state)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "installed_projects", list)
    monkeypatch.setattr(release_canary, "post_status", post_status)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--post-status"])
    assert release_canary.main() == 1
    assert posted == ["pending", "failure"]


def test_a_step_past_its_limit_stops_every_process_it_started(tmp_path: Path) -> None:
    """Hung tests and installers must not outlive the step."""
    pid_file = tmp_path / "child.pid"
    spawn = (
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
        "open(sys.argv[1], 'w').write(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    with (tmp_path / "step.log").open("w") as log:
        command = [sys.executable, "-c", spawn, str(pid_file)]
        assert not release_canary.step(command, tmp_path, log, 2)
    child = int(pid_file.read_text())
    time.sleep(0.5)
    with pytest.raises(ProcessLookupError):
        os.kill(child, 0)


def test_an_install_without_the_update_runner_uses_its_older_entry_point(
    tmp_path: Path,
) -> None:
    hooks = tmp_path / ".hooks"
    hooks.mkdir()
    (hooks / "update.py").write_text(
        "def latest_verified(previous):\n    return None\n\n\n"
        "def update(root):\n    return f'updated to {latest_verified(None)}'\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", release_canary.UPDATE, "a" * 40],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert done.stdout == f"updated to {'a' * 40}\n"


def test_a_second_run_waits_and_keeps_the_active_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parallel agents must not delete each other's checkouts and logs."""
    active = tmp_path / "cache/run-active/project.log"
    active.parent.mkdir(parents=True)
    active.write_text("running\n")
    lock = tmp_path / "canary.lock"
    monkeypatch.setattr(release_canary, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(release_canary, "LOCK", lock)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD"])
    with lock.open("a") as holder:
        fcntl.flock(holder, fcntl.LOCK_EX)
        assert release_canary.main() == 1
    assert active.read_text() == "running\n"

"""`release_canary.py`: which releases need a try on installed projects, and what it publishes."""

import fcntl
import json
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
    assert text == "1 of 2 canary runs passed"
    assert "owner" not in text


def test_a_run_that_finds_no_project_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty search must not certify a release."""
    monkeypatch.setattr(release_canary, "LOCK", tmp_path / "canary.lock")
    posted: list[str] = []
    replies = {"rev-parse": "a" * 40, "diff": ".hooks/update.py"}

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return replies.get(command[1], "")

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append(state)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "repositories", list)
    monkeypatch.setattr(release_canary, "public_text", str)
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
    child = pid_file.read_text()
    time.sleep(0.5)
    # A killed orphan stays a zombie where the container's first process never reaps it.
    state = subprocess.run(
        ["ps", "-o", "stat=", "-p", child], check=False, capture_output=True, text=True
    )
    assert state.stdout.strip() in {"", "Z"}


def test_projects_with_dotted_names_keep_their_own_log_and_clone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cloned: list[str] = []

    def step(command: list[str], cwd: Path, log: object, limit: int) -> bool:
        cloned.append(command[-1])
        return False

    monkeypatch.setattr(release_canary, "step", step)
    messages = [
        release_canary.try_target(
            ("installed", name), "a" * 40, tmp_path, tmp_path, ()
        )[f"installed {name}"][1]
        for name in ("owner/app.api", "owner/app.web", "owner/app.log")
    ]
    logs = [message.rsplit("log ", 1)[1] for message in messages]
    assert len(set(logs)) == 3
    assert not set(logs) & set(cloned)


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


def test_a_release_that_names_a_private_project_fails_without_publishing_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The source repository is public; private project names must not reach it."""
    monkeypatch.setattr(release_canary, "LOCK", tmp_path / "canary.lock")
    posted: list[str] = []
    found = [("owner/secret-app", True, False), ("owner/open-tool", False, False)]

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        return "a" * 40

    def post_status(revision: str, state: str, description: str) -> None:
        posted.append(description)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "repositories", lambda: found)
    monkeypatch.setattr(release_canary, "public_text", "Seen in secret-app {}.".format)
    monkeypatch.setattr(release_canary, "post_status", post_status)
    monkeypatch.setattr(sys, "argv", ["release_canary.py", "HEAD", "--post-status"])
    assert release_canary.main() == 1
    assert posted == ["The release names a private project"]


def test_only_whole_private_names_count_as_leaks() -> None:
    private = ["owner/secret-app"]
    for text in ("see owner/secret-app", "in secret-app.", "SECRET-APP fails"):
        assert release_canary.leaked_names(text, private), text
    for text in ("secret-apps", "my-secret-app", "secret-app.py", "x/secret-app/y"):
        assert not release_canary.leaked_names(text, private), text


def test_a_cut_github_reply_is_retried_before_reading_release_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """GitHub sometimes cuts a reply short; one cut reply must not stop a full run."""
    failed: set[str] = set()

    def output(command: list[str], cwd: Path = release_canary.SOURCE) -> str:
        if command[0] == "gh":
            if command[2] not in failed:
                failed.add(command[2])
                raise subprocess.CalledProcessError(1, command)
            return f"PR for {command[2]}"
        return "c1 c2" if command[1] == "rev-list" else ""

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(time, "sleep", float)
    text = release_canary.public_text("HEAD")
    assert "commits/c1/pulls" in text
    assert "commits/c2/pulls" in text


def test_a_private_repository_named_after_a_public_owner_is_no_leak() -> None:
    private = ["school/sgaabdu4"]
    assert not release_canary.leaked_names('"github_login":"sgaabdu4"', private)
    assert release_canary.leaked_names("see school/sgaabdu4", private)


def agent_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, session: dict[str, object]
) -> Path:
    work = tmp_path / "target"
    work.mkdir()
    for command in (
        ["git", "init", "-q"],
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "base",
        ],
    ):
        subprocess.run(command, cwd=work, check=True)
    agent = (
        "import json, pathlib, sys\n"
        "pathlib.Path('sum.py').write_text('def add(a, b):\\n    return a + b\\n')\n"
        "state = pathlib.Path('.hard-eng/sessions/s.json')\n"
        "state.parent.mkdir(parents=True)\n"
        "state.write_text(sys.argv[1])\n"
    )

    def agent_command(name: str, copy: Path) -> list[str]:
        return [sys.executable, "-c", agent, json.dumps(session)]

    monkeypatch.setattr(release_canary, "agent_command", agent_command)
    return work


@pytest.mark.parametrize(
    ("session", "expected"),
    [
        ({"base": "x", "verified": {}}, (True, "codex passed")),
        ({"base": "x"}, (False, "codex ended without a passing Hard Eng check")),
    ],
)
def test_an_agent_run_passes_only_when_hard_eng_recorded_a_passing_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    session: dict[str, object],
    expected: tuple[bool, str],
) -> None:
    """Agent exit status alone cannot prove the hooks loaded and the gate passed."""
    work = agent_target(tmp_path, monkeypatch, session)
    with (tmp_path / "agent.log").open("w") as log:
        assert release_canary.try_agent("codex", work, log) == expected
    assert sorted(path.name for path in tmp_path.iterdir()) == ["agent.log", "target"]


def test_git_locks_in_the_target_never_reach_the_agent_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Background git maintenance holds and drops lock files while the target is copied."""
    work = agent_target(tmp_path, monkeypatch, {"base": "x", "verified": {}})
    (work / ".git/index.lock").touch()
    with (tmp_path / "agent.log").open("w") as log:
        assert release_canary.try_agent("codex", work, log) == (True, "codex passed")

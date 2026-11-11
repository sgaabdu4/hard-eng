"""Session start must never wait on, leak or duplicate a scaffold update."""

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import agent_hooks
import pytest
import update
import update_pr
import update_runner
from conftest import SOURCE, add_origin, commit, git, init
from gate_config import JsonObject
from test_setup import project_with_commit_hook
from test_updates import select_release


@pytest.fixture
def installed(repository: Path) -> Path:
    marker = repository / update.SOURCE_FILE
    marker.parent.mkdir()
    marker.write_text(json.dumps({"revision": "a" * 40}))
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    commit(repository, "installed")
    add_origin(repository)
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


@contextmanager
def held_lock(root: Path) -> Generator[None]:
    with update_runner.lock_file(root).open("a") as handle:
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
    assert message.endswith("Last: none recorded yet")
    (installed / update_runner.RESULT_FILE).write_text("earlier: Updated Hard Eng\n")
    assert update_runner.start_update(installed).endswith(
        "Last: earlier: Updated Hard Eng"
    )


def test_running_update_is_reported_not_duplicated(
    installed: Path, spawned: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    installer = Mock()
    monkeypatch.setattr(update, "update", installer)
    with held_lock(installed):
        message = update_runner.start_update(installed)
        assert update_runner.run_update(installed) == 0
        with pytest.raises(update_runner.UpdateRunning):
            update_runner.locked_update(installed, repair=True)
    assert message.startswith("Hard Eng update already running")
    assert not (installed / update_runner.LOG_FILE).exists()
    assert not spawned.exists()
    installer.assert_not_called()
    assert not (installed / update_runner.RESULT_FILE).exists()


def test_stop_waits_for_running_update_instead_of_rerunning_setup(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update, "latest_verified", Mock(return_value="b" * 40))
    monkeypatch.setattr(update_pr, "gh", Mock(return_value="[]"))
    with (
        held_lock(installed),
        pytest.raises(ValueError, match="still running") as running,
    ):
        update.require_current(installed)
    assert not isinstance(running.value, update_runner.UpdateNeeded)
    with pytest.raises(update_runner.UpdateNeeded, match="update-pr"):
        update.require_current(installed)


def test_update_prints_its_result_and_fails_when_the_update_failed(
    installed: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    worker = tmp_path / "worker"
    monkeypatch.setattr(update_runner.sys, "executable", str(worker))
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    for outcome, code in (("Hard Eng update failed: boom", 1), ("Updated", 0)):
        worker.write_text(
            "#!/bin/sh\nmkdir -p .hard-eng\n"
            f"echo 'now: {outcome}' > {update_runner.RESULT_FILE}\n"
        )
        worker.chmod(0o755)
        assert update_runner.run_update(installed) == code
        assert capsys.readouterr().out == f"now: {outcome}\n"
    with held_lock(installed):
        assert update_runner.run_update(installed) == 0
    assert "already running" in capsys.readouterr().out


def test_unavailable_update_is_reported_without_a_worker(
    repository: Path, spawned: Path
) -> None:
    message = update_runner.start_update(repository)
    assert not (repository / update_runner.LOG_FILE).exists()
    assert not spawned.exists()
    assert message == (
        "Hard Eng update result: Auto-update unavailable: no installed source revision."
    )


def test_update_removes_only_candidates_whose_update_ended(
    installed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    finished = subprocess.Popen(["true"])
    finished.wait()
    owners = {
        "hard-eng-update-killed": f"hard-eng-update {finished.pid}",
        "hard-eng-update-vanished": f"hard-eng-update {finished.pid}",
        "hard-eng-update-running": f"hard-eng-update {os.getpid()}",
        "hard-eng-update-legacy": None,
        "hard-eng-update-abandoned": None,
        "hard-eng-scaffold-check-running": f"hard-eng-update {finished.pid}",
    }
    for name, owner in owners.items():
        lock = ["--lock", "--reason", owner] if owner else []
        git(
            installed,
            "worktree",
            "add",
            "-q",
            "--detach",
            *lock,
            str(tmp_path / name / "candidate"),
        )
    shutil.rmtree(tmp_path / "hard-eng-update-vanished")
    hours_ago = time.time() - 7 * 3600
    os.utime(tmp_path / "hard-eng-update-abandoned", (hours_ago, hours_ago))
    monkeypatch.setattr(update, "update", Mock(return_value="No newer revision."))
    assert update_runner.locked_update(installed) == "No newer revision."
    listing = git(installed, "worktree", "list", "--porcelain")
    for name in (
        "hard-eng-update-killed",
        "hard-eng-update-vanished",
        "hard-eng-update-abandoned",
    ):
        assert name not in listing and not (tmp_path / name).exists()
    for name in ("running", "legacy"):
        assert f"hard-eng-update-{name}" in listing
    assert "hard-eng-scaffold-check-running" in listing


def test_update_sweeps_day_old_hard_eng_temporary_directories(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    temporary = Path(tempfile.gettempdir())
    day_ago = time.time() - 25 * 3600
    for name in ("hard-eng-push-left0001", "hard-eng-push-fresh001"):
        git(
            installed,
            "worktree",
            "add",
            "-q",
            "--detach",
            str(temporary / name / "project"),
        )
    left = ("hard-eng-gate-left0002", "hard-eng-mutation-left0003")
    for name in (*left, "hard-eng-gate-fresh002", "hard-eng-notes"):
        (temporary / name).mkdir()
    for name in ("hard-eng-push-left0001", *left, "hard-eng-notes"):
        os.utime(temporary / name, (day_ago, day_ago))
    monkeypatch.setattr(update, "update", Mock(return_value="No newer revision."))
    update_runner.locked_update(installed)
    listing = git(installed, "worktree", "list", "--porcelain")
    assert "hard-eng-push-left0001" not in listing
    assert "hard-eng-push-fresh001" in listing
    assert {path.name for path in temporary.iterdir()} >= {
        "hard-eng-push-fresh001",
        "hard-eng-gate-fresh002",
        "hard-eng-notes",
    }
    assert not any((temporary / name).exists() for name in left)
    assert not (temporary / "hard-eng-push-left0001").exists()


def test_update_cleanup_stops_file_watchers_of_worktrees_idle_for_a_day(
    installed: Path, tmp_path: Path
) -> None:
    git(installed, "config", "core.fsmonitor", "true")
    idle, active = tmp_path / "idle", tmp_path / "active"
    for worktree in (idle, active):
        git(installed, "worktree", "add", "-q", "--detach", str(worktree))
    watched = (installed, idle, active)

    def running() -> dict[Path, bool]:
        return {
            worktree: not subprocess.run(
                ["git", "fsmonitor--daemon", "status"], cwd=worktree, check=False
            ).returncode
            for worktree in watched
        }

    try:
        for worktree in watched:
            git(worktree, "status")
        if not all(running().values()):
            pytest.skip("this Git build has no file watcher")
        day_ago = time.time() - 25 * 3600
        for worktree in (installed, idle):
            index = git(
                worktree, "rev-parse", "--path-format=absolute", "--git-path", "index"
            )
            os.utime(index, (day_ago, day_ago))
        update_runner.remove_stale_candidates(installed)
        assert running() == {installed: True, idle: False, active: True}
    finally:
        for worktree in watched:
            subprocess.run(
                ["git", "fsmonitor--daemon", "stop"], cwd=worktree, check=False
            )


@pytest.mark.parametrize(
    "still_running", [True, False], ids=["during-update", "during-cleanup"]
)
def test_interrupted_update_stops_every_process_and_records_failure(
    installed: Path, tmp_path: Path, still_running: bool
) -> None:
    child = tmp_path / "child.pid"
    work = f"sleep 60 & echo $! > {child}" + ("; wait" if still_running else "")
    setup = (
        "import subprocess, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "import update, update_runner\n"
    )
    inner = tmp_path / "inner.py"
    inner.write_text(
        setup
        + "update.update = lambda root, repair=False, remember=False: subprocess.run(\n"
        f"    ['sh', '-c', \"trap '' TERM; {work}\"],\n"
        "    check=True,\n"
        ")\n"
        "raise SystemExit(update_runner.apply_update(Path.cwd()))\n"
    )
    supervisor = tmp_path / "supervisor.py"
    supervisor.write_text(
        setup
        + f"update_runner.update_command = lambda *options: [sys.executable, {str(inner)!r}]\n"
        "raise SystemExit(update_runner.run_update(Path.cwd()))\n"
    )
    worker = subprocess.Popen(
        [sys.executable, str(supervisor)], cwd=installed, start_new_session=True
    )
    ready = child if still_running else installed / update_runner.RESULT_FILE
    deadline = time.monotonic() + 30
    while not ready.is_file() or not ready.read_text().strip():
        assert time.monotonic() < deadline and worker.poll() is None
        time.sleep(0.05)
    assert update_runner.update_running(installed)
    worker.terminate()
    assert worker.wait(timeout=60) == int(still_running)
    sleeper = int(child.read_text())
    assert subprocess.run(["kill", "-0", str(sleeper)], check=False).returncode != 0
    result = (installed / update_runner.RESULT_FILE).read_text()
    assert (
        "Hard Eng update failed: interrupted by signal 15" in result
    ) == still_running
    assert not update_runner.update_running(installed)


def test_a_stop_after_the_result_is_recorded_keeps_the_result(
    installed: Path, tmp_path: Path
) -> None:
    script = tmp_path / "apply.py"
    script.write_text(
        "import os, signal, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "import update, update_runner\n"
        "update.update = lambda root, repair=False, remember=False: None\n"
        "code = update_runner.apply_update(Path.cwd())\n"
        "os.kill(os.getpid(), signal.SIGTERM)\n"
        "raise SystemExit(code)\n"
    )
    applied = subprocess.run([sys.executable, str(script)], cwd=installed, check=False)
    assert applied.returncode == 0
    assert "failed" not in update_runner.last_result(installed)


def test_update_commit_is_not_counted_as_session_work(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update_runner, "start_update", Mock(return_value="started"))
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    before: JsonObject = {"session_id": "before"}
    after: JsonObject = {"session_id": "after"}
    other = installed / ".hard-eng/sessions/other.json"
    other.parent.mkdir(parents=True)
    other.write_text(json.dumps({"base": "c" * 40}))
    agent_hooks.session_context(installed, before)
    head = git(installed, "rev-parse", "HEAD")
    (installed / ".hooks/update.py").write_text("updated = True\n")
    commit(installed, "Update Hard Eng to " + "b" * 40)
    agent_hooks.session_context(installed, after)
    (installed / "app.py").write_text("print('user work')\n")
    commit(installed, "user work")
    assert update_runner.rebase_sessions(installed, head)
    assert json.loads(other.read_text())["base"] == "c" * 40
    assert agent_hooks.completion(installed, after)["decision"] == "block"
    git(installed, "reset", "-q", "--hard", "HEAD^")
    assert "no code checks run" in str(agent_hooks.completion(installed, before))
    os.remove(installed / ".hooks/update.py")
    assert agent_hooks.completion(installed, before)["decision"] == "block"


def install_hook(root: Path, name: str, script: str) -> None:
    hook = root / ".git/hooks" / name
    hook.write_text("#!/bin/sh\n" + script)
    hook.chmod(0o755)


def pushed_release(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    source, target, _ = release
    add_origin(target)
    select_release(source, monkeypatch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    return target


def refused_release(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Mock]:
    source, target, _ = release
    config_path = target / "hard-eng.gates.json"
    config = json.loads(config_path.read_text())
    scanner = ["node", "scan.mjs", "gitleaks", "dir", "--report-path", "files.sarif"]
    config["shared"].append(
        {"name": "files", "role": "secrets-files", "command": scanner}
    )
    config_path.write_text(json.dumps(config))
    commit(target, "wrapped files scanner the new hooks reject")
    add_origin(target)
    select_release(source, monkeypatch)
    fetch = Mock(side_effect=update.fetch_sources)
    monkeypatch.setattr(update, "fetch_sources", fetch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    return target, fetch


def test_background_update_does_not_repeat_a_refusal_until_inputs_change(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, fetch = refused_release(release, monkeypatch)
    result = target / update_runner.RESULT_FILE
    assert update_runner.apply_update(target) == 0
    assert "secrets-files requires native" in result.read_text()
    assert "A fix in tracked files goes on the base branch" in result.read_text()
    assert update_runner.apply_update(target) == 0
    assert "it is not retried before 24 hours unless a new release" in (
        result.read_text()
    )
    assert fetch.call_count == 1
    with pytest.raises(ValueError, match="secrets-files requires native"):
        update.update(target, repair=True)
    assert fetch.call_count == 2
    (target / "notes.txt").write_text("new base work\n")
    commit(target, "base moved")
    git(target, "push", "-q", "--no-verify", "origin", "main")
    assert update_runner.apply_update(target) == 0
    assert "not retried" not in result.read_text()
    assert fetch.call_count == 3
    failure = target / update_runner.FAILURE_FILE
    saved = json.loads(failure.read_text())
    failure.write_text(json.dumps({**saved, "at": time.time() - 25 * 3600}))
    assert update_runner.apply_update(target) == 0
    assert fetch.call_count == 4


def test_setup_retries_a_remembered_refusal(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, fetch = refused_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    assert update_runner.apply_update(target) == 0
    assert fetch.call_count == 1
    with pytest.raises(ValueError, match="secrets-files requires native"):
        update_runner.locked_update(target, repair=True)
    assert fetch.call_count == 3


def test_an_update_replaces_the_old_tool_hook_commands(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = release[1]
    settings = target / ".claude/settings.json"
    old = "$(git rev-parse --show-toplevel 2>/dev/null)"
    settings.write_text(settings.read_text().replace("$CLAUDE_PROJECT_DIR", old))
    assert settings.read_text().count(old) == 3
    commit(target, "old tool hooks")
    pushed_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    updated = git(
        target, "show", f"{update_runner.UPDATE_BRANCH}:.claude/settings.json"
    )
    assert old not in updated
    assert updated.count("$CLAUDE_PROJECT_DIR/.hooks/") == 3


def test_a_linked_local_settings_file_does_not_block_the_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    with (target / ".git/info/exclude").open("a") as exclude:
        exclude.write(".claude/settings.local.json\n")
    local = target / ".claude/settings.local.json"
    local.write_text(
        '{"permissions":{"allow":'
        '["Bash(python3 .agents/hard-eng/current/.hooks/hard-eng.py check)"]}}\n'
    )
    before = local.read_bytes()
    assert git(target, "status", "--porcelain", "--ignored", str(local)).startswith(
        "!!"
    )
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "ready on hard-eng/update" in result
    assert local.read_bytes() == before


PRIVATE_MCP = '{"mcpServers":{"private":{"command":"private-integration"}}}\n'


def private_mcp_release(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, ignored: bool
) -> Path:
    source, target, _ = release
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
    (target / "app.js").write_text('import { Client } from "appwrite";\n')
    if ignored:
        (target / ".gitignore").write_text(".mcp.json\n")
    commit(target, "use Appwrite")
    add_origin(target)
    (target / ".mcp.json").write_text(PRIVATE_MCP)
    select_release(source, monkeypatch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    return target


@pytest.mark.parametrize("ignored", [True, False], ids=["ignored", "untracked"])
def test_an_update_refuses_to_replace_a_local_file_git_does_not_track(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, ignored: bool
) -> None:
    target = private_mcp_release(release, monkeypatch, ignored)
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert ".mcp.json" in result and "ready on" not in result
    assert "move or rename them, then rerun setup to retry: curl " in result
    assert not git(target, "branch", "--list", update_runner.UPDATE_BRANCH)
    assert (target / ".mcp.json").read_text() == PRIVATE_MCP
    assert update_runner.apply_update(target) == 0
    assert "not retried" in (target / update_runner.RESULT_FILE).read_text()


@pytest.mark.parametrize("kind", ["untracked", "ignored", "link"])
def test_an_update_refuses_a_local_file_where_it_needs_a_folder(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    target = private_mcp_release(release, monkeypatch, False)
    (target / ".mcp.json").unlink()
    skill = Path(".agents/skills/appwrite-backend")
    if kind == "link":
        (target / skill).symlink_to(target / ".agents")
    else:
        (target / skill).write_text("mine\n")
    if kind == "ignored":
        with (target / ".git/info/exclude").open("a") as exclude:
            exclude.write(f"{skill}\n")
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert str(skill) in result and "ready on" not in result
    assert not git(target, "branch", "--list", update_runner.UPDATE_BRANCH)
    assert (target / skill).is_symlink() == (kind == "link")
    assert update_runner.apply_update(target) == 0
    assert "not retried" in (target / update_runner.RESULT_FILE).read_text()


def test_an_update_without_a_shipping_policy_uses_the_remote_default_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    remote = target.parent / "origin.git"
    git(remote, "branch", "-m", "main", "master")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/master")
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "ready on" in result
    assert update_runner.NOT_PUBLISHED not in result


def test_a_setup_rerun_restores_the_pre_push_hook_when_origin_cannot_be_reached(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    git(target, "remote", "set-url", "origin", str(target.parent / "gone.git"))
    hook = target / ".git/hooks/pre-push"
    hook.unlink(missing_ok=True)
    with pytest.raises(subprocess.SubprocessError):
        update_runner.locked_update(target, repair=True)
    assert hook.is_file()


def test_a_setup_rerun_refuses_to_replace_a_local_file_git_does_not_track(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = private_mcp_release(release, monkeypatch, True)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    update_runner.record_result(target, update_runner.failed_update("old refusal"))
    with pytest.raises(ValueError, match=r"\.mcp\.json"):
        update_runner.locked_update(target, repair=True)
    recorded = (target / update_runner.RESULT_FILE).read_text()
    assert ".mcp.json" in recorded and "old refusal" not in recorded
    assert not git(target, "branch", "--list", update_runner.UPDATE_BRANCH)
    assert (target / ".mcp.json").read_text() == PRIVATE_MCP


def test_a_failing_project_commit_hook_leaves_the_checkout_and_worktrees_unchanged(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    install_hook(target, "pre-commit", "echo rejected by project hook\nexit 1\n")

    def files() -> dict[Path, bytes]:
        return {
            path.relative_to(target): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
            and not {".git", ".hard-eng", "__pycache__"} & set(path.parts)
        }

    before = files()
    head, branch = (
        git(target, "rev-parse", "HEAD"),
        git(target, "branch", "--show-current"),
    )
    worktrees = git(target, "worktree", "list", "--porcelain")
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "git commit exited 1" in result and "rejected by project hook" in result
    assert "project commit hook" in result
    assert git(target, "rev-parse", "HEAD") == head
    assert git(target, "branch", "--show-current") == branch
    assert git(target, "worktree", "list", "--porcelain") == worktrees
    assert git(target, "status", "--porcelain") == ""
    assert not git(target, "branch", "--list", update_runner.UPDATE_BRANCH)
    assert files() == before


def test_background_update_retries_after_a_network_failure(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, fetch = refused_release(release, monkeypatch)
    fetches = fetch.side_effect
    fetch.side_effect = subprocess.CalledProcessError(128, ["git", "clone"])
    assert update_runner.apply_update(target) == 0
    fetch.side_effect = fetches
    assert update_runner.apply_update(target) == 0
    assert fetch.call_count == 2
    assert "not retried" not in (target / update_runner.RESULT_FILE).read_text()


def test_interrupted_write_keeps_the_original_file(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = installed / ".hooks/update.py"
    target.write_text("original = True\n")

    def interrupted(_self: Path, _target: Path) -> Path:
        raise subprocess.SubprocessError("interrupted by signal 15")

    monkeypatch.setattr(Path, "replace", interrupted)
    with pytest.raises(subprocess.SubprocessError):
        update.write_changes(installed, {".hooks/update.py": "new = True\n"})
    assert target.read_text() == "original = True\n"
    assert sorted(path.name for path in target.parent.iterdir()) == [
        "hard-eng-source.json",
        "update.py",
    ]


def test_install_commit_with_crlf_lines_kept_by_git_filters_is_not_undone(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = project_with_commit_hook(tmp_path, "#!/bin/sh\nexit 0\n")
    (project / ".gitattributes").write_text("*.md text eol=crlf\n")
    (project / "AGENTS.md").write_bytes(b"# Project rules\r\n\r\nKeep this.\r\n")
    commit(project, "windows line endings")
    head = git(project, "rev-parse", "HEAD")
    installer.install(project)
    output = capsys.readouterr().out
    assert "Committed the installed files locally without pushing." in output
    assert git(project, "rev-parse", "HEAD") != head


def test_install_commit_rewritten_by_a_hook_is_found_when_the_message_changes(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = project_with_commit_hook(
        tmp_path,
        "#!/bin/sh\necho '<!-- formatted -->' >> AGENTS.md\ngit add AGENTS.md\n",
    )
    message = project / ".git/hooks/commit-msg"
    message.write_text(
        '#!/bin/sh\nprintf "chore: %s" "$(cat "$1")" > "$1.new"\nmv "$1.new" "$1"\n'
    )
    message.chmod(0o755)
    head = git(project, "rev-parse", "HEAD")
    installer.install(project)
    output = capsys.readouterr().out
    assert "Committed the installed files locally without pushing." not in output
    assert "AGENTS.md" in output.split("Installed files are not committed (")[1]
    assert git(project, "rev-parse", "HEAD") == head
    assert "<!-- formatted -->" not in (project / "AGENTS.md").read_text()


def prefix_commit_messages(root: Path) -> None:
    install_hook(
        root,
        "commit-msg",
        'printf "chore: %s" "$(cat "$1")" > "$1.new"\nmv "$1.new" "$1"\n',
    )


def test_install_moves_session_bases_when_a_hook_changes_the_commit_message(
    installer: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    project = project_with_commit_hook(tmp_path, "#!/bin/sh\nexit 0\n")
    prefix_commit_messages(project)
    head = git(project, "rev-parse", "HEAD")
    session = project / ".hard-eng/sessions/work.json"
    session.parent.mkdir(parents=True)
    session.write_text(json.dumps({"base": head}))
    installer.install(project)
    assert "Committed the installed files locally without pushing." in (
        capsys.readouterr().out
    )
    assert git(project, "log", "-1", "--format=%s") == "chore: Install Hard Eng"
    assert json.loads(session.read_text())["base"] == git(project, "rev-parse", "HEAD")


def test_an_update_lands_when_a_project_hook_changes_the_commit_message(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    prefix_commit_messages(target)
    assert update_runner.apply_update(target) == 0
    assert "ready on" in (target / update_runner.RESULT_FILE).read_text()
    subject = git(target, "log", "-1", "--format=%s", update_runner.UPDATE_BRANCH)
    assert subject.startswith("chore: Update Hard Eng to ")


def test_the_note_says_pull_when_the_update_is_already_on_the_base(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    assert "update-pr" in update_runner.freshness_note(target)
    git(
        target,
        "push",
        "-q",
        "--no-verify",
        "origin",
        f"{update_runner.UPDATE_BRANCH}:main",
    )
    note = update_runner.freshness_note(target)
    assert "already on origin/main" in note and "git rebase origin/main" in note
    assert "update-pr" not in note


def test_a_failed_remote_lookup_keeps_gits_reason(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    git(target, "remote", "set-url", "origin", str(target.parent / "gone.git"))
    lookup = subprocess.run(
        ["git", "ls-remote", "origin"],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    reason = lookup.stderr.splitlines()[0]
    assert reason.startswith("fatal:") and "gone.git" in reason
    assert update_runner.apply_update(target) == 0
    assert reason in (target / update_runner.RESULT_FILE).read_text()


def test_the_refusal_for_a_main_checkout_names_a_step_that_works(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    (target / "notes.txt").write_text("base moved\n")
    commit(target, "base moved")
    git(target, "push", "-q", "--no-verify", "origin", "main")
    git(target, "switch", "-q", update_runner.UPDATE_BRANCH)
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "checked out" in result
    assert "switch the main checkout to another branch" in result
    assert "git worktree remove" not in result


def test_a_setup_rerun_records_its_result(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    update_runner.record_result(target, update_runner.failed_update("old refusal"))
    outcome = update_runner.locked_update(target, repair=True)
    recorded = (target / update_runner.RESULT_FILE).read_text()
    assert outcome in recorded
    assert "old refusal" not in recorded


GATES_FILE = "hard-eng.gates.json"
SRC_PROJECT = '[project]\nname="mylib"\nversion="1"\n[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'


def add_src_package(root: Path, name: str) -> None:
    package = root / "src" / name
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(f"NAME = '{name}'\n")
    (package / "use.py").write_text(f"from {name} import NAME\n\nvalue = NAME\n")


def installed_python_project(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, remote: bool
) -> Path:
    source = release[0]
    select_release(source, monkeypatch)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    project = source.parent / "project"
    init(project)
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text(SRC_PROJECT)
    add_src_package(project, "mylib")
    subprocess.run(
        [sys.executable, str(source / "setup.py"), str(project)],
        check=True,
        capture_output=True,
    )
    commit(project, "installed")
    if remote:
        add_origin(project)
    git(project, "switch", "-q", "-c", "task")
    add_src_package(project, "extra")
    commit(project, "a second package")
    return project


@pytest.mark.parametrize("remote", [True, False])
def test_a_rerun_writes_the_planned_gates_file_to_the_current_checkout(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, remote: bool
) -> None:
    project = installed_python_project(release, monkeypatch, remote)
    before = (project / GATES_FILE).read_text()
    assert "extra" not in before
    outcome = update_runner.locked_update(project, repair=True)
    assert f"This checkout: setup wrote {GATES_FILE} to match" in outcome
    assert ("pushed to a remote" in outcome) is not remote
    assert '"extra"' in (project / GATES_FILE).read_text()
    assert git(project, "status", "--porcelain") == f"M {GATES_FILE}"
    assert git(project, "diff", "--cached", "--name-only") == ""
    again = update_runner.locked_update(project, repair=True)
    assert "This checkout" not in again


def test_a_rerun_writes_each_project_file_that_setup_plans_and_no_scaffold_file(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    (project / "web/src").mkdir(parents=True)
    (project / "web/package.json").write_text('{"name": "web", "private": true}\n')
    (project / "web/src/index.ts").write_text("export const value = 1;\n")
    commit(project, "a web package")
    outcome = update_runner.locked_update(project, repair=True)
    written = f"{GATES_FILE}, web/.semgrepignore, web/tsconfig.json"
    assert f"This checkout: setup wrote {written} to match" in outcome
    assert git(project, "status", "--porcelain", "-uall").splitlines() == [
        f"M {GATES_FILE}",
        "?? web/.semgrepignore",
        "?? web/tsconfig.json",
    ]
    assert '"web"' in (project / GATES_FILE).read_text()


def test_a_rerun_goes_on_when_setup_refuses_the_checkout(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    before = (project / GATES_FILE).read_text()
    skill = project / ".agents/skills/he/SKILL.md"
    skill.write_text(skill.read_text() + "\nA local line.\n")
    outcome = update_runner.locked_update(project, repair=True)
    assert "No newer CI-verified Hard Eng revision is available." in outcome
    assert "This checkout is unchanged: setup refused the update: " in outcome
    assert ".agents/skills/he/SKILL.md already differs" in outcome
    assert (project / GATES_FILE).read_text() == before
    assert skill.read_text().endswith("\nA local line.\n")


def test_a_rerun_with_no_remote_keeps_the_pushed_line_when_the_fetch_fails(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, False)
    failure = subprocess.CalledProcessError(128, ["git", "checkout"])
    monkeypatch.setattr(update, "fetch_sources", Mock(side_effect=failure))
    outcome = update_runner.locked_update(project, repair=True)
    assert outcome.startswith(update_runner.NOT_PUBLISHED)
    assert "This checkout is unchanged: the installed release could not be" in outcome
    assert outcome.endswith("exit status 128.")


def test_a_rerun_the_plan_refuses_writes_nothing(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    before = (project / GATES_FILE).read_text()
    (project / "AGENTS.md").write_text("# Project rules\n")
    monkeypatch.setattr(
        update, "update_plan", Mock(side_effect=ValueError("setup refused the update"))
    )
    with pytest.raises(ValueError, match="setup refused"):
        update_runner.locked_update(project, repair=True)
    assert (project / GATES_FILE).read_text() == before


def test_an_update_at_session_start_does_not_touch_the_checkout(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    before = (project / GATES_FILE).read_text()
    fetch = Mock(side_effect=update.fetch_sources)
    monkeypatch.setattr(update, "fetch_sources", fetch)
    outcome = update_runner.prepare_update(project)
    assert "This checkout" not in outcome
    assert (project / GATES_FILE).read_text() == before
    assert fetch.call_count == 0


def test_an_install_that_is_not_on_the_base_branch_gets_the_pushed_line(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = release[0]
    select_release(source, monkeypatch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    project = source.parent / "project"
    init(project)
    (project / "package.json").write_text('{"private":true}')
    (project / "bun.lock").write_text('{"lockfileVersion": 1}\n')
    commit(project, "baseline")
    add_origin(project)
    subprocess.run(
        [sys.executable, str(source / "setup.py"), str(project)],
        check=True,
        capture_output=True,
    )
    for repair in (False, True):
        outcome = update_runner.prepare_update(project, repair)
        assert outcome.startswith(update_runner.NOT_PUBLISHED)
    assert update_runner.apply_update(project) == 0
    assert update_runner.freshness_note(project) == update_runner.NOT_PUBLISHED

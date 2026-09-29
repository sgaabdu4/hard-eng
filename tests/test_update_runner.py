"""Session start must never wait on, leak or duplicate a scaffold update."""

import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import agent_hooks
import pytest
import update
import update_runner
from conftest import SOURCE, commit, git
from gate_config import JsonObject
from test_adoption import link_skill_into_old_copy
from test_updates import select_release


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
    assert message.endswith("Last update result: none recorded yet")
    (installed / update_runner.RESULT_FILE).write_text("earlier: Updated Hard Eng\n")
    assert update_runner.start_update(installed).endswith(
        "Last update result: earlier: Updated Hard Eng"
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
    assert message.startswith("A Hard Eng update is already running")
    assert not (installed / update_runner.LOG_FILE).exists()
    assert not spawned.exists()
    installer.assert_not_called()
    assert not (installed / update_runner.RESULT_FILE).exists()


def test_stop_waits_for_running_update_instead_of_rerunning_setup(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(update, "latest_verified", Mock(return_value="b" * 40))
    with held_lock(installed), pytest.raises(ValueError, match="still running"):
        update.require_current(installed)
    with pytest.raises(ValueError, match="Use the supported updater"):
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
        setup + "update.update = lambda root, repair=False: subprocess.run(\n"
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
    assert worker.wait(timeout=60) == 0
    sleeper = int(child.read_text())
    assert subprocess.run(["kill", "-0", str(sleeper)], check=False).returncode != 0
    result = (installed / update_runner.RESULT_FILE).read_text()
    assert (
        "Hard Eng update failed: interrupted by signal 15" in result
    ) == still_running
    assert not update_runner.update_running(installed)


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
    assert update_runner.rebase_sessions(
        installed, head, "Update Hard Eng to " + "b" * 40
    )
    assert json.loads(other.read_text())["base"] == "c" * 40
    assert agent_hooks.completion(installed, after)["decision"] == "block"
    git(installed, "reset", "-q", "--hard", "HEAD^")
    assert "no code checks were run" in str(agent_hooks.completion(installed, before))
    os.remove(installed / ".hooks/update.py")
    assert agent_hooks.completion(installed, before)["decision"] == "block"


def commit_changes(root: Path, changes: dict[str, str | None]) -> None:
    update_runner.commit_update(
        root, changes, {}, "b" * 40, update_runner.snapshot(root, changes)
    )


def install_hook(root: Path, name: str, script: str) -> None:
    hook = root / ".git/hooks" / name
    hook.write_text("#!/bin/sh\n" + script)
    hook.chmod(0o755)


def test_failed_update_commit_keeps_edits_made_while_it_ran(installed: Path) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    (installed / ".hooks/update.py").write_text("old = True\n")
    head = commit(installed, "managed files")
    install_hook(installed, "pre-commit", "echo 'agent edit' > AGENTS.md\nexit 1\n")
    changes: dict[str, str | None] = {
        "AGENTS.md": "updated rules\n",
        ".hooks/update.py": "new = True\n",
    }
    with pytest.raises(
        subprocess.SubprocessError, match="kept later edits to AGENTS.md"
    ):
        commit_changes(installed, changes)
    assert (installed / "AGENTS.md").read_text() == "agent edit\n"
    assert (installed / ".hooks/update.py").read_text() == "old = True\n"
    assert git(installed, "rev-parse", "HEAD") == head
    assert git(installed, "diff", "--cached", "--name-only") == ""


def test_update_keeps_an_edit_made_before_it_reached_that_path(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    (installed / ".hooks/update.py").write_text("old = True\n")
    (installed / "README.md").write_text("original readme\n")
    head = commit(installed, "managed files")
    changes: dict[str, str | None] = {
        "AGENTS.md": "updated rules\n",
        ".hooks/update.py": "new = True\n",
        "README.md": "updated readme\n",
    }
    before = update_runner.snapshot(installed, changes)
    install = update.replace_file

    def agent_edits_next_path(
        target: Path, content: bytes, ready: Callable[[], bool]
    ) -> bool:
        if target.name == "AGENTS.md":
            (installed / ".hooks/update.py").write_text("agent = True\n")
        return install(target, content, ready)

    monkeypatch.setattr(update, "replace_file", agent_edits_next_path)
    with pytest.raises(
        ValueError,
        match=r"^\.hooks/update\.py changed while the update was being applied$",
    ):
        update_runner.commit_update(installed, changes, {}, "b" * 40, before)
    assert (installed / ".hooks/update.py").read_text() == "agent = True\n"
    assert (installed / "AGENTS.md").read_text() == "original rules\n"
    assert (installed / "README.md").read_text() == "original readme\n"
    assert git(installed, "rev-parse", "HEAD") == head
    assert git(installed, "diff", "--cached", "--name-only") == ""


def test_rollback_leaves_paths_the_update_never_reached(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    (installed / "old.md").write_text("retired\n")
    commit(installed, "managed files")
    changes: dict[str, str | None] = {
        "AGENTS.md": "updated rules\n",
        "new.md": "planned\n",
        "old.md": None,
    }
    before = update_runner.snapshot(installed, changes)
    head = update_runner.current_head

    def agent_works_first(root: Path) -> str | None:
        (root / "AGENTS.md").write_text("agent edit\n")
        (root / "new.md").write_text("planned\n")
        (root / "old.md").unlink()
        return head(root)

    monkeypatch.setattr(update_runner, "current_head", agent_works_first)
    with pytest.raises(ValueError, match="^AGENTS.md changed"):
        update_runner.commit_update(installed, changes, {}, "b" * 40, before)
    assert (installed / "AGENTS.md").read_text() == "agent edit\n"
    assert (installed / "new.md").read_text() == "planned\n"
    assert not (installed / "old.md").exists()


def test_failed_update_commit_restores_staging_made_before_it(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    commit(installed, "managed files")
    install_hook(installed, "pre-commit", "exit 1\n")
    snapshot = update_runner.index_entries
    calls: list[int] = []

    def agent_stages_first(root: Path, names: list[str]) -> dict[str, str]:
        calls.append(len(calls))
        if len(calls) == 1:
            (root / "AGENTS.md").write_text("staged by agent\n")
            git(root, "add", "AGENTS.md")
            (root / "AGENTS.md").write_text("still editing\n")
        return snapshot(root, names)

    monkeypatch.setattr(update_runner, "index_entries", agent_stages_first)
    with pytest.raises(subprocess.SubprocessError, match="kept later edits"):
        commit_changes(installed, {"AGENTS.md": "updated rules\n"})
    assert git(installed, "show", ":AGENTS.md") == "staged by agent"
    assert (installed / "AGENTS.md").read_text() == "still editing\n"


def test_update_commit_never_takes_an_edit_made_after_its_writes(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    head = commit(installed, "managed files")
    snapshot = update_runner.index_entries

    def agent_edits_after_writes(root: Path, names: list[str]) -> dict[str, str]:
        (root / "AGENTS.md").write_text("agent edit\n")
        return snapshot(root, names)

    monkeypatch.setattr(update_runner, "index_entries", agent_edits_after_writes)
    with pytest.raises(subprocess.SubprocessError, match="kept later edits to AGENTS"):
        commit_changes(installed, {"AGENTS.md": "updated rules\n"})
    assert (installed / "AGENTS.md").read_text() == "agent edit\n"
    assert git(installed, "rev-parse", "HEAD") == head
    assert git(installed, "diff", "--cached", "--name-only") == ""


def test_update_commit_never_takes_a_link_repointed_after_its_writes(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("a", "b", "c"):
        (installed / "skills" / name).mkdir(parents=True)
        (installed / "skills" / name / "SKILL.md").write_text(name)
    link = installed / ".claude/skills/he"
    link.parent.mkdir(parents=True)
    link.symlink_to("../../skills/a", target_is_directory=True)
    head = commit(installed, "linked skill")
    snapshot = update_runner.index_entries

    def agent_repoints_after_writes(root: Path, names: list[str]) -> dict[str, str]:
        link.unlink()
        link.symlink_to("../../skills/c", target_is_directory=True)
        return snapshot(root, names)

    monkeypatch.setattr(update_runner, "index_entries", agent_repoints_after_writes)
    links: dict[str, str | None] = {".claude/skills/he": "../../skills/b"}
    with pytest.raises(subprocess.SubprocessError, match="kept later edits to .claude"):
        update_runner.commit_update(installed, {}, links, "b" * 40, {})
    assert str(link.readlink()) == "../../skills/c"
    assert git(installed, "rev-parse", "HEAD") == head


def test_retiring_a_link_never_commits_a_folder_created_in_its_place(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "skills/old").mkdir(parents=True)
    (installed / "skills/old/SKILL.md").write_text("old")
    link = installed / ".claude/skills/old"
    link.parent.mkdir(parents=True)
    link.symlink_to("../../skills/old", target_is_directory=True)
    head = commit(installed, "linked skill")
    snapshot = update_runner.index_entries

    def agent_fills_the_path(root: Path, names: list[str]) -> dict[str, str]:
        (link / "agent.py").parent.mkdir(exist_ok=True)
        (link / "agent.py").write_text("print('agent')\n")
        return snapshot(root, names)

    monkeypatch.setattr(update_runner, "index_entries", agent_fills_the_path)
    links: dict[str, str | None] = {".claude/skills/old": None}
    with pytest.raises(
        subprocess.SubprocessError,
        match="old changed while the update was being applied",
    ):
        update_runner.commit_update(installed, {}, links, "b" * 40, {})
    assert (link / "agent.py").read_text() == "print('agent')\n"
    assert git(installed, "rev-parse", "HEAD") == head


def test_sessions_still_count_an_unplanned_file_under_a_planned_path(
    installed: Path,
) -> None:
    (installed / "skills/he").mkdir(parents=True)
    (installed / "skills/he/SKILL.md").write_text("planned")
    (installed / "skills/he/agent.py").write_text("print('agent')\n")
    commit(installed, "update with an extra file")
    commit_id = git(installed, "rev-parse", "HEAD")
    planned: dict[str, str | None] = {"skills/he/SKILL.md": "planned", "skills": None}
    assert not update_runner.committed_matches(installed, commit_id, planned)
    del planned["skills"]
    assert update_runner.committed_matches(installed, commit_id, planned)


def test_sessions_still_count_an_update_commit_holding_other_content(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    head = commit(installed, "managed files")
    state = installed / ".hard-eng/sessions/known.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"base": head, "dirty": {}}))
    check = update_runner.written

    def agent_edits_after_check(
        root: Path, name: str, content: str | None, link: bool
    ) -> bool:
        found = check(root, name, content, link)
        (root / name).write_text("agent edit\n")
        return found

    monkeypatch.setattr(update_runner, "written", agent_edits_after_check)
    commit_changes(installed, {"AGENTS.md": "updated rules\n"})
    assert git(installed, "show", "HEAD:AGENTS.md") == "agent edit"
    assert json.loads(state.read_text())["base"] == head


def test_interrupt_after_the_update_commit_keeps_the_update(installed: Path) -> None:
    (installed / ".hooks/update.py").write_text("old = True\n")
    head = commit(installed, "managed files")
    state = installed / ".hard-eng/sessions/known.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"base": head, "dirty": {}}))
    install_hook(installed, "post-commit", "kill -TERM $PPID\n")
    with pytest.raises(subprocess.SubprocessError, match="git commit exited"):
        commit_changes(installed, {".hooks/update.py": "new = True\n"})
    assert (installed / ".hooks/update.py").read_text() == "new = True\n"
    assert (
        git(installed, "log", "-1", "--format=%s") == f"Update Hard Eng to {'b' * 40}"
    )
    assert git(installed, "status", "--porcelain") == ""
    assert json.loads(state.read_text())["base"] == git(installed, "rev-parse", "HEAD")


def test_interrupt_after_installing_reports_the_installed_revision(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def interrupted(root: Path, repair: bool = False) -> str:
        (root / update.SOURCE_FILE).write_text(json.dumps({"revision": "b" * 40}))
        raise subprocess.SubprocessError("interrupted by signal 15")

    monkeypatch.setattr(update, "update", interrupted)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    assert update_runner.apply_update(installed) == 0
    result = (installed / update_runner.RESULT_FILE).read_text()
    assert f"Updated Hard Eng to {'b' * 40} with a local commit" in result
    assert "failed" not in result


def test_update_commit_landing_after_an_agent_commit_is_kept(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / ".hooks/update.py").write_text("old = True\n")
    commit(installed, "managed files")
    install = update.replace_file

    def install_while_agent_commits(
        target: Path, content: bytes, ready: Callable[[], bool]
    ) -> bool:
        git(installed, "commit", "-qm", "agent work", "--allow-empty")
        install_hook(installed, "post-commit", "kill -TERM $PPID\n")
        return install(target, content, ready)

    monkeypatch.setattr(update, "replace_file", install_while_agent_commits)
    with pytest.raises(subprocess.SubprocessError, match="git commit exited"):
        commit_changes(installed, {".hooks/update.py": "new = True\n"})
    assert (installed / ".hooks/update.py").read_text() == "new = True\n"
    assert git(installed, "log", "-2", "--format=%s").splitlines() == [
        f"Update Hard Eng to {'b' * 40}",
        "agent work",
    ]
    assert git(installed, "status", "--porcelain") == ""


def test_rollback_keeps_an_edit_made_to_an_already_checked_path(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("first.md", "second.md"):
        (installed / name).write_text("original\n")
    changes: dict[str, str | None] = {"first.md": "new\n", "second.md": "new\n"}
    update.write_changes(installed, changes)
    check = update_runner.written

    def edit_first_while_checking_second(
        root: Path, name: str, content: str | None, link: bool
    ) -> bool:
        if name == "second.md":
            (root / "first.md").write_text("agent edit\n")
        return check(root, name, content, link)

    monkeypatch.setattr(update_runner, "written", edit_first_while_checking_second)
    before: dict[str, bytes | None] = dict.fromkeys(changes, b"original\n")
    assert update_runner.roll_back(installed, changes, {}, before, {}, [*changes]) == []
    assert (installed / "first.md").read_text() == "agent edit\n"
    assert (installed / "second.md").read_text() == "original\n"


def test_rollback_keeps_an_edit_made_while_restoring_that_path(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = installed / "first.md"
    target.write_text("original\n")
    changes: dict[str, str | None] = {"first.md": "new\n"}
    update.write_changes(installed, changes)
    copy = shutil.copymode

    def edit_while_preparing(source: Path, destination: Path) -> None:
        target.write_text("agent edit\n")
        copy(source, destination)

    monkeypatch.setattr(shutil, "copymode", edit_while_preparing)
    before: dict[str, bytes | None] = {"first.md": b"original\n"}
    assert update_runner.roll_back(installed, changes, {}, before, {}, [*changes]) == [
        "first.md"
    ]
    assert target.read_text() == "agent edit\n"


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


def test_failed_update_commit_keeps_staging_made_while_it_ran(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / "AGENTS.md").write_text("original rules\n")
    (installed / ".hooks/update.py").write_text("old = True\n")
    commit(installed, "managed files")
    install_hook(installed, "pre-commit", "exit 1\n")
    unstage = update_runner.unstage_own

    def agent_stages_then_unstage(
        root: Path, names: list[str], staging: tuple[dict[str, str], dict[str, str]]
    ) -> None:
        (root / "AGENTS.md").write_text("staged by agent\n")
        git(root, "add", "AGENTS.md")
        (root / "AGENTS.md").write_text("still editing\n")
        unstage(root, names, staging)

    monkeypatch.setattr(update_runner, "unstage_own", agent_stages_then_unstage)
    changes: dict[str, str | None] = {
        "AGENTS.md": "updated rules\n",
        ".hooks/update.py": "new = True\n",
    }
    with pytest.raises(subprocess.SubprocessError, match="git commit exited 1"):
        commit_changes(installed, changes)
    assert git(installed, "show", ":AGENTS.md") == "staged by agent"
    assert (installed / "AGENTS.md").read_text() == "still editing\n"
    assert (installed / ".hooks/update.py").read_text() == "old = True\n"
    assert git(installed, "diff", "--cached", "--name-only") == "AGENTS.md"


def test_interrupt_right_after_staging_still_unstages_the_update(
    installed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (installed / ".hooks/update.py").write_text("old = True\n")
    commit(installed, "managed files")
    snapshot = update_runner.index_entries
    calls: list[int] = []

    def interrupted_after_add(root: Path, names: list[str]) -> dict[str, str]:
        calls.append(len(calls))
        if len(calls) == 2:
            os.kill(os.getpid(), signal.SIGTERM)
        return snapshot(root, names)

    monkeypatch.setattr(update_runner, "index_entries", interrupted_after_add)
    previous = signal.signal(signal.SIGTERM, update_runner.interrupt_update)
    try:
        with pytest.raises(subprocess.SubprocessError, match="signal 15"):
            commit_changes(installed, {".hooks/update.py": "new = True\n"})
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert git(installed, "diff", "--cached", "--name-only") == ""
    assert (installed / ".hooks/update.py").read_text() == "old = True\n"


def test_failed_update_restores_the_skill_folder_link(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    skill = link_skill_into_old_copy(target)
    select_release(source, monkeypatch)
    hook = target / ".git/hooks/pre-commit"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(subprocess.SubprocessError, match="git commit exited 1"):
        update.update(target)
    assert skill.is_symlink()
    assert git(target, "status", "--porcelain") == ""


@pytest.mark.parametrize("newer", [True, False], ids=["update", "repair"])
def test_migrating_a_skill_link_keeps_a_file_created_during_it(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, newer: bool
) -> None:
    source, target, _ = release
    skill = link_skill_into_old_copy(target)
    if newer:
        select_release(source, monkeypatch)
    else:
        monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    head = git(target, "rev-parse", "HEAD")
    install = update.replace_file
    created: list[Path] = []

    def agent_creates_a_planned_file(
        path: Path, content: bytes, ready: Callable[[], bool] = lambda: True
    ) -> bool:
        if not created and path.is_relative_to(skill):
            other = skill / "references/workflow.md"
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_text("agent edit\n")
            created.append(other)
        return install(path, content, ready)

    monkeypatch.setattr(update, "replace_file", agent_creates_a_planned_file)
    with pytest.raises(
        (ValueError, subprocess.SubprocessError), match="workflow.md changed while"
    ):
        update.update(target)
    assert created[0].read_text() == "agent edit\n"
    assert git(target, "rev-parse", "HEAD") == head

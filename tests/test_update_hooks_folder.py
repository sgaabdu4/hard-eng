"""Hard Eng's worktree launcher never leaves a tracked hooks folder dirty."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import change_size
import hook_chain
import pytest
import update
import update_runner
from conftest import add_origin, commit, git, init
from test_hook_chain import husky_shims
from test_update_runner import SRC_PROJECT, add_src_package
from test_updates import select_release

OWNER_HOOK = "#!/bin/sh\necho owner hook\n"
LAUNCHER = ".githooks/post-checkout"
KEPT_COPY = ".githooks/post-checkout.project"


def short_status(project: Path) -> str:
    return subprocess.check_output(
        ["git", "status", "--short", "--untracked-files=all"], cwd=project, text=True
    )


def installed_project(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    hooks: str,
) -> Path:
    """A project installed before the worktree launcher, whose own hooks folder is tracked."""
    select_release(release[0], monkeypatch)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    project = release[0].parent / "project"
    init(project)
    (project / "uv.lock").touch()
    (project / "pyproject.toml").write_text(SRC_PROJECT)
    add_src_package(project, "mylib")
    (project / ".gitignore").write_text(".env\n")
    if hooks == ".husky":
        husky_shims(project)
        (project / ".husky/pre-push").write_text("echo owner hook\n")
    else:
        (project / hooks).mkdir()
        (project / hooks / "pre-push").write_text(OWNER_HOOK)
        (project / hooks / "pre-push").chmod(0o755)
        git(project, "config", "core.hooksPath", hooks)
    commit(project, "project hooks")
    subprocess.run(
        [sys.executable, str(release[0] / "setup.py"), str(project)],
        check=True,
        capture_output=True,
    )
    git(project, "rm", "-q", f"{hooks}/post-checkout")
    commit(project, "installed before the worktree launcher")
    add_origin(project)
    return project


def tracked_hooks_project(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    return installed_project(release, monkeypatch, ".githooks")


def husky_project(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    return installed_project(release, monkeypatch, ".husky")


def launcher_left_by_a_rerun(project: Path) -> None:
    path = project / LAUNCHER
    path.write_text(hook_chain.WORKTREE_LAUNCHER)
    path.chmod(0o755)


def shell_gate_lists(project: Path, name: str) -> None:
    gates = project / "hard-eng.gates.json"
    config = json.loads(gates.read_text())
    shell = next(gate for gate in config["shared"] if gate.get("role") == "shell")
    shell["command"].append(name)
    gates.write_text(json.dumps(config, indent=2) + "\n")


def owner_post_checkout(project: Path) -> None:
    path = project / LAUNCHER
    path.write_text(OWNER_HOOK)
    path.chmod(0o755)
    shell_gate_lists(project, LAUNCHER)
    commit(project, "the project's own post-checkout hook")
    git(project, "push", "-q", "--no-verify", "origin", "main")


def a_linked_worktree_shares_the_env_file(project: Path) -> Path:
    (project / ".env").write_text("SECRET=local\n")
    linked = project.parent / "linked"
    git(project, "worktree", "add", "-q", "--detach", str(linked))
    assert (linked / ".env").resolve() == (project / ".env").resolve()
    return linked


def assert_clean_and_small(project: Path) -> None:
    assert short_status(project) == ""
    assert change_size.size_verdict(project) == (True, change_size.NO_CHANGE)


def test_a_setup_rerun_keeps_the_worktree_launcher_out_of_a_tracked_hooks_folder_status(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    update_runner.locked_update(project, repair=True)
    assert_clean_and_small(project)
    assert hook_chain.is_own(project, project / LAUNCHER)
    a_linked_worktree_shares_the_env_file(project)


def test_the_background_update_clears_a_worktree_launcher_that_a_rerun_left_untracked(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    launcher_left_by_a_rerun(project)
    assert update_runner.apply_update(project) == 0
    assert_clean_and_small(project)
    assert hook_chain.is_own(project, project / LAUNCHER)


def test_the_background_update_drops_a_launcher_entry_that_a_rerun_added_to_the_shell_gate(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    launcher_left_by_a_rerun(project)
    shell_gate_lists(project, LAUNCHER)
    assert update_runner.apply_update(project) == 0
    assert_clean_and_small(project)


def test_the_background_update_gives_back_the_projects_tracked_post_checkout_hook(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    owner_post_checkout(project)
    (project / KEPT_COPY).write_text(OWNER_HOOK)
    (project / KEPT_COPY).chmod(0o755)
    launcher_left_by_a_rerun(project)
    assert update_runner.apply_update(project) == 0
    assert_clean_and_small(project)
    assert (project / LAUNCHER).read_text() == OWNER_HOOK


def test_a_kept_copy_the_owner_changed_stays_as_it_is(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    owner_post_checkout(project)
    (project / KEPT_COPY).write_text(OWNER_HOOK + "echo edited\n")
    launcher_left_by_a_rerun(project)
    assert update_runner.apply_update(project) == 0
    assert short_status(project) == f" M {LAUNCHER}\n?? {KEPT_COPY}\n"


def test_a_setup_rerun_leaves_a_tracked_project_post_checkout_hook_alone(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    owner_post_checkout(project)
    update_runner.locked_update(project, repair=True)
    assert_clean_and_small(project)
    assert (project / LAUNCHER).read_text() == OWNER_HOOK


def test_the_background_update_keeps_its_launcher_in_a_hooks_folder_named_by_an_absolute_path_out_of_the_status(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    git(project, "config", "core.hooksPath", str(project / ".githooks"))
    assert update_runner.apply_update(project) == 0
    assert_clean_and_small(project)
    assert hook_chain.is_own(project, project / LAUNCHER)


def test_the_merged_update_and_the_pull_leave_the_default_branch_clean(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = release[0]
    project = tracked_hooks_project(release, monkeypatch)
    launcher_left_by_a_rerun(project)
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + "\nnewer release\n")
    select_release(source, monkeypatch)
    assert update_runner.apply_update(project) == 0
    branch = update_runner.UPDATE_BRANCH
    git(project, "push", "-q", "--no-verify", "origin", f"{branch}:main")
    git(project, "pull", "-q", "--ff-only", "origin", "main")
    assert_clean_and_small(project)


LISTS_LAUNCHERS = (
    "        and str(path.relative_to(root)) not in listed\n"
    "        and not is_own(root, path)\n"
)


def test_a_rerun_planned_by_a_release_that_lists_launchers_leaves_the_gates_file_alone(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    rules = release[0] / ".hooks/project_setup.py"
    text = rules.read_text()
    assert LISTS_LAUNCHERS in text
    rules.write_text(
        text.replace(LISTS_LAUNCHERS, LISTS_LAUNCHERS.partition("        and not")[0])
    )
    project = tracked_hooks_project(release, monkeypatch)
    update_runner.locked_update(project, repair=True)
    assert_clean_and_small(project)


def test_a_setup_rerun_keeps_the_husky_worktree_launcher_out_of_the_status(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = husky_project(release, monkeypatch)
    update_runner.locked_update(project, repair=True)
    assert_clean_and_small(project)
    linked = a_linked_worktree_shares_the_env_file(project)
    assert (linked / ".husky/_/pre-push").is_file()


def exclude_text(project: Path) -> str:
    exclude = project / ".git/info/exclude"
    return exclude.read_text() if exclude.is_file() else ""


@pytest.mark.parametrize("rerun", [False, True], ids=["background", "rerun"])
def test_a_task_worktree_inside_the_main_checkout_gets_no_launcher_and_no_exclude_line(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, rerun: bool
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    linked = project / ".claude/worktrees/task"
    git(project, "worktree", "add", "-q", "--detach", str(linked))
    before = exclude_text(project)
    if rerun:
        update_runner.locked_update(linked, repair=True)
    else:
        assert update_runner.apply_update(linked) == 0
    assert short_status(project) == ""
    assert short_status(linked) == ""
    assert exclude_text(project) == before


def test_an_ignored_hooks_folder_still_chains_the_projects_post_checkout_hook(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    with (project / ".git/info/exclude").open("a") as exclude:
        exclude.write("/.localhooks/\n")
    hooks = project / ".localhooks"
    hooks.mkdir()
    (hooks / "post-checkout").write_text(OWNER_HOOK)
    (hooks / "post-checkout").chmod(0o755)
    git(project, "config", "core.hooksPath", ".localhooks")
    update_runner.locked_update(project, repair=True)
    assert short_status(project) == ""
    assert hook_chain.is_own(project, hooks / "post-checkout")
    assert (hooks / "post-checkout.project").read_text() == OWNER_HOOK


def test_the_background_update_gives_back_a_husky_hook_with_its_committed_mode(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = husky_project(release, monkeypatch)
    hook = project / ".husky/post-checkout"
    hook.write_text("echo owner hook\n")
    hook.chmod(0o644)
    commit(project, "the project's own husky post-checkout hook")
    git(project, "push", "-q", "--no-verify", "origin", "main")
    copy = hook_chain.project_copy(hook)
    copy.write_text("echo owner hook\n")
    copy.chmod(0o644)
    hook.write_text(hook_chain.HUSKY_WORKTREE_LAUNCHER)
    hook.chmod(0o755)
    assert update_runner.apply_update(project) == 0
    assert_clean_and_small(project)


def test_a_launcher_waiting_for_the_install_commit_stays_in_the_status(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    git(project, "rm", "-q", "--cached", update.SOURCE_FILE)
    git(project, "commit", "-qm", "install not committed yet")
    launcher_left_by_a_rerun(project)
    assert update_runner.apply_update(project) == 0
    assert f"?? {LAUNCHER}\n" in short_status(project)


def test_an_owner_hook_that_replaces_the_hidden_launcher_shows_again(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    update_runner.locked_update(project, repair=True)
    assert short_status(project) == ""
    (project / LAUNCHER).write_text(OWNER_HOOK)
    assert update_runner.apply_update(project) == 0
    assert short_status(project) == f"?? {LAUNCHER}\n"


def test_a_session_in_a_task_worktree_clears_the_launcher_of_the_main_checkout(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    launcher_left_by_a_rerun(project)
    linked = project / ".claude/worktrees/task"
    git(project, "worktree", "add", "-q", "--detach", str(linked))
    assert update_runner.apply_update(linked) == 0
    assert_clean_and_small(project)
    assert short_status(linked) == ""


def test_a_gates_change_of_the_owner_beside_the_launcher_entry_stays(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    launcher_left_by_a_rerun(project)
    shell_gate_lists(project, LAUNCHER)
    gates = project / "hard-eng.gates.json"
    config = json.loads(gates.read_text())
    config["owner_note"] = "kept"
    gates.write_text(json.dumps(config, indent=2) + "\n")
    before = gates.read_bytes()
    assert update_runner.apply_update(project) == 0
    assert gates.read_bytes() == before
    assert short_status(project) == " M hard-eng.gates.json\n"


def test_a_tracked_hook_the_owner_changed_after_the_rerun_stays_as_it_is(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    owner_post_checkout(project)
    (project / KEPT_COPY).write_text(OWNER_HOOK)
    (project / LAUNCHER).write_text(OWNER_HOOK + "echo edited\n")
    assert update_runner.apply_update(project) == 0
    assert (project / LAUNCHER).read_text() == OWNER_HOOK + "echo edited\n"
    assert (project / KEPT_COPY).read_text() == OWNER_HOOK


def test_an_exclude_line_the_owner_wrote_stays_when_their_hook_replaces_the_launcher(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    with (project / ".git/info/exclude").open("a") as exclude:
        exclude.write(f"/{LAUNCHER}\n")
    (project / LAUNCHER).write_text(OWNER_HOOK)
    assert update_runner.apply_update(project) == 0
    assert f"/{LAUNCHER}\n" in exclude_text(project)


def test_a_committed_kept_copy_is_never_deleted_when_the_hook_is_given_back(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tracked_hooks_project(release, monkeypatch)
    owner_post_checkout(project)
    (project / KEPT_COPY).write_text(OWNER_HOOK)
    commit(project, "the project's own copy")
    launcher_left_by_a_rerun(project)
    assert update_runner.apply_update(project) == 0
    assert (project / KEPT_COPY).read_text() == OWNER_HOOK
    assert " D " not in short_status(project)

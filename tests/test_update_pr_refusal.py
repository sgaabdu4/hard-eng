import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import update_pr
import update_runner
from conftest import SOURCE, add_origin, commit, git
from test_update_runner import (
    GATES_FILE,
    add_shipping_policy,
    installed_python_project,
    refused_release,
    shared_names,
)

FIX_FIRST = (
    "Fix that cause first. A fix in tracked files goes on the base branch as its own "
    "commit, since the update is built from it. Cause outside repo → tell user. "
    "Installed gates still apply."
)

CI_STEP = (
    "CI setup pending: add a `shipping` block with the project's checks and a "
    "measured ci_seconds budget to hard-eng.gates.json and merge it to the base "
    "branch, then rerun setup"
)


def test_update_pr_fails_after_a_remembered_refusal(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, _ = refused_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()
    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert "Hard Eng update failed" in printed
    assert "secrets-files requires native" in printed
    assert "Nothing to publish" not in printed


NO_NEWER_RELEASE = """
import runpy, sys
sys.path.insert(0, ".hooks")
import update
update.latest_verified = lambda previous: None
sys.argv = [".hooks/hard-eng.py", *sys.argv[1:]]
runpy.run_path(".hooks/hard-eng.py", run_name="__main__")
"""


@pytest.mark.parametrize("command", [["update-pr"], ["update", "--apply"]])
def test_update_pr_with_no_update_branch_prints_no_git_error(
    release: tuple[Path, Path, str], command: list[str]
) -> None:
    _, target, _ = release
    add_origin(target)
    done = subprocess.run(
        [sys.executable, "-c", NO_NEWER_RELEASE, *command],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout
    assert "fatal:" not in done.stderr


def recorded_failure(project: Path) -> str:
    recorded = (project / update_runner.RESULT_FILE).read_text()
    return ("Hard Eng" + recorded.partition("Hard Eng")[2]).strip()


def test_a_failed_update_build_still_names_the_files_that_the_rerun_wrote(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    gone = project.parent / "gone.git"
    git(project, "remote", "set-url", "origin", str(gone))
    with pytest.raises(subprocess.SubprocessError) as error:
        update_runner.locked_update(project, repair=True)
    cause = f"git ls-remote exited 128: fatal: '{gone}' does not appear to be a git repository"
    note = f"This checkout: setup wrote {GATES_FILE}; review and commit it; {CI_STEP}."
    assert str(error.value) == f"{cause}. {note}"
    assert recorded_failure(project) == (
        f"Hard Eng update failed: {cause}. {FIX_FIRST} {note}"
    )


def test_a_build_error_that_needs_more_arguments_keeps_its_cause_and_the_note(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    cause = json.JSONDecodeError("Expecting value", "{", 0)
    monkeypatch.setattr(update_runner, "build_update", Mock(side_effect=cause))
    with pytest.raises(ValueError) as error:
        update_runner.locked_update(project, repair=True)
    note = f"This checkout: setup wrote {GATES_FILE}; review and commit it; {CI_STEP}."
    assert str(error.value) == f"Expecting value: line 1 column 1 (char 0). {note}"
    assert recorded_failure(project) == (
        f"Hard Eng update failed: Expecting value: line 1 column 1 (char 0). {FIX_FIRST} {note}"
    )


def base_with_policy(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    project = installed_python_project(release, monkeypatch, True)
    git(project, "switch", "-q", "main")
    add_shipping_policy(project)
    git(project, "push", "-q", "--no-verify", "origin", "main")
    git(project, "switch", "-q", "task")
    git(project, "merge", "-q", "main")
    return project


def test_the_update_brings_the_workflow_files_once_the_base_holds_the_shipping_block(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = base_with_policy(release, monkeypatch)
    outcome = update_runner.locked_update(project, repair=True)
    assert (
        "the update brings the workflow files and their gates when the `shipping` block of hard-eng.gates.json is on the base branch"
        in outcome
    )
    tree = git(project, "ls-tree", "-r", "--name-only", update_runner.UPDATE_BRANCH)
    assert ".github/workflows/hard-eng.yml" in tree.splitlines()
    gates = git(project, "show", f"{update_runner.UPDATE_BRANCH}:{GATES_FILE}")
    names = [gate["name"] for gate in json.loads(gates)["shared"]]
    assert {"actionlint", "zizmor"} <= set(names)


def test_a_rerun_writes_the_workflow_gates_when_the_checkout_has_a_workflow(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    add_shipping_policy(project)
    workflows = project / ".github/workflows"
    workflows.mkdir(parents=True)
    source = SOURCE / ".github/workflows/hard-eng.yml"
    (workflows / "hard-eng.yml").write_text(source.read_text())
    commit(project, "a workflow")
    outcome = update_runner.locked_update(project, repair=True)
    assert "the update brings the workflow files" not in outcome
    assert {"actionlint", "zizmor"} <= set(shared_names(project))


def built_repair_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    project = base_with_policy(release, monkeypatch)
    update_runner.locked_update(project, repair=True)
    return project


def test_a_repair_branch_in_its_own_worktree_is_ready_when_nothing_is_newer(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = built_repair_branch(release, monkeypatch)
    git(
        project,
        "worktree",
        "add",
        "-q",
        str(project.parent / "fixing"),
        update_runner.UPDATE_BRANCH,
    )
    outcome = update_runner.locked_update(project, repair=True)
    assert "ready on" in outcome


def test_a_merged_repair_branch_at_the_base_tip_is_not_ready(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = built_repair_branch(release, monkeypatch)
    branch = update_runner.UPDATE_BRANCH
    tip = git(project, "rev-parse", "origin/main")
    assert update_runner.branch_current(project, tip)
    git(project, "push", "-q", "--no-verify", "origin", f"{branch}:main")
    git(project, "fetch", "-q", "origin", "main")
    assert not update_runner.branch_current(
        project, git(project, "rev-parse", "origin/main")
    )


def test_a_rerun_with_the_block_only_on_the_checkout_prints_no_ci_setup_step(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    add_shipping_policy(project)
    capsys.readouterr()
    outcome = update_runner.locked_update(project, repair=True)
    shown = capsys.readouterr().err + outcome
    assert "CI setup pending" not in shown
    assert "the update brings the workflow files" in outcome


def test_a_rerun_with_no_shipping_block_names_the_ci_step_once(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    capsys.readouterr()
    outcome = update_runner.locked_update(project, repair=True)
    shown = capsys.readouterr().err + outcome
    assert shown.count("CI setup pending") == 1
    assert "merge it to the base branch, then rerun setup" in outcome


def test_a_refused_checkout_plan_with_no_shipping_block_names_the_ci_step_once(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    skill = project / ".agents/skills/he/SKILL.md"
    skill.write_text(skill.read_text() + "\nA local line.\n")
    capsys.readouterr()
    outcome = update_runner.locked_update(project, repair=True)
    shown = capsys.readouterr().err + outcome
    assert "This checkout is unchanged: setup refused the update: " in outcome
    assert shown.count("CI setup pending") == 1
    assert outcome.endswith(f"{CI_STEP}.")

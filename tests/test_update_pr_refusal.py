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
    note = f"This checkout: setup wrote {GATES_FILE}; review and commit it."
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
    note = f"This checkout: setup wrote {GATES_FILE}; review and commit it."
    assert str(error.value) == f"Expecting value: line 1 column 1 (char 0). {note}"
    assert recorded_failure(project) == (
        f"Hard Eng update failed: Expecting value: line 1 column 1 (char 0). {FIX_FIRST} {note}"
    )


def test_the_update_brings_the_workflow_files_once_the_base_holds_the_shipping_block(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    project = installed_python_project(release, monkeypatch, True)
    git(project, "switch", "-q", "main")
    add_shipping_policy(project)
    git(project, "push", "-q", "--no-verify", "origin", "main")
    git(project, "switch", "-q", "task")
    git(project, "merge", "-q", "main")
    outcome = update_runner.locked_update(project, repair=True)
    assert (
        "come with the update, which needs the `shipping` block of hard-eng.gates.json on the base branch"
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
    assert "come with the update" not in outcome
    assert {"actionlint", "zizmor"} <= set(shared_names(project))

import json
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from unittest.mock import Mock

import gate_config
import pytest
import update
import update_pr
import update_runner
from conftest import WORKFLOW_TEMPLATE, add_origin, commit, git, remove_application
from test_update_pr import FakeGh
from test_update_runner import (
    GATES_FILE,
    add_shipping_policy,
    installed_python_project,
    refused_release,
    shared_names,
)
from test_updates import select_release

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
    assert "SKILL.md already differs" in printed
    assert "Nothing to publish" not in printed


def test_update_pr_refuses_a_tip_that_the_older_gates_rule_rejects(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, _ = refused_release(release, monkeypatch, wrapped=True)
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()
    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert "secrets-files requires native" in printed
    assert f"Fix its checks on branch {update_runner.UPDATE_BRANCH}" in printed


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
    source = WORKFLOW_TEMPLATE
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


def test_a_refused_push_of_the_update_branch_names_the_next_step(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = release
    remote = add_origin(target)
    git(target, "switch", "-qc", "feature/work")
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + "\nnew release\n")
    select_release(source, monkeypatch)
    assert update_runner.apply_update(target) == 0
    hook = remote / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert (
        f"The push of {update_runner.UPDATE_BRANCH} failed; the lines above give the "
        "reason. When the pre-push check refused it, the new release found a fault in "
        f"this project: fix it on the branch {update_runner.UPDATE_BRANCH} in its own "
        "worktree, as its own commit, then run "
        f"`{update_runner.UPDATE_COMMAND}` again."
    ) in printed
    assert "returned non-zero exit status" not in printed


NEW_RULE = '\nROLE_TOOLS["shared"]["deployment"] = ("trivy",)\n'
RULE_TEXT = "deploy: the deployment check must run `trivy`; this command does not name it: python3 -c print('DEPLOY')"
LOAD = (
    "import sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[1])\n"
    "from gate_config import load_groups\nload_groups(Path(sys.argv[2]))\n"
)


def loading_project(target: Path, deployment: list[str]) -> str:
    remove_application(target)
    gates = target / GATES_FILE
    config = json.loads(gates.read_text())
    config["shared"] = [
        {"name": "actionlint", "role": "workflows", "command": ["actionlint"]},
        {"name": "zizmor", "role": "ci-security", "command": ["zizmor", "."]},
        {"name": "deploy", "role": "deployment", "command": deployment},
    ]
    gates.write_text(json.dumps(config))
    before = commit(target, "gates the installed release loads")
    assert gate_config.load_groups(target)
    return before


def release_with_new_load_rule(source: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    tools = source / ".hooks/tool_setup.py"
    tools.write_text(tools.read_text() + NEW_RULE)
    revision = commit(source, "require the deployment tool")
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=revision))
    return revision


def installed_load(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-I", "-c", LOAD, str(target / ".hooks"), str(target)],
        capture_output=True,
        text=True,
        check=False,
    )


def refused_tip(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, str]:
    source, target, old = release
    loading_project(target, ["python3", "-c", "print('DEPLOY')"])
    remote = add_origin(target)
    release_with_new_load_rule(source, monkeypatch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    return target, remote, old


def drop_push_hook(root: Path) -> None:
    git_path = git(
        root, "rev-parse", "--path-format=absolute", "--git-path", "hooks/pre-push"
    )
    Path(git_path).unlink(missing_ok=True)


class GreenGh(FakeGh):
    def __call__(self, root: Path, *args: str) -> str:
        shown = super().__call__(root, *args)
        for pull in self.pulls:
            pull["statusCheckRollup"] = [
                {"context": "deploy-preview", "state": "SUCCESS"}
            ]
        return shown


def test_update_pr_requests_no_merge_for_an_unfixed_tip_with_only_an_unrelated_green_check(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, remote, _ = refused_tip(release, monkeypatch)
    fresh = target.parent / "fresh"
    git(target.parent, "clone", "-q", str(remote), str(fresh))
    git(fresh, "config", "user.name", "Fixture")
    git(fresh, "config", "user.email", "fixture@example.invalid")
    fake = GreenGh()
    monkeypatch.setattr(update_pr, "gh", fake)
    monkeypatch.setattr("shipping.gh", fake)

    with suppress(ValueError):
        update_pr.publish(fresh)
    drop_push_hook(fresh)
    with suppress(ValueError):
        update_pr.publish(fresh)
    capsys.readouterr()
    assert "pr merge" not in fake.verbs()
    assert git(remote, "branch", "--list", update_runner.UPDATE_BRANCH) == ""


def test_an_update_whose_release_cannot_load_the_gates_file_leaves_the_update_branch_and_the_checkout_untouched(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, _, old = refused_tip(release, monkeypatch)
    before = git(target, "rev-parse", "HEAD")

    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "Hard Eng update failed" not in result
    branch = f"refs/heads/{update_runner.UPDATE_BRANCH}"
    marker = json.loads(git(target, "show", f"{branch}:{update.SOURCE_FILE}"))
    assert marker["revision"] != old
    assert git(target, "rev-parse", "HEAD") == before
    assert git(target, "status", "--short") == ""
    assert json.loads((target / update.SOURCE_FILE).read_text())["revision"] == old
    assert installed_load(target).returncode == 0


def test_update_pr_refuses_to_push_an_update_tip_its_release_cannot_load(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, remote, _ = refused_tip(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()

    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert RULE_TEXT in printed
    assert f"Fix its checks on branch {update_runner.UPDATE_BRANCH}" in printed
    assert git(remote, "branch", "--list", update_runner.UPDATE_BRANCH) == ""


def test_a_fix_on_the_update_branch_is_pushed_and_merged_by_update_pr(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, remote, _ = refused_tip(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    drop_push_hook(target)
    branch = update_runner.UPDATE_BRANCH
    work = target.parent / "fix"
    git(target, "worktree", "add", "-q", str(work), branch)
    gates = work / GATES_FILE
    config = json.loads(gates.read_text())
    config["shared"][-1]["command"] = ["trivy", "config", "."]
    gates.write_text(json.dumps(config))
    git(work, "commit", "-qam", "meet the new rule")
    fake = GreenGh()
    monkeypatch.setattr(update_pr, "gh", fake)
    monkeypatch.setattr("shipping.gh", fake)

    assert update_pr.publish(work) == 0
    tip = git(work, "rev-parse", branch)
    assert git(remote, "rev-parse", branch) == tip
    merges = [call for call in fake.calls if call[:2] == ("pr", "merge")]
    assert len(merges) == 1
    assert merges[0][-1] == tip


def test_a_refusal_for_a_missing_product_file_does_not_send_the_reader_to_the_gates_file(
    release: tuple[Path, Path, str],
) -> None:
    _, target, _ = release
    assert update_pr.load_refusal(target) is None
    (target / "PRODUCT.md").unlink()

    refusal = update_pr.load_refusal(target)
    assert refusal is not None and "PRODUCT.md is required" in refusal
    assert "hard-eng.gates.json" not in refusal


def test_an_update_whose_release_loads_the_gates_file_still_lands(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    loading_project(target, ["trivy", "config", "."])
    add_origin(target)
    revision = release_with_new_load_rule(source, monkeypatch)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())

    assert update_runner.apply_update(target) == 0
    assert revision in (target / update_runner.RESULT_FILE).read_text()
    branch = f"refs/heads/{update_runner.UPDATE_BRANCH}"
    marker = json.loads(git(target, "show", f"{branch}:{update.SOURCE_FILE}"))
    assert marker["revision"] == revision

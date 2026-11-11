import contextlib
import json
import os
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path
from unittest.mock import Mock

import change_size
import pytest
import update
import update_runner
from conftest import commit, git
from plans import validate_plans
from test_plans import edit, new_file, released_branch, sized_branch
from test_updates import select_release


@pytest.mark.parametrize(
    ("change", "verdict"),
    [
        (partial(edit, name="a.py", count=2), (True, "1 file, 4 changed lines")),
        (new_file, (False, "it adds, deletes or renames the file new.py")),
    ],
    ids=["small", "new"],
)
def test_sandbox_placeholder_does_not_add_a_file(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[Path], object],
    verdict: tuple[bool, str],
) -> None:
    sized_branch(repository)
    change(repository)
    # Inside the sandbox .bashrc is /dev/null bound over an empty file, so Git lists it.
    os.mkfifo(repository / ".bashrc")
    listed = change_size._git_output

    def sandbox_listing(root: Path, *arguments: str) -> str:
        found = listed(root, *arguments)
        return found + "\0.bashrc" if arguments[0] == "ls-files" else found

    monkeypatch.setattr(change_size, "_git_output", sandbox_listing)
    assert change_size.size_verdict(repository) == verdict


def test_the_debt_file_does_not_count_toward_the_size(repository: Path) -> None:
    sized_branch(repository)
    git(repository, "switch", "-q", "main")
    debt_file = repository / "hard-eng.debt.json"
    debt_file.write_text("".join(f"line {n}\n" for n in range(30)))
    commit(repository, "debt")
    git(repository, "switch", "-q", "work")
    git(repository, "rebase", "-q", "main")
    edit(repository, "a.py", 2)
    edit(repository, "hard-eng.debt.json", 25)
    assert change_size.size_verdict(repository) == (True, "1 file, 4 changed lines")


def test_small_change_needs_no_plan(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    validate_plans(repository)
    assert "Size: small (1 file, 4 changed lines); no plan needed." in (
        capsys.readouterr().out
    )


def test_documentation_only_change_needs_no_plan(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / "notes.md").write_text("notes\n" * 50)
    validate_plans(repository)
    assert "Size: small (documentation only)" in capsys.readouterr().out


def test_new_documentation_file_beside_a_small_fix_stays_small(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    (repository / "docs").mkdir()
    (repository / "docs/decision.md").write_text("why\n" * 80)
    validate_plans(repository)
    assert "Size: small (1 file, 4 changed lines)" in capsys.readouterr().out


def test_new_documentation_file_beside_a_new_code_file_is_big(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    new_file(repository)
    (repository / "docs").mkdir()
    (repository / "docs/decision.md").write_text("why\n")
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)
    assert "Size: big, because it adds" in capsys.readouterr().out


def test_a_check_with_no_base_passes_a_first_install_that_the_base_lacks(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng.py").write_text("x = 1\n")
    commit(repository, "Install Hard Eng")
    validate_plans(repository)
    assert "Size:" not in capsys.readouterr().out
    new_file(repository)
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)


def test_a_check_with_no_base_passes_a_clean_branch_with_no_branch_point(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repository, "branch", "-M", "trunk")
    validate_plans(repository)
    assert "Size:" not in capsys.readouterr().out


def merging(repository: Path, other: str, linked: bool, conflict: bool) -> Path:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    commit(repository, "task edit")
    git(repository, "switch", "-q", "main")
    (repository / "base_new.py").write_text("x = 1\n")
    if conflict:
        lines = (repository / "a.py").read_text().splitlines()
        (repository / "a.py").write_text("\n".join(["base line", *lines[1:]]) + "\n")
    commit(repository, "base moves")
    git(repository, "switch", "-qc", "other", "main~1")
    (repository / "other.py").write_text("y = 1\n")
    commit(repository, "other work")
    git(repository, "switch", "-q", "work")
    root = repository
    if linked:
        git(repository, "branch", "work2", "work")
        git(repository, "switch", "-q", "main")
        root = repository.parent / "linked"
        git(repository, "worktree", "add", "-q", str(root), "work2")
    subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", other],
        cwd=root,
        capture_output=True,
        check=False,
    )
    assert git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    assert bool(git(root, "ls-files", "--unmerged")) == conflict
    return root


@pytest.mark.parametrize("conflict", [True, False], ids=["conflict", "staged"])
@pytest.mark.parametrize("linked", [False, True], ids=["main checkout", "linked"])
def test_a_merge_of_the_base_in_progress_does_not_count_the_base_changes(
    repository: Path, linked: bool, conflict: bool
) -> None:
    root = merging(repository, "main", linked, conflict)
    small, reason = change_size.size_verdict(root)
    assert small, reason
    assert reason.startswith("1 file, ")


@pytest.mark.parametrize("linked", [False, True], ids=["main checkout", "linked"])
def test_a_merge_of_another_branch_in_progress_counts_its_files(
    repository: Path, linked: bool
) -> None:
    root = merging(repository, "other", linked, False)
    assert change_size.size_verdict(root) == (
        False,
        "it adds, deletes or renames the file other.py",
    )


def test_a_branch_that_installs_hard_eng_names_the_install_as_the_reason(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / ".agents").mkdir()
    (repository / ".agents/biome.json").write_text("{}\n")
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text("{}\n")
    commit(repository, "Install Hard Eng")
    assert change_size.size_verdict(repository) == (
        False,
        "this branch installs Hard Eng",
    )
    assert not change_size.plan_not_needed(repository)
    assert "Size: big, because this branch installs Hard Eng; a plan is needed." in (
        capsys.readouterr().out
    )


def test_a_merge_of_an_older_branch_into_a_rebased_task_counts_only_its_files(
    repository: Path,
) -> None:
    sized_branch(repository)
    git(repository, "switch", "-qc", "older", "main")
    (repository / "other.py").write_text("y = 1\n")
    commit(repository, "older work")
    git(repository, "switch", "-q", "main")
    (repository / "base_new.py").write_text("x = 1\n")
    commit(repository, "base moves")
    git(repository, "switch", "-q", "work")
    edit(repository, "a.py", 2)
    commit(repository, "task edit")
    git(repository, "rebase", "-q", "main")
    git(repository, "merge", "--no-commit", "--no-ff", "older")
    assert change_size.size_verdict(repository) == (
        False,
        "it adds, deletes or renames the file other.py",
    )


def test_a_markdown_edit_beside_committed_code_keeps_the_ready_plan_refusal(
    repository: Path, completed_plan: str
) -> None:
    released_branch(repository)
    (repository / "PLAN.md").write_text(
        completed_plan.replace("Status: Complete", "Status: Ready")
    )
    commit(repository, "plan")
    edit(repository, "a.py", 2)
    commit(repository, "code")
    (repository / "README.md").write_text("notes\n")
    with pytest.raises(ValueError, match="plan is Ready; this check requires Complete"):
        validate_plans(repository)


def process_starts(monkeypatch: pytest.MonkeyPatch, root: Path) -> int:
    import plans

    spy = Mock(side_effect=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", spy)
    with contextlib.suppress(ValueError):
        plans.validate_plans(root, "main")
    return spy.call_count


@pytest.mark.parametrize(
    ("state", "expected"),
    [("committed", 23), ("uncommitted", 23), ("update", 31)],
)
def test_the_plan_rule_starts_no_more_processes_than_before_for_an_installed_path(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    state: str,
    expected: int,
) -> None:
    if state == "update":
        target = draft_plan_beside_an_update(release, monkeypatch)
    else:
        target = release[1]
        git(target, "update-ref", "refs/heads/main", "HEAD")
        git(target, "switch", "-qc", "feature/work")
        (target / "AGENTS.md").write_text("rules\n")
        if state == "committed":
            commit(target, "rules")
    assert process_starts(monkeypatch, target) == expected


def started(spy: Mock) -> list[str]:
    return [call.args[0][1] for call in spy.call_args_list]


def test_a_change_with_no_installed_path_starts_no_update_lookup(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text(
        '{"revision": "' + "a" * 40 + '"}\n'
    )
    sized_branch(repository)
    edit(repository, "a.py", 2)
    spy = Mock(side_effect=subprocess.check_output)
    monkeypatch.setattr(subprocess, "check_output", spy)
    assert change_size.size_verdict(repository) == (True, "1 file, 4 changed lines")
    assert not {"status", "show", "log"}.intersection(started(spy))
    spy.reset_mock()
    edit(repository, "a.py", 1)
    (repository / "AGENTS.md").write_text("rules\n")
    change_size.size_verdict(repository)
    lookups = [name for name in started(spy) if name in {"status", "show", "log"}]
    assert lookups == ["show", "log"]


def test_a_change_with_no_removed_plan_starts_no_moved_plan_lookup(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sized_branch(repository)
    (repository / "PLAN.md").write_text("# Plan\n")
    spy = Mock(side_effect=subprocess.check_output)
    monkeypatch.setattr(subprocess, "check_output", spy)
    assert change_size.moved_plans(repository, "main", {"a.py", "PLAN.md"}) == set()
    assert started(spy) == []


def two_commits_then_edit(root: Path) -> None:
    edit(root, "a.py", 6)
    commit(root, "first half")
    edit(root, "b.py", 6)


def deleted_file(root: Path) -> None:
    (root / "d.py").unlink()


def binary_file(root: Path) -> None:
    (root / "image.bin").write_bytes(b"\x00\x03\x04")


def removed_test_line(root: Path) -> None:
    edit(root, "tests/test_a.py", 1)


def four_files(root: Path) -> None:
    for name in ("a.py", "b.py", "c.py", "d.py"):
        edit(root, name, 1)


BIG_CHANGES = [
    (partial(edit, name="a.py", count=11), "it changes 22 lines"),
    (four_files, "it changes 4 files"),
    (new_file, "it adds, deletes or renames the file new.py"),
    (deleted_file, "it adds, deletes or renames the file d.py"),
    (binary_file, "it changes the binary file image.bin"),
    (
        partial(edit, name="uv.lock", count=1),
        "it changes uv.lock, which always needs a plan",
    ),
    (
        partial(edit, name=".github/workflows/ci.yml", count=1),
        "it changes .github/workflows/ci.yml, which always needs a plan",
    ),
    (removed_test_line, "it removes lines from the test file tests/test_a.py"),
    (two_commits_then_edit, "it changes 24 lines"),
]


@pytest.mark.parametrize(("change", "reason"), BIG_CHANGES)
def test_big_change_still_needs_a_plan_and_names_why(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    change: Callable[[Path], object],
    reason: str,
) -> None:
    sized_branch(repository)
    change(repository)
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)
    assert f"Size: big, because {reason}" in capsys.readouterr().out


def test_unknown_branch_point_is_big(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    git(repository, "branch", "-m", "work", "other")
    git(repository, "branch", "-D", "main")
    edit(repository, "a.py", 1)
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)
    assert "the branch point with the default branch cannot be found" in (
        capsys.readouterr().out
    )


def test_a_plan_stage_check_passes_a_small_change_with_no_plan(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    assert validate_plans(repository, stage="Complete") == "Complete"
    assert "Size: small (1 file, 4 changed lines)" in capsys.readouterr().out
    new_file(repository)
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository, stage="Complete")


def test_a_draft_plan_with_code_edits_names_the_ready_step(
    repository: Path, completed_plan: str
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    draft = completed_plan.replace("Status: Complete", "Status: Draft")
    (repository / "PLAN.md").write_text(draft)
    with pytest.raises(
        ValueError, match="plan is Draft; this check requires Complete"
    ) as error:
        validate_plans(repository)
    assert (
        "get approval for the plan and set its Status to Ready before you build"
        in str(error.value)
    )
    with pytest.raises(ValueError, match="requires Ready") as explicit:
        validate_plans(repository, stage="Ready")
    assert "set its Status to Ready" not in str(explicit.value)


def test_update_branch_needs_no_plan_for_files_the_update_wrote(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue 299: setup's own edits outside the scaffold made update PRs demand a plan."""
    source, target, _ = release
    ignore = target / ".gitignore"
    current = ignore.read_text()
    ignore.write_text("".join(current.splitlines(keepends=True)[:-1]))
    retired = {"mcpServers": {"context-mode": {"command": "context-mode"}}}
    (target / ".mcp.json").write_text(json.dumps(retired))
    commit(target, "ignore list and MCP file from an older release")
    git(target, "update-ref", "refs/heads/main", "HEAD")
    git(target, "checkout", "-qb", update_runner.UPDATE_BRANCH)
    select_release(source, monkeypatch)
    update.update(target)
    assert ignore.read_text() == current
    assert not (target / ".mcp.json").exists()
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    small, reason = change_size.size_verdict(target)
    assert small, reason
    (target / "package.json").write_text('{"private":true,"type":"module"}')
    commit(target, "project edit beside the update")
    assert change_size.size_verdict(target) == (
        False,
        "it changes package.json, which always needs a plan",
    )
    (target / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    commit(target, "binary file beside the update")
    assert change_size.size_verdict(target) == (
        False,
        "it adds, deletes or renames the file logo.png",
    )


def draft_plan_beside_an_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> Path:
    source, target, _ = release
    (target / "PLAN.md").write_text("# Later work\n\nStatus: Draft\n")
    commit(target, "draft plan for later work")
    git(target, "update-ref", "refs/heads/main", "HEAD")
    git(target, "checkout", "-qb", update_runner.UPDATE_BRANCH)
    select_release(source, monkeypatch)
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    return target


def test_update_branch_check_skips_an_unrelated_draft_plan(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project's open Draft plan blocked its Hard Eng update PR check."""
    import plans

    target = draft_plan_beside_an_update(release, monkeypatch)
    assert plans.validate_plans(target, "main") == "Complete"
    (target / "app.py").write_text("print('project work')\n")
    commit(target, "project work beside the update")
    with pytest.raises(ValueError, match="PLAN.md: plan needs"):
        plans.validate_plans(target, "main")


def test_the_update_only_rule_asks_no_proof_of_a_tree_that_is_not_clean(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import plans

    target = draft_plan_beside_an_update(release, monkeypatch)
    proof = Mock(return_value=True)
    monkeypatch.setattr(update, "verified_revision", proof)
    assert plans.validate_plans(target, "main") == "Complete"
    proof.assert_called()
    proof.reset_mock()
    (target / "app.py").write_text("print('more work')\n")
    with pytest.raises(ValueError, match="PLAN.md: plan needs"):
        plans.validate_plans(target, "main")
    proof.assert_not_called()

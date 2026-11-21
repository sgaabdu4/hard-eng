"""A step plan names its parent plan; the parent stays open until the last step."""

import re
from pathlib import Path

import pytest
from conftest import commit, ready_plan
from plans import plan_files, validate_plans
from test_plans import edit, released_branch
from test_ui_quality import UNCHANGED_NOTE, VISIBLE_FILE, ci_problem

PARENT = "features/effort/PLAN.md"
CHILD = "features/effort/step-1/PLAN.md"


def write(root: Path, name: str, text: str) -> None:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text)


def with_parent(plan: str, parent: str = PARENT) -> str:
    return re.sub(r"(?m)^(Status: .*)$", rf"\1\nParent: {parent}", plan, count=1)


def step_branch(root: Path, completed_plan: str, parent: str) -> None:
    write(root, PARENT, parent)
    commit(root, "parent plan")
    write(root, CHILD, with_parent(completed_plan))


def check(root: Path) -> str:
    return validate_plans(root, base="HEAD", stage="Complete")


def test_a_complete_step_passes_while_its_parent_is_ready(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    assert check(repository) == "Complete"


def test_a_step_whose_parent_is_missing_fails(
    repository: Path, completed_plan: str
) -> None:
    write(repository, CHILD, with_parent(completed_plan))
    with pytest.raises(ValueError, match=f"{CHILD}: Parent {PARENT} is not a plan"):
        check(repository)


def test_a_step_whose_parent_is_a_draft_fails(
    repository: Path, completed_plan: str
) -> None:
    draft = completed_plan.replace("Status: Complete", "Status: Draft")
    step_branch(repository, completed_plan, draft)
    with pytest.raises(ValueError, match="Parent .* is Draft; it must be Ready"):
        check(repository)


def test_a_parent_in_another_letter_case_is_found(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    write(repository, CHILD, with_parent(completed_plan, "features/effort/plan.md"))
    assert check(repository) == "Complete"


def test_a_step_outside_its_parents_folder_fails(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    (repository / CHILD).unlink()
    write(repository, "features/other/PLAN.md", with_parent(completed_plan))
    with pytest.raises(ValueError, match="must sit above"):
        check(repository)


def test_a_parent_that_has_a_parent_fails(
    repository: Path, completed_plan: str
) -> None:
    nested = with_parent(ready_plan(completed_plan), "features/effort/step-1/PLAN.md")
    step_branch(repository, completed_plan, nested)
    with pytest.raises(ValueError, match="has its own Parent"):
        check(repository)


def test_two_parent_lines_fail(repository: Path, completed_plan: str) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    write(
        repository,
        CHILD,
        with_parent(with_parent(completed_plan), "features/effort/PLAN.md"),
    )
    with pytest.raises(ValueError, match="one 'Parent:' line"):
        check(repository)


def test_a_parent_cannot_close_while_a_step_is_open(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    (repository / CHILD).write_text(with_parent(ready_plan(completed_plan)))
    commit(repository, "open step")
    write(repository, PARENT, completed_plan)
    with pytest.raises(ValueError, match="step .*step-1/PLAN.md is Ready"):
        check(repository)
    (repository / CHILD).write_text(with_parent(completed_plan))
    assert check(repository) == "Complete"


def test_separate_sibling_plans_without_a_parent_line_keep_passing(
    repository: Path, completed_plan: str
) -> None:
    for name in ("effort-s1-first", "effort-s2-second"):
        write(repository, f"features/{name}/PLAN.md", completed_plan)
    assert len(plan_files(repository)) == 2
    assert check(repository) == "Complete"


def test_the_first_step_pr_adds_a_ready_parent_beside_its_complete_step(
    repository: Path, completed_plan: str
) -> None:
    released_branch(repository)
    write(repository, PARENT, ready_plan(completed_plan))
    write(repository, CHILD, with_parent(completed_plan))
    edit(repository, "a.py", 2)
    commit(repository, "first step")
    assert validate_plans(repository, stage="Complete") == "Complete"


def test_a_ready_plan_with_no_step_still_blocks_a_complete_check(
    repository: Path, completed_plan: str
) -> None:
    released_branch(repository)
    write(repository, PARENT, ready_plan(completed_plan))
    write(repository, "features/other/PLAN.md", completed_plan)
    edit(repository, "a.py", 2)
    commit(repository, "work")
    with pytest.raises(ValueError, match="plan is Ready; this check requires Complete"):
        validate_plans(repository, stage="Complete")


def test_a_ready_parent_does_not_ride_along_with_a_draft_step(
    repository: Path, completed_plan: str
) -> None:
    released_branch(repository)
    write(repository, PARENT, ready_plan(completed_plan))
    write(
        repository,
        CHILD,
        with_parent(completed_plan.replace("Status: Complete", "Status: Draft")),
    )
    write(repository, "features/other/PLAN.md", completed_plan)
    edit(repository, "a.py", 2)
    commit(repository, "work")
    with pytest.raises(ValueError, match="plan is Ready; this check requires Complete"):
        validate_plans(repository, stage="Complete")


def test_a_parent_with_an_unknown_status_fails(
    repository: Path, completed_plan: str
) -> None:
    step_branch(
        repository,
        completed_plan,
        completed_plan.replace("Status: Complete", "Status: In progress"),
    )
    with pytest.raises(ValueError, match="Parent .* must be Ready or Complete"):
        check(repository)


def test_a_step_cannot_be_open_while_its_parent_is_complete(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, completed_plan)
    write(repository, CHILD, with_parent(ready_plan(completed_plan)))
    with pytest.raises(ValueError, match="Parent .* is Complete; .* open"):
        validate_plans(repository, base="HEAD", stage="Ready")


def pr_problem(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, plans: dict[str, str]):
    from test_pr_text import _VALID

    files: list[dict[str, object]] = [VISIBLE_FILE]
    files += [{"filename": name, "status": "added"} for name in plans]
    body = f"{_VALID}\n{UNCHANGED_NOTE}"
    return ci_problem(tmp_path, monkeypatch, body, files, plans)


MOCK = "N/A — the redesign mock sits in the parent plan"
UNCHANGED = "N/A — unchanged: ![Before](a.png) ![After](a.png) — Home screen"


def pair(parent_line: str = f"Parent: {PARENT}") -> dict[str, str]:
    reference = "\n\n## ux_reference\n{}\n\n## Verification\n"
    return {
        PARENT: "# Effort\nStatus: Ready" + reference.format(MOCK),
        CHILD: f"# Step\nStatus: Complete\n{parent_line}" + reference.format(UNCHANGED),
    }


def test_the_pr_text_check_skips_a_parent_plan_beside_its_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert pr_problem(tmp_path / "a", monkeypatch, pair()) is None
    assert (
        pr_problem(
            tmp_path / "b", monkeypatch, pair("Parent: ./features/Effort/plan.md")
        )
        is None
    )
    unlinked = pair("Parent: features/other/PLAN.md")
    assert "ux_reference says N/A" in str(
        pr_problem(tmp_path / "c", monkeypatch, unlinked)
    )


def test_a_document_that_names_a_plan_as_its_parent_does_not_skip_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plans = pair()
    plans["docs/rollout/PLAN.md"] = plans.pop(CHILD)
    assert "ux_reference says N/A" in str(
        pr_problem(tmp_path / "a", monkeypatch, plans)
    )


def test_a_parent_path_with_a_dot_segment_is_found(
    repository: Path, completed_plan: str
) -> None:
    step_branch(repository, completed_plan, ready_plan(completed_plan))
    write(repository, CHILD, with_parent(completed_plan, "./features/effort/PLAN.md"))
    assert check(repository) == "Complete"

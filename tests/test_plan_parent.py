"""A step plan names its parent plan; the parent stays open until the last step."""

import re
from pathlib import Path

import pytest
from conftest import commit, ready_plan
from plans import plan_files, validate_plans
from test_plans import edit, released_branch

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

"""An old Complete plan that only repoints test names, or only changes its layout, is no plan of the change."""

from pathlib import Path

from change_size import unedited_plans
from conftest import commit, init
from gate_config import JsonValue
from local_ui_proof import _active_plan_texts
from ship_scope import plan_in

NAME = "features/old/PLAN.md"
ROW = "- [x] Observe the configured command exit → N/A — fixture plan has no product test."
TESTS = "def test_old():\n    pass\n\ndef test_kept():\n    pass\n"


def repository(tmp_path: Path, completed_plan: str) -> tuple[Path, str, str]:
    root = tmp_path / "project"
    init(root)
    (root / "README.md").write_text("base\n")
    (root / "tests").mkdir()
    (root / "tests/test_one.py").write_text(TESTS)
    old = completed_plan.replace(
        ROW,
        "- [x] Observe the configured command exit → `tests/test_one.py::test_old`.",
    )
    (root / NAME).parent.mkdir(parents=True)
    (root / NAME).write_text(old)
    return root, old, commit(root, "base")


def test_a_repointed_or_reformatted_old_complete_plan_is_no_active_plan(
    tmp_path: Path, completed_plan: str
) -> None:
    """The repointed plan passes today's rules, so it was judged as a plan of the change; a layout change was already skipped."""
    root, old, base = repository(tmp_path, completed_plan)
    (root / NAME).write_text(old.replace("test_old", "test_kept"))
    assert unedited_plans(root, base, {NAME}) == {NAME}
    assert _active_plan_texts(root, base, {NAME}) == []
    (root / NAME).write_text(old.replace("\n## ", "\n\n## "))
    assert _active_plan_texts(root, base, {NAME}) == []


def test_a_really_edited_old_complete_plan_is_still_an_active_plan(
    tmp_path: Path, completed_plan: str
) -> None:
    root, old, base = repository(tmp_path, completed_plan)
    edited = old.replace("test_old", "test_kept").replace(
        "Verify fixture command exits", "Verify the fixture command and its exit"
    )
    (root / NAME).write_text(edited)
    assert unedited_plans(root, base, {NAME}) == set()
    assert _active_plan_texts(root, base, {NAME}) == [edited]


def files_of(*items: tuple[str, str]) -> list[dict[str, JsonValue]]:
    return [{"filename": name, "status": status} for name, status in items]


def test_a_pr_that_only_repoints_or_reformats_an_old_plan_needs_no_plan_flag(
    tmp_path: Path, completed_plan: str
) -> None:
    """`ship --stage delivered` named such a plan as the PR's plan; it asks for --plan only for a plan the PR added or edited."""
    root, old, base = repository(tmp_path, completed_plan)
    (root / NAME).write_text(old.replace("test_old", "test_kept"))
    repointed = commit(root, "repoint")
    changed = files_of((NAME, "modified"))
    assert plan_in(root, base, repointed, changed) is None
    (root / NAME).write_text(old.replace("\n## ", "\n\n## "))
    reformatted = commit(root, "format")
    assert plan_in(root, base, reformatted, changed) is None


def test_a_pr_that_adds_or_edits_a_plan_still_names_it(
    tmp_path: Path, completed_plan: str
) -> None:
    root, old, base = repository(tmp_path, completed_plan)
    (root / NAME).write_text(old.replace("Verify fixture", "Verify a changed fixture"))
    edited = commit(root, "edit")
    assert plan_in(root, base, edited, files_of((NAME, "modified"))) == NAME
    assert plan_in(root, base, edited, files_of((NAME, "added"))) == NAME
    assert plan_in(root, base, "0" * 40, files_of((NAME, "modified"))) == NAME

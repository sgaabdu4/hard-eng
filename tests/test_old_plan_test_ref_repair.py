"""Repairing only acceptance test refs in an old Complete plan keeps it exempt from newer plan fields."""

import re
from pathlib import Path

import change_size
import pytest
from conftest import commit, git
from plans import validate_plan
from test_planning_handoffs import (
    OLD_NAME,
    dated,
    finished_before_the_update,
    plan_from_before_newer_fields,
)


def old_plan_with_test_ref(
    tmp_path: Path,
    completed_plan: str,
    test_body: str = "def test_old():\n    pass\n",
    extra_row: str = "",
) -> tuple[Path, str, str]:
    root = tmp_path / "project"
    row = "- [x] Observe the configured command exit → `tests/test_one.py::test_old`."
    if extra_row:
        row = f"{row}\n{extra_row}"
    old = plan_from_before_newer_fields(
        completed_plan.replace(
            "- [x] Observe the configured command exit → N/A — fixture plan has no product test.",
            row,
        )
    )
    finished_before_the_update(root, old)
    (root / "tests").mkdir(parents=True)
    (root / "tests/test_one.py").write_text(test_body)
    dated(root, 2, "add test")
    return root, old, git(root, "rev-parse", "HEAD")


def test_repairing_only_acceptance_test_refs_in_an_old_complete_plan_counts_as_unchanged(
    tmp_path: Path, completed_plan: str
) -> None:
    root, old, base = old_plan_with_test_ref(
        tmp_path,
        completed_plan,
        "def test_old():\n    pass\n\ndef test_kept():\n    pass\n",
    )

    repaired_only = old.replace(
        "`tests/test_one.py::test_old`",
        "`tests/test_one.py::test_kept`",
    ).replace("\n## Baseline + execution", "\n\n## Baseline + execution")
    (root / OLD_NAME).write_text(repaired_only)

    assert "Same cause" in str(
        pytest.raises(ValueError, validate_plan, root / OLD_NAME).value
    )
    assert change_size.judged_stage(root, base, None) == "Draft"

    (root / "tests/test_one.py").write_text(
        "def test_new_one():\n    pass\n\ndef test_new_two():\n    pass\n"
    )
    repaired = old.replace(
        "`tests/test_one.py::test_old`",
        "`tests/test_one.py::test_new_one` and `tests/test_one.py::test_new_two`",
    )
    (root / OLD_NAME).write_text(repaired)
    with pytest.raises(ValueError, match="applicable PLAN"):
        change_size.judged_stage(root, base, None)

    mine = root / "features/mine/PLAN.md"
    mine.parent.mkdir(parents=True)
    mine.write_text(completed_plan)
    assert change_size.judged_stage(root, base, None) == "Complete"


@pytest.mark.parametrize(
    ("case", "replacement", "expected"),
    [
        (
            "missing test",
            "`tests/test_one.py::test_missing`",
            "acceptance names tests that do not exist",
        ),
        (
            "committed missing test",
            "`tests/test_one.py::test_missing`",
            "acceptance names tests that do not exist",
        ),
        (
            "reused stale ref on another row",
            "`tests/test_one.py::test_stale`",
            "acceptance names tests that do not exist",
        ),
        (
            "unchanged dot-slash deleted test",
            "`tests/test_one.py::test_kept`",
            "acceptance names tests that do not exist",
        ),
        ("weakened to N/A", "N/A — skipped now", "Same cause"),
        ("outcome changed", None, "Same cause"),
    ],
)
def test_old_plan_test_ref_repair_still_refuses_missing_tests_na_or_word_edits(
    tmp_path: Path,
    completed_plan: str,
    case: str,
    replacement: str | None,
    expected: str,
) -> None:
    extra = (
        "- [x] Second outcome → `./tests/test_two.py::test_removed`."
        if case == "unchanged dot-slash deleted test"
        else "- [x] Second outcome → `tests/test_one.py::test_stale`."
        if case == "reused stale ref on another row"
        else ""
    )
    root, old, base = old_plan_with_test_ref(
        tmp_path,
        completed_plan,
        "def test_old():\n    pass\n\ndef test_kept():\n    pass\n",
        extra_row=extra,
    )
    if case == "unchanged dot-slash deleted test":
        (root / "tests/test_two.py").write_text("def test_removed():\n    pass\n")
        dated(root, 3, "add second test")
        base = git(root, "rev-parse", "HEAD")

    if case == "outcome changed":
        edited = old.replace("Observe the configured", "Observe any configured")
    else:
        assert replacement is not None
        edited = old.replace("`tests/test_one.py::test_old`", replacement)
    (root / OLD_NAME).write_text(edited)
    if case in {"committed missing test", "reused stale ref on another row"}:
        dated(root, 4, "commit bad repair")
    elif case == "unchanged dot-slash deleted test":
        (root / "tests/test_two.py").write_text("def test_other():\n    pass\n")

    with pytest.raises(ValueError, match=expected):
        change_size.judged_stage(root, base, None)


def test_retargeting_a_directory_symlink_still_checks_referenced_tests(
    tmp_path: Path, completed_plan: str
) -> None:
    root, old, _ = old_plan_with_test_ref(
        tmp_path,
        completed_plan,
        "def test_old():\n    pass\n\ndef test_kept():\n    pass\n",
        extra_row="- [x] Second outcome → `./tests/current/test_two.py::test_removed`.",
    )
    (root / "tests/v1").mkdir()
    (root / "tests/v1/test_two.py").write_text("def test_removed():\n    pass\n")
    (root / "tests/v2").mkdir()
    (root / "tests/v2/test_two.py").write_text("def test_other():\n    pass\n")
    (root / "tests/current").symlink_to("v1")
    dated(root, 3, "add symlinked test dir")
    base = git(root, "rev-parse", "HEAD")

    (root / "tests/current").unlink()
    (root / "tests/current").symlink_to("v2")
    (root / OLD_NAME).write_text(
        old.replace("`tests/test_one.py::test_old`", "`tests/test_one.py::test_kept`")
    )

    with pytest.raises(ValueError, match="acceptance names tests that do not exist"):
        change_size.judged_stage(root, base, None)


KEPT_AND_OLD = "def test_old():\n    pass\n\ndef test_kept():\n    pass\n"
PROOFLESS = "- [x] An old line with no named proof."
OLD_TARGET = "`tests/test_one.py::test_old`"
KEPT_TARGET = "`tests/test_one.py::test_kept`"


@pytest.mark.parametrize("beside", [False, True], ids=["alone", "beside_my_plan"])
@pytest.mark.parametrize("stage", [None, "Ready", "Complete"])
def test_repointing_an_old_plan_with_a_proofless_row_gives_the_untouched_result(
    tmp_path: Path, completed_plan: str, stage: str | None, beside: bool
) -> None:
    root, old, base = old_plan_with_test_ref(
        tmp_path, completed_plan, KEPT_AND_OLD, extra_row=PROOFLESS
    )
    if beside:
        mine = root / "features/mine/PLAN.md"
        mine.parent.mkdir(parents=True)
        mine.write_text(completed_plan)
    untouched = change_size.judged_stage(root, base, stage)

    (root / OLD_NAME).write_text(old.replace(OLD_TARGET, KEPT_TARGET))

    assert change_size.judged_stage(root, base, stage) == untouched


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("text before the arrow", "Same cause"),
        ("added checkbox with a target", "Same cause"),
        ("added checkbox with no proof", "Same cause"),
        ("removed checkbox", "Same cause"),
        ("changed text outside the checkboxes", "Same cause"),
        ("target set to N/A", "Same cause"),
        ("target to a missing test", "acceptance names tests that do not exist"),
    ],
)
def test_a_repoint_with_another_change_is_still_judged_as_a_changed_plan(
    tmp_path: Path, completed_plan: str, case: str, expected: str
) -> None:
    root, old, base = old_plan_with_test_ref(
        tmp_path, completed_plan, KEPT_AND_OLD, extra_row=PROOFLESS
    )
    edited = old.replace(OLD_TARGET, KEPT_TARGET)
    if case == "text before the arrow":
        edited = edited.replace("Observe the configured", "Observe any configured")
    if case == "added checkbox with a target":
        edited = edited.replace(
            PROOFLESS, f"{PROOFLESS}\n- [x] A new outcome → {KEPT_TARGET}."
        )
    if case == "added checkbox with no proof":
        edited = edited.replace(PROOFLESS, f"{PROOFLESS}\n- [x] Another old line.")
    if case == "removed checkbox":
        edited = edited.replace(f"\n{PROOFLESS}", "")
    if case == "changed text outside the checkboxes":
        edited = edited.replace("Verify fixture command", "Verify the fixture command")
    if case == "target set to N/A":
        edited = old.replace(OLD_TARGET, "N/A — gone")
    if case == "target to a missing test":
        edited = old.replace(OLD_TARGET, "`tests/test_one.py::test_missing`")
    (root / OLD_NAME).write_text(edited)

    with pytest.raises(ValueError, match=expected):
        change_size.judged_stage(root, base, None)


@pytest.mark.parametrize("form", ["no ux_reference section", "a bare N/A"])
def test_repointing_an_old_plan_of_an_old_form_gives_the_untouched_result(
    tmp_path: Path, completed_plan: str, form: str
) -> None:
    root, old, base = old_plan_with_test_ref(tmp_path, completed_plan, KEPT_AND_OLD)
    old = (
        re.sub(r"(?ms)^## ux_reference\n.*?(?=^## )", "", old)
        if form == "no ux_reference section"
        else old.replace("Verify fixture", "Notes: N/A\nVerify fixture", 1)
    )
    (root / OLD_NAME).write_text(old)
    base = commit(root, "old form")
    mine = root / "features/mine/PLAN.md"
    mine.parent.mkdir(parents=True)
    mine.write_text(completed_plan)
    untouched = change_size.judged_stage(root, base, None)

    (root / OLD_NAME).write_text(old.replace(OLD_TARGET, KEPT_TARGET))

    assert change_size.judged_stage(root, base, None) == untouched

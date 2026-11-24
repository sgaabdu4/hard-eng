"""The CI PR text check judges the screen files by the plan that names them, as the local check does."""

from pathlib import Path

import look
import pytest
from test_ui_quality import (
    _UI_BODY,
    NO_UX,
    REAL_UX,
    VISIBLE_FILE,
    ci_problem,
    sample_record,
)


def two_plan_ci_problem(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, repair_owner: str = ""
) -> str | None:
    from test_pr_text import _VALID

    body = f"{_UI_BODY}\n{look.block_text(sample_record(1))}\n{_VALID}"
    files: list[dict[str, object]] = [
        VISIBLE_FILE,
        {"filename": "features/a/PLAN.md", "status": "modified"},
        {"filename": "features/b/PLAN.md", "status": "modified"},
    ]
    screen_plan = (
        f"## ux_reference\n{REAL_UX}\n\n## Verification\nOwners: src/App.tsx\n"
    )
    repair_plan = f"## ux_reference\n{NO_UX}\n\n## Verification\n{repair_owner}\n"
    return ci_problem(
        tmp_path / "ci",
        monkeypatch,
        body,
        files,
        {"features/a/PLAN.md": screen_plan, "features/b/PLAN.md": repair_plan},
    )


def test_ci_judges_the_screen_files_by_the_plan_that_owns_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert two_plan_ci_problem(tmp_path, monkeypatch) is None


def test_ci_still_refuses_an_na_plan_that_owns_a_screen_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem = two_plan_ci_problem(tmp_path, monkeypatch, "Owners: src/App.tsx")
    assert "ux_reference says N/A" in str(problem)

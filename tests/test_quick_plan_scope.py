"""The quick check judges every plan that the branch changed, also when no base branch is known."""

from pathlib import Path

import change_size
import pytest
from conftest import commit, git, init, plan_document

BARE = "- Declined: a second copy; N/A here\n"


def committed_bad_plan(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("# Fixture\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "start")
    git(root, "switch", "-qc", "trunk")
    git(root, "branch", "-qD", "master")
    (root / "PLAN.md").write_text(
        plan_document().replace("Blockers: None\n", f"Blockers: None\n{BARE}")
    )
    commit(root, "add a plan whose N/A has no reason")
    return root


@pytest.mark.parametrize("base", [None, "HEAD"])
def test_the_quick_check_judges_a_committed_plan_when_no_base_branch_is_known(
    tmp_path: Path, base: str | None
) -> None:
    root = committed_bad_plan(tmp_path)
    with pytest.raises(ValueError, match="N/A needs an inline reason"):
        change_size.judged_stage(root, base, None)


def test_a_base_that_resolves_keeps_the_check_off_untouched_plans(
    tmp_path: Path,
) -> None:
    root = committed_bad_plan(tmp_path)
    base = git(root, "rev-parse", "HEAD")
    (root / "features/new").mkdir(parents=True)
    (root / "features/new/PLAN.md").write_text(plan_document())
    commit(root, "add a plan that is fine")
    assert change_size.judged_stage(root, base, None) == "Complete"

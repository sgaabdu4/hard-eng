"""A formatter rewrite of an old plan keeps its text, so it is no change to judge; a real edit still is."""

from pathlib import Path

import local_ui_proof
import pytest
from change_size import plan_words
from conftest import commit, git
from test_local_ui_proof import clear_ci
from test_shipping import _fixture

FIXTURES = Path(__file__).parent / "fixtures/plan-format"
SENTENCE = "Verify fixture command exits; no product release."


def old_plan_branch(tmp_path: Path, rewrite: str) -> Path:
    """A base with an old Complete plan that says N/A for its screen, and a branch that edits a screen and rewrites that plan."""
    root = _fixture(tmp_path, ui_paths=["src/**"]).root
    (root / ".git/info/exclude").write_text(".hard-eng/\n")
    (root / "src").mkdir()
    (root / "src/App.tsx").write_text("export const App = () => <p>Old</p>;\n")
    commit(root, "base")
    git(root, "branch", "-f", "main", "HEAD")
    git(root, "update-ref", "refs/remotes/origin/main", git(root, "rev-parse", "main"))
    (root / "src/App.tsx").write_text("export const App = () => <p>New</p>;\n")
    plan = root / "PLAN.md"
    assert SENTENCE in plan.read_text()
    plan.write_text(plan.read_text().replace(SENTENCE, rewrite))
    commit(root, "edit a screen and rewrite the old plan")
    return root


def test_a_formatter_rewrite_of_an_old_complete_plan_does_not_reopen_its_ux_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    wrapped = SENTENCE.replace("command exits", "command\n  exits")
    root = old_plan_branch(tmp_path, wrapped)
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert "ux_reference" not in (problem or "")


def test_a_real_text_change_to_an_old_complete_plan_still_reopens_its_ux_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    clear_ci(monkeypatch)
    root = old_plan_branch(tmp_path, SENTENCE.replace("no product", "one product"))
    problem = local_ui_proof.local_ui_proof_problem(root, "origin/main")
    assert problem is not None and "ux_reference says N/A" in problem


def test_the_words_of_a_plan_survive_what_a_real_formatter_rewrites() -> None:
    before = (FIXTURES / "before.md").read_text()
    after = (FIXTURES / "after.md").read_text()
    assert before != after
    assert plan_words(before) == plan_words(after)


@pytest.mark.parametrize(
    ("kept", "changed"),
    [
        ("- [x] A late invoice adds the fee", "- [ ] A late invoice adds the fee"),
        ("Status: Complete", "Status: Ready"),
        ("`tests/test_total.py::test_fee_once`", "`tests/test_total.py::test_feeonce`"),
        ("the snake_case word", "the snake case word"),
        ("1. First step", "2. First step"),
        ("| late | fee |", "| late | no fee |"),
    ],
)
def test_a_change_of_checkbox_status_name_or_cell_is_still_a_text_change(
    kept: str, changed: str
) -> None:
    assert plan_words(kept) != plan_words(changed)

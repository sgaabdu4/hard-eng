"""Decision records name the paths they govern and are not left stale by a change."""

from pathlib import Path

import pytest
from conftest import commit, init
from plans import validate_decisions


def adr_root(tmp_path: Path, status: str = "Accepted", applies: str = "") -> Path:
    init(tmp_path / "adr")
    root = tmp_path / "adr"
    (root / "src/pay").mkdir(parents=True)
    (root / "src/pay/a.py").write_text("x = 1\n")
    (root / "docs/adr").mkdir(parents=True)
    (root / "docs/adr/0001-pay.md").write_text(
        f"# 0001 — Pay\n\nStatus: {status}\n{applies}\n## Decision\nUse it.\n"
    )
    commit(root, "baseline")
    return root


def test_changed_decision_without_applies_to_line_fails(tmp_path: Path) -> None:
    root = adr_root(tmp_path)
    validate_decisions(root, "HEAD")
    (root / "docs/adr/0002-new.md").write_text("# 0002\n\nStatus: Accepted\n")
    with pytest.raises(ValueError, match="0002-new.md needs an 'Applies to:'"):
        validate_decisions(root, "HEAD")


def test_changed_decision_with_applies_to_line_passes(tmp_path: Path) -> None:
    root = adr_root(tmp_path, applies="Applies to: `src/pay/`, `api/`\n")
    (root / "docs/adr/0001-pay.md").write_text(
        "# 0001\n\nStatus: Accepted\nApplies to: `src/pay/`\n"
    )
    validate_decisions(root, "HEAD")


def test_deleting_the_last_file_under_a_prefix_fails(tmp_path: Path) -> None:
    root = adr_root(tmp_path, applies="Applies to: `src/pay/`\n")
    (root / "src/pay/b.py").write_text("y = 1\n")
    (root / "src/pay/a.py").unlink()
    validate_decisions(root, "HEAD")
    (root / "src/pay/b.py").unlink()
    with pytest.raises(ValueError, match="last file under src/pay/"):
        validate_decisions(root, "HEAD")


def test_note_stale_before_the_change_does_not_fail(tmp_path: Path) -> None:
    root = adr_root(tmp_path, applies="Applies to: `gone/`\n")
    (root / "README.md").write_text("change\n")
    validate_decisions(root, "HEAD")

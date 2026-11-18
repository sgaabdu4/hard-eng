"""The brownfield canary does what a real adoption does with the Ruff settings that Hard Eng refuses."""

from pathlib import Path

from conftest import git

import release_canary


def test_the_brownfield_refactor_deletes_a_ruff_ignore_list(tmp_path: Path) -> None:
    """A real project fixes the cause of a Ruff `ignore` or deletes the setting; the canary deletes it, and adopt records what the rule then finds."""
    git(tmp_path, "init", "-q")
    (tmp_path / "pkg.py").write_text("# TODO later\nvalue = 1\n")
    project = (
        '[tool.ruff]\nfix = true\nsrc = ["src"]\n\n[tool.ruff.lint]\nselect = [\n    "B",  # bugbear\n    "UP",  # pyupgrade\n]\n'
        'ignore = [\n    "UP038",  # keep isinstance tuple\n]\n\n'
        "[tool.ruff.lint.isort]\nforce-single-line = true\n"
    )
    (tmp_path / "pyproject.toml").write_text(project)
    git(tmp_path, "add", "pkg.py", "pyproject.toml")
    release_canary.refactor_for_strict_checks(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == (
        '[tool.ruff]\nsrc = ["src"]\n\n[tool.ruff.lint]\nextend-select = [\n    "B",  # bugbear\n    "UP",  # pyupgrade\n]\n\n'
        "[tool.ruff.lint.isort]\nforce-single-line = true\n"
    )

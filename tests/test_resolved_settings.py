"""The full check judges what Ruff prints as its settings, so the spelling of a setting does not matter."""

from pathlib import Path

import pytest
from conftest import commit, init
from gate_config import Gate, Group
from resolved_settings import validate_resolved

COMPLEXITY = [
    "uvx",
    "ruff@latest",
    "check",
    ".",
    "--select",
    "C901,PLR0912,PLR0915",
    "--config",
    "lint.mccabe.max-complexity = 10",
    "--config",
    "lint.pylint.max-branches = 12",
    "--config",
    "lint.pylint.max-statements = 50",
]


def groups(command: list[str], role: str) -> list[Group]:
    gate: Gate = {"name": role, "role": role, "command": command}
    return [{"path": ".", "checks": [gate]}]


def project(tmp_path: Path, settings: str) -> Path:
    root = tmp_path / "repo"
    tmp_path.mkdir(parents=True, exist_ok=True)
    init(root)
    (root / "pyproject.toml").write_text(settings)
    (root / "main.py").write_text("x = 1\n")
    (root / "src").mkdir()
    (root / "src/a.py").write_text("x = 1\n")
    commit(root, "baseline")
    return root


@pytest.mark.parametrize(
    ("settings", "reason"),
    [
        ('[tool.ruff.lint]\nselect = ["E"]\n', r"lacks \d+ of Ruff's default rules"),
        ('[tool.ruff]\nextend-exclude = ["src"]\n', r"does not check src/a\.py"),
        ('[tool.ruff.lint]\nper-file-ignores = {"a.py" = ["F"]}\n', "per_file_ignores"),
        ('[tool.ruff.lint]\nexclude = ["src"]\n', "linter.exclude is not empty"),
        ('[tool.ruff]\nexclude = ["src"]\n', r"does not check src/a\.py"),
    ],
)
def test_a_lint_gate_whose_resolved_settings_narrow_the_rules_is_refused(
    tmp_path: Path, settings: str, reason: str
) -> None:
    """HE-NO-SWITCH-OFF: Ruff's printed settings show a dropped rule or a skipped file, in any spelling."""
    root = project(tmp_path, settings)
    with pytest.raises(ValueError, match=rf"HE-NO-SWITCH-OFF[\s\S]*{reason}"):
        validate_resolved(
            root, groups(["uvx", "ruff@latest", "check", "."], "lint"), 900
        )


@pytest.mark.parametrize(
    "settings",
    [
        "",
        '[tool.ruff.lint]\nselect = ["ALL"]\n',
        '[tool.ruff.lint]\nextend-select = ["I"]\n',
        "[tool.ruff.lint]\nextend-select = []\n",
    ],
)
def test_a_lint_gate_that_keeps_the_default_rules_passes(
    tmp_path: Path, settings: str
) -> None:
    root = project(tmp_path, settings)
    validate_resolved(root, groups(["uvx", "ruff@latest", "check", "."], "lint"), 900)


def test_a_complexity_gate_keeps_the_limits_of_the_template(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a raised limit in the settings file shows in the printed settings unless the gate sets it."""
    root = project(tmp_path, "[tool.ruff.lint.mccabe]\nmax-complexity = 99\n")
    open_gate = ["uvx", "ruff@latest", "check", ".", "--select", "C901,PLR0912,PLR0915"]
    with pytest.raises(ValueError, match=r"max_complexity is 99, above the limit 10"):
        validate_resolved(root, groups(open_gate, "complexity"), 900)
    validate_resolved(root, groups(COMPLEXITY, "complexity"), 900)


def test_a_complexity_gate_that_drops_a_rule_is_refused(tmp_path: Path) -> None:
    root = project(tmp_path, "")
    narrow = [*COMPLEXITY[:4], "--select", "C901", *COMPLEXITY[6:]]
    with pytest.raises(
        ValueError, match=r"lacks 2 of the complexity rules: PLR0912, PLR0915"
    ):
        validate_resolved(root, groups(narrow, "complexity"), 900)

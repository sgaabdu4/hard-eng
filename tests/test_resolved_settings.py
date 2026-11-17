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
        (
            '[tool.ruff.lint]\nexclude = ["src"]\n',
            "linter.exclude differs from Ruff's default",
        ),
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
    with pytest.raises(
        ValueError, match=r"linter.mccabe.max_complexity is \['99'\], above the limit"
    ):
        validate_resolved(root, groups(open_gate, "complexity"), 900)
    validate_resolved(root, groups(COMPLEXITY, "complexity"), 900)


def test_a_complexity_gate_that_drops_a_rule_is_refused(tmp_path: Path) -> None:
    root = project(tmp_path, "")
    narrow = [*COMPLEXITY[:4], "--select", "C901", *COMPLEXITY[6:]]
    with pytest.raises(
        ValueError, match=r"lacks 2 of the complexity rules: PLR0912, PLR0915"
    ):
        validate_resolved(root, groups(narrow, "complexity"), 900)


def refused(tmp_path: Path, settings: str, reason: str) -> None:
    root = project(tmp_path, settings)
    with pytest.raises(ValueError, match=rf"HE-NO-SWITCH-OFF[\s\S]*{reason}"):
        validate_resolved(
            root, groups(["uvx", "ruff@latest", "check", "."], "lint"), 900
        )


FINDING_CHANGING = [
    ("[tool.ruff]\nfix = true\n", "fix"),
    ("[tool.ruff]\nfix-only = true\n", "fix_only"),
    ('[tool.ruff]\nextension = {"py" = "ipynb"}\n', "linter.extension"),
    (
        '[tool.ruff.lint]\nselect = ["ALL"]\n[tool.ruff]\nline-length = 1000\n',
        "line_length",
    ),
    ('[tool.ruff.lint]\ntask-tags = ["NEVER"]\n', "task_tags"),
    ("[tool.ruff.lint.flake8-copyright]\nmin-file-size = 100000\n", "min_file_size"),
    (
        '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.12"\n[tool.ruff]\ntarget-version = "py37"\n',
        "target version",
    ),
]


@pytest.mark.parametrize(("settings", "reason"), FINDING_CHANGING)
def test_a_setting_that_changes_which_findings_ruff_reports_is_not_free(
    tmp_path: Path, settings: str, reason: str
) -> None:
    """HE-NO-SWITCH-OFF: a key is free only when it cannot change the findings or the exit code."""
    refused(tmp_path, settings, reason)


@pytest.mark.parametrize(
    "settings",
    [
        '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.12"\n[tool.ruff]\ntarget-version = "py312"\n',
        '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.10"\n[tool.ruff]\ntarget-version = "py313"\n',
        "[tool.ruff]\nline-length = 88\n",
        '[tool.ruff.lint]\nselect = ["ALL"]\n[tool.ruff]\nline-length = 60\n',
        "[tool.ruff]\nline-length = 120\n",
    ],
)
def test_a_setting_that_can_only_add_findings_passes(
    tmp_path: Path, settings: str
) -> None:
    root = project(tmp_path, settings)
    validate_resolved(root, groups(["uvx", "ruff@latest", "check", "."], "lint"), 900)


ANNOTATIONS = [
    "uvx",
    "ruff@latest",
    "check",
    ".",
    "--select",
    "ANN,TID251,RUF017,ASYNC210",
    "--config",
    "lint.flake8-annotations.ignore-fully-untyped = false",
]


@pytest.mark.parametrize(
    "select", ["ANN001", "ANN", "ANN,TID251,RUF017", "E", "ANN,RUF017,ASYNC210"]
)
def test_an_annotations_gate_that_drops_a_rule_of_its_set_is_refused(
    tmp_path: Path, select: str
) -> None:
    """HE-NO-SWITCH-OFF: the annotations gate keeps every rule of the template set, as lint keeps Ruff's defaults."""
    root = project(tmp_path, "")
    command = [*ANNOTATIONS[:5], select, *ANNOTATIONS[6:]]
    with pytest.raises(ValueError, match=r"lacks \d+ of the annotation rules"):
        validate_resolved(root, groups(command, "annotations"), 900)


@pytest.mark.parametrize("select", ["ANN,TID251,RUF017,ASYNC210", "ALL"])
def test_an_annotations_gate_that_keeps_its_set_passes(
    tmp_path: Path, select: str
) -> None:
    root = project(tmp_path, "")
    command = [*ANNOTATIONS[:5], select, *ANNOTATIONS[6:]]
    validate_resolved(root, groups(command, "annotations"), 900)

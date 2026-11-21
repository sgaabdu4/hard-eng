"""The full check judges the settings of each Ruff config that governs a file of the gate, with the gate's own launcher."""

from pathlib import Path

import pytest
import resolved_settings
from gate_config import Gate, Group, validate_gate
from resolved_settings import validate_resolved
from test_strict_refusals import project

LINT = ["ruff", "check", "."]
PYPROJECT = '[project]\nname = "x"\nversion = "0"\nrequires-python = ">=3.10"\n'


def groups(*paths: str, command: list[str] = LINT) -> list[Group]:
    return [
        {
            "path": path,
            "language": "python",
            "checks": [{"name": "lint", "role": "lint", "command": command}],
        }
        for path in paths
    ]


def test_a_config_with_only_a_target_version_cannot_hide_the_root_settings(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: ruff reads the closest config for each file, and the judge reads each one that governs a file."""
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT
            + '[tool.ruff]\nextend-exclude = [".agents", ".hooks"]\n[tool.ruff.lint]\nselect = ["E4"]\n',
            ".github/scripts/ruff.toml": 'target-version = "py310"\n',
            ".github/scripts/release.py": "x = 1\n",
            "src/pkg/a.py": "import os\n",
        },
    )
    with pytest.raises(ValueError, match=r"lacks \d+ of Ruff's default rules"):
        validate_resolved(root, groups("."), 900)


def test_a_child_group_config_cannot_hide_the_parent_settings(tmp_path: Path) -> None:
    root = project(
        tmp_path,
        {
            "backend/pyproject.toml": PYPROJECT + '[tool.ruff.lint]\nselect = ["E4"]\n',
            "backend/zz/a.py": "import os\n",
            "backend/libs/core/pyproject.toml": PYPROJECT
            + "[tool.ruff]\nline-length = 88\n",
            "backend/libs/core/b.py": "x = 1\n",
        },
    )
    every = groups("backend", "backend/libs/core")
    with pytest.raises(ValueError, match=r"lacks \d+ of Ruff's default rules"):
        validate_resolved(root, every[:1], 900, every)


def test_the_judge_runs_the_launcher_the_gate_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The settings come from the same tool the runner runs, not from `uvx ruff@latest`."""
    root = project(tmp_path, {"pyproject.toml": PYPROJECT, "a.py": "x = 1\n"})
    seen: list[list[str]] = []

    def printed(prefix: list[str], *_rest: object) -> str:
        seen.append(prefix)
        raise ValueError("stop")

    monkeypatch.setattr(resolved_settings, "printed", printed)
    command = ["uvx", "ruff@0.14.0", "check", "."]
    with pytest.raises(ValueError, match="stop"):
        validate_resolved(root, groups(".", command=command), 900)
    assert seen[0] == ["uvx", "ruff@0.14.0"]


def test_a_project_script_that_shadows_ruff_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `uv run ruff` runs the project's own `ruff` script when it has one, so the gate would run another tool."""
    (tmp_path / "pyproject.toml").write_text(
        PYPROJECT + '[project.scripts]\nruff = "fake:main"\n'
    )
    gate: Gate = {
        "name": "lint",
        "role": "lint",
        "command": ["uv", "run", "--no-sync", "ruff", "check", "."],
    }
    with pytest.raises(ValueError, match="shadows"):
        validate_gate(gate, tmp_path, set())


NOTEBOOK = (
    '{"cells": [{"cell_type": "code", "execution_count": null, "metadata": {}, '
    '"outputs": [], "source": ["import os\\n", "import sys\\n"]}], '
    '"metadata": {}, "nbformat": 4, "nbformat_minor": 5}\n'
)


def test_a_config_that_governs_only_a_notebook_is_judged(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: a root config that narrows the rules governs a notebook that no .py file shares it with."""
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT + '[tool.ruff.lint]\nselect = ["E4"]\n',
            "src/ruff.toml": 'target-version = "py310"\n',
            "src/x.py": "x = 1\n",
            "analysis.ipynb": NOTEBOOK,
        },
    )
    with pytest.raises(ValueError, match=r"lacks \d+ of Ruff's default rules"):
        validate_resolved(root, groups("."), 900)


def test_a_nested_config_with_a_higher_target_version_is_judged(
    tmp_path: Path,
) -> None:
    """HE-NO-SWITCH-OFF: a nested config that sets only a target version is harmless only at the requires-python minimum."""
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT,
            "src/ruff.toml": 'target-version = "py313"\n',
            "src/x.py": "x = 1\n",
        },
    )
    with pytest.raises(ValueError, match=r"target version 3\.13 is above"):
        validate_resolved(root, groups("."), 900)

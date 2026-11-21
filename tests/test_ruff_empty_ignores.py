"""A Ruff ignore setting that ignores nothing switches nothing off."""

from pathlib import Path

import pytest
from test_strict_refusals import project
from whole_project import validate_whole_project


@pytest.mark.parametrize(
    "setting",
    [
        "ignore = []",
        "extend-ignore = []",
        "per-file-ignores = {}",
        "extend-per-file-ignores = {}",
    ],
)
def test_an_empty_ignore_setting_passes(tmp_path: Path, setting: str) -> None:
    text = f'[tool.ruff.lint]\nselect = ["E401"]\n{setting}\n'
    validate_whole_project(project(tmp_path, {"pyproject.toml": text}))

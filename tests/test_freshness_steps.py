"""The steps that the freshness gate prints must run word for word."""

import json
import shlex
from pathlib import Path

import pytest
from test_freshness import check, moves, poetry_dry_run

SPLIT_LOCK = (
    '[[package]]\nname = "pytest"\nversion = "8.4.2"\n'
    "markers = 'python_version == \"3.9\"'\n\n"
    '[[package]]\nname = "pytest"\nversion = "10.0.0"\n'
    "markers = 'python_version >= \"3.10\"'\n\n"
    '[[package]]\nname = "pyyaml"\nversion = "6.0.1"\n'
    "markers = 'python_version == \"3.9\"'\n\n"
    '[[package]]\nname = "pyyaml"\nversion = "6.0.3"\n'
    "markers = 'python_version >= \"3.10\"'\n"
)


def row(name: str, current: str, latest: str) -> str:
    return json.dumps([{"name": name, "version": current, "latest_version": latest}])


def added_entries(step: str) -> list[str]:
    command = step.split("`")[1]
    return shlex.split(command.partition("uvx poetry add ")[2])


def test_the_poetry_step_is_the_add_its_dry_run_proved(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nrequires-python = ">=3.9"\n'
        '[dependency-groups]\ndev = ["pytest~=7.2"]\n'
    )
    log = poetry_dry_run(
        tmp_path, monkeypatch, "  - Installing pytest (9.2.0)\n", status=0
    )
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(tmp_path, "poetry", row("pytest", "7.4.4", "9.2.0"))
    asked = log.read_text().split(" age=")[0].split()
    assert added_entries(str(failure.value)) == asked[asked.index("--group") :]
    assert added_entries(str(failure.value)) == ["--group", "dev", "pytest>=7.4.4"]


def test_a_split_lock_floors_each_entry_at_its_oldest_locked_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[dependency-groups]\ndev = ["pytest>=8"]\n'
    )
    (tmp_path / "poetry.lock").write_text(SPLIT_LOCK)
    log = poetry_dry_run(tmp_path, monkeypatch, moves(("pytest", "10.0.0", "10.1.0")))
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(tmp_path, "poetry", row("pytest", "10.0.0", "10.1.0"))
    assert "pytest>=8.4.2 age=" in log.read_text()
    assert added_entries(str(failure.value)) == ["--group", "dev", "pytest>=8.4.2"]


def test_a_capitalised_name_finds_its_entry_on_a_split_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "pyproject.toml").write_text('[dependency-groups]\ndev = ["PyYAML"]\n')
    (tmp_path / "poetry.lock").write_text(SPLIT_LOCK)
    log = poetry_dry_run(tmp_path, monkeypatch, moves(("PyYAML", "6.0.3", "6.0.4")))
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(tmp_path, "poetry", row("PyYAML", "6.0.3", "6.0.4"))
    assert "PyYAML>=6.0.1 age=" in log.read_text()
    assert added_entries(str(failure.value)) == ["--group", "dev", "PyYAML>=6.0.1"]

"""The steps that the freshness gate prints must run word for word."""

import json
import shlex
from pathlib import Path

import pytest
from test_freshness import PYPI, Registry, check, moves, poetry_dry_run

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


def uv_registry(*versions: tuple[str, str]) -> Registry:
    upload = [{"upload_time_iso_8601": "2020-01-01T00:00:00.000000Z"}]
    return Registry(
        {
            f"{PYPI}{name}/json": json.dumps({"releases": {latest: upload}})
            for name, latest in versions
        }
    )


def uv_failure(tmp_path: Path, tree: str, *versions: tuple[str, str]) -> str:
    with pytest.raises(ValueError, match="baseline repair") as failure:
        check(tmp_path, "uv", tree, uv_registry(*versions))
    return str(failure.value)


def test_the_uv_step_raises_each_entry_in_its_package_and_section(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "mcp"\n')
    tree = (
        "mcp-simple-tool v0.1.0\n"
        "├── anyio v4.14.2 (latest: v4.16.0)\n"
        "└── pytest v9.1.1 (group: dev) (latest: v9.2.0)\n"
        "mcp v1.0.0\n"
        "├── typer v0.17.4 (extra: cli) (latest: v0.29.1)\n"
        "├── coverage[toml] v7.13.0 (group: dev) (latest: v7.17.2)\n"
        "└── httpx v0.27.0 (latest: v0.28.1)\n"
    )
    step = uv_failure(
        tmp_path,
        tree,
        ("anyio", "4.16.0"),
        ("pytest", "9.2.0"),
        ("typer", "0.29.1"),
        ("coverage", "7.17.2"),
        ("httpx", "0.28.1"),
    )
    assert step.endswith(
        ". Run `uv add --package mcp-simple-tool 'anyio>=4.16.0'`, then "
        "`uv add --package mcp-simple-tool --group dev 'pytest>=9.2.0'`, then "
        "`uv add --package mcp --optional cli 'typer>=0.29.1'`, then "
        "`uv add --package mcp --group dev 'coverage[toml]>=7.17.2'`, then "
        "`uv add --package mcp 'httpx>=0.28.1'` in a separate PR first (baseline repair)."
    )


def test_a_dynamic_dependency_list_gets_the_hand_step(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "app"\n[tool.uv.workspace]\nmembers = ["packages/*"]\n'
    )
    library = tmp_path / "packages/lib"
    library.mkdir(parents=True)
    (library / "pyproject.toml").write_text(
        '[project]\nname = "lib"\ndynamic = ["version", "dependencies"]\n'
    )
    tree = (
        "app v0.1.0\n"
        "└── httpx v0.27.0 (latest: v0.28.1)\n"
        "lib v0.1.0\n"
        "├── jsonschema v4.25.1 (latest: v4.26.0)\n"
        "└── pytest v9.1.1 (group: dev) (latest: v9.2.0)\n"
    )
    step = uv_failure(
        tmp_path,
        tree,
        ("httpx", "0.28.1"),
        ("jsonschema", "4.26.0"),
        ("pytest", "9.2.0"),
    )
    assert "`uv add --package app 'httpx>=0.28.1'`, then " in step
    assert "`uv add --package lib --group dev 'pytest>=9.2.0'`" in step
    assert (
        "Raise jsonschema to 4.26.0 by hand where lib declares its dynamic "
        "dependencies, then run `uv lock`."
    ) in step
    assert "uv add --package lib 'jsonschema" not in step


def test_a_single_uv_project_gets_a_command_it_can_run_as_printed(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    step = uv_failure(
        tmp_path,
        "demo v0.1.0\n└── httpx v0.27.0 (latest: v0.28.1)\n",
        ("httpx", "0.28.1"),
    )
    assert "Run `uv add 'httpx>=0.28.1'` in a separate PR first" in step
    assert "<group>" not in step
    assert "--package" not in step

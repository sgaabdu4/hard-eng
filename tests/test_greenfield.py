"""Faults a fresh uv app met when Hard Eng was installed on it."""

import json
import os
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest
from conftest import git
from gate_config import Gate, Group, JsonObject, validate_required_checks
from plans import validate_plans
from python_setup import python_roots
from test_plans import edit, sized_branch
from test_setup import repository

PROJECT = '[project]\nname="fixture"\nversion="1"\n'


def uv_project(root: Path, project: str) -> None:
    repository(root)
    (root / "package.json").unlink()
    (root / "uv.lock").touch()
    (root / "pyproject.toml").write_text(project)


def test_missing_performance_suite_names_the_requirement(
    runner: ModuleType, capsys: pytest.CaptureFixture[str]
) -> None:
    """HE-PERFORMANCE-SUITE: a missing suite folder fails with the rule, not a test-runner usage error."""
    group: Group = {
        "path": ".",
        "language": "python",
        "sources": ["main.py"],
        "checks": [],
    }
    performance: Gate = {
        "name": "performance",
        "role": "performance",
        "command": [sys.executable, "-c", "raise SystemExit(4)", "tests/performance"],
        "report": {"type": "performance-junit", "path": "coverage/performance.xml"},
    }
    assert runner.run_gate(group, performance, 5, threading.Lock()) is True
    output = capsys.readouterr().out
    assert "HE-PERFORMANCE-SUITE: tests/performance does not exist" in output
    assert "performance_exception" in output


@pytest.mark.parametrize(("rescanned", "failed"), [(1, False), (0, True)])
def test_jscpd_passes_files_below_its_minimum_only_when_a_rescan_finds_them(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    rescanned: int,
    failed: bool,
) -> None:
    summary: JsonObject = {
        key: 0
        for key in (
            "clones",
            "duplicatedLines",
            "duplicatedTokens",
            "newClones",
            "newDuplicatedLines",
            "percentage",
            "percentageTokens",
        )
    }
    small: JsonObject = {
        "duplicates": [],
        "statistics": {
            "formats": {},
            "total": {**summary, "sources": 0, "lines": 0, "tokens": 0},
        },
    }
    scope: JsonObject = {**summary, "sources": rescanned, "lines": 3, "tokens": 9}
    full: JsonObject = {
        "duplicates": [{}],
        "statistics": {
            "formats": {"python": scope} if rescanned else {},
            "total": scope,
        },
    }
    tool = tmp_path / "bin/jscpd"
    tool.parent.mkdir()
    tool.write_text(
        f"#!{sys.executable}\nimport json, sys, pathlib\n"
        "arguments = sys.argv[1:]\n"
        "output = pathlib.Path(arguments[arguments.index('--output') + 1])\n"
        "output.mkdir(parents=True, exist_ok=True)\n"
        f"report = {full!r} if '--min-tokens' in arguments else {small!r}\n"
        "(output / 'jscpd-report.json').write_text(json.dumps(report))\n"
    )
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    (tmp_path / "main.py").write_text("print(1)\n")
    duplicates: Gate = {
        "name": "duplicates",
        "role": "duplicates",
        "command": [
            "jscpd",
            "main.py",
            "--format",
            "python",
            "--output",
            "coverage/jscpd",
        ],
        "report": {"type": "jscpd", "path": "coverage/jscpd/jscpd-report.json"},
    }
    group: Group = {
        "path": ".",
        "language": "python",
        "sources": ["main.py"],
        "checks": [duplicates],
    }
    assert runner.run_gate(group, duplicates, 30, threading.Lock()) is failed
    output = capsys.readouterr().out
    assert ("below jscpd's --min-tokens" in output) is not failed
    assert (
        json.loads((tmp_path / "coverage/jscpd/jscpd-report.json").read_text()) == small
    )


@pytest.mark.parametrize(
    ("source", "failed"),
    [('{ virtual = "." }', False), ('{ registry = "https://pypi.org/simple" }', True)],
)
def test_osv_needs_no_scan_when_uv_locks_no_third_party_package(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    source: str,
    failed: bool,
) -> None:
    tool = tmp_path / "bin/osv-scanner"
    tool.parent.mkdir()
    tool.write_text("#!/bin/sh\necho 'No package sources found' >&2\nexit 128\n")
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    (tmp_path / "uv.lock").write_text(
        f'version = 1\n\n[[package]]\nname = "app"\nversion = "1"\nsource = {source}\n'
    )
    vulnerabilities: Gate = {
        "name": "vulnerabilities",
        "role": "vulnerabilities",
        "command": [
            "osv-scanner",
            "scan",
            "source",
            "--lockfile=uv.lock",
            "--format=json",
            "--output-file=coverage/osv.json",
        ],
        "report": {"type": "osv", "path": "coverage/osv.json"},
    }
    group: Group = {
        "path": ".",
        "language": "python",
        "sources": ["app.py"],
        "checks": [vulnerabilities],
    }
    assert runner.run_gate(group, vulnerabilities, 30, threading.Lock()) is failed
    assert (
        "uv.lock locks no third-party package" in capsys.readouterr().out
    ) is not failed


def test_import_contract_waits_for_a_package_with_submodules(
    installer: ModuleType, tmp_path: Path
) -> None:
    uv_project(tmp_path, PROJECT)
    package = tmp_path / "example"
    package.mkdir()
    (package / "__init__.py").write_text("value = 1\n")
    group: Group = {"path": ".", "checks": [], "sources": ["example"]}
    assert python_roots(tmp_path, group) == []
    installer.install(tmp_path)
    assert "importlinter" not in (tmp_path / "pyproject.toml").read_text()
    (package / "calc.py").write_text("value = 2\n")
    assert python_roots(tmp_path, group) == ["example"]


@pytest.mark.parametrize("installed", [False, True])
def test_tests_import_root_modules_of_a_project_uv_does_not_install(
    installer: ModuleType, tmp_path: Path, installed: bool
) -> None:
    build = '[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    uv_project(tmp_path, PROJECT + (build if installed else ""))
    (tmp_path / "calc.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_calc.py").write_text(
        "from calc import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n"
    )
    installer.install(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    assert ('pythonpath = ["."]' in content) is not installed
    if not installed:
        pytest_script = Path(sys.executable).with_name("pytest")
        subprocess.run(
            [pytest_script, "-q", "-p", "no:cacheprovider"], cwd=tmp_path, check=True
        )
        installer.install(tmp_path)
        assert (tmp_path / "pyproject.toml").read_text() == content


def test_python_code_added_after_setup_must_join_the_checked_sources(
    installer: ModuleType, tmp_path: Path
) -> None:
    uv_project(tmp_path, PROJECT)
    (tmp_path / "main.py").write_text("value = 1\n")
    config = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, config)
    (tmp_path / "calc.py").write_text("value = 2\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_calc.py").write_text("value = 3\n")
    with pytest.raises(ValueError, match="outside its sources: calc.py;"):
        validate_required_checks(tmp_path, config)
    config["packages"][0]["sources"].append("calc.py")
    validate_required_checks(tmp_path, config)


@pytest.mark.parametrize("default", ["master", "trunk"])
def test_small_change_without_a_remote_compares_with_the_local_default_branch(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    default: str,
) -> None:
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(repository.parent / "no-global-config"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    sized_branch(repository)
    git(repository, "branch", "-m", "main", default)
    if default != "master":
        git(repository, "config", "init.defaultBranch", default)
    edit(repository, "a.py", 2)
    validate_plans(repository)
    assert "Size: small (1 file, 4 changed lines); no plan needed." in (
        capsys.readouterr().out
    )

"""Faults a fresh uv app met when Hard Eng was installed on it."""

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path
from types import ModuleType

import pytest
from conftest import git
from gate_config import (
    Gate,
    Group,
    JsonObject,
    validate_performance,
    validate_required_checks,
)
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


def test_the_performance_suite_error_names_its_package() -> None:
    group: Group = {"path": "services/api", "language": "python", "checks": []}
    with pytest.raises(ValueError, match="^services/api: HE-PERFORMANCE-SUITE"):
        validate_performance(group)


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


OSV_GATE: Gate = {
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
    vulnerabilities = OSV_GATE
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
    for listed in (["."], ["./main.py", "./calc.py"], ["./"]):
        config["packages"][0]["sources"] = listed
        validate_required_checks(tmp_path, config)


def test_the_missing_imports_message_gives_a_gate_and_a_block_that_pass(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    uv_project(tmp_path, PROJECT)
    (tmp_path / "main.py").write_text("value = 1\n")
    config = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, config)
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg/__init__.py").write_text("")
    (tmp_path / "pkg/mod.py").write_text("value = 1\n")
    group = config["packages"][0]
    group["sources"].append("pkg")
    with pytest.raises(
        ValueError, match="missing mandatory checks: imports"
    ) as refusal:
        validate_required_checks(tmp_path, config)
    message = str(refusal.value)
    gate: Gate = json.JSONDecoder().raw_decode(message[message.index("{") :])[0]
    group["checks"].append(gate)
    project = tmp_path / "pyproject.toml"
    project.write_text(
        project.read_text() + "\n" + message[message.index("[tool.importlinter]") :]
    )
    validate_required_checks(tmp_path, config)
    assert runner.run_gate(group, gate, 300, threading.Lock()) is False
    assert "PASS imports" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("manifest", "lock", "first", "added"),
    [
        ("package.json", "bun.lock", "src/index.ts", "server/main.ts"),
        ("pubspec.yaml", "pubspec.lock", "lib/main.dart", "tool/build.dart"),
    ],
)
def test_javascript_and_dart_code_added_after_setup_must_join_the_checked_sources(
    installer: ModuleType,
    tmp_path: Path,
    manifest: str,
    lock: str,
    first: str,
    added: str,
) -> None:
    repository(tmp_path)
    if manifest != "package.json":
        (tmp_path / "package.json").unlink()
        (tmp_path / "bun.lock").unlink()
        (tmp_path / manifest).write_text("name: app_fixture\n")
        (tmp_path / lock).touch()
    for name in (first, added):
        (tmp_path / name).parent.mkdir(exist_ok=True)
    (tmp_path / first).write_text("export const a = 1;\n")
    config = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, config)
    (tmp_path / added).write_text("export const b = 2;\n")
    folder = Path(added).parts[0]
    step = "`sources` list in hard-eng.gates.json. Tests must then cover its files"
    with pytest.raises(ValueError, match=f"outside its sources: {folder};.*{step}"):
        validate_required_checks(tmp_path, config)
    validate_required_checks(tmp_path, config, starting=True)
    config["packages"][0]["sources"].append(folder)
    validate_required_checks(tmp_path, config)
    top = Path(first).parts[0]
    for listed in (
        ["."],
        [f"./{top}", f"{folder}/"],
        [first, added],
        [top, added],
    ):
        config["packages"][0]["sources"] = listed
        validate_required_checks(tmp_path, config)
    (tmp_path / added).with_stem("other").write_text("export const c = 3;\n")
    with pytest.raises(ValueError, match=f"outside its sources: {folder};"):
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


def test_failed_vulnerability_scan_names_the_vulnerable_packages(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = {
        "results": [
            {
                "source": {"path": "uv.lock", "type": "lockfile"},
                "packages": [
                    {
                        "package": {"name": "lib", "version": "1", "ecosystem": "PyPI"},
                        "vulnerabilities": [{"id": "GHSA-0001"}, {"id": "GHSA-0002"}],
                    }
                ],
            }
        ]
    }
    tool = tmp_path / "bin/osv-scanner"
    tool.parent.mkdir()
    tool.write_text(
        "#!/bin/sh\nmkdir -p coverage\n"
        f"printf '%s' '{json.dumps(report)}' > coverage/osv.json\n"
        "echo 'Scanning dir .'\nexit 1\n"
    )
    tool.chmod(0o755)
    monkeypatch.setenv("PATH", f"{tool.parent}:{os.environ['PATH']}")
    (tmp_path / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "lib"\nversion = "1"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )
    gate = OSV_GATE
    group: Group = {"path": ".", "language": "python", "sources": [], "checks": [gate]}
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    assert runner.run_gate(group, gate, 30, threading.Lock()) is True
    assert "lib@1: GHSA-0001, GHSA-0002" in capsys.readouterr().out


def test_a_src_layout_package_that_imports_itself_passes_the_dependencies_gate(
    installer: ModuleType,
    runner: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    build = '[build-system]\nrequires = ["uv_build"]\nbuild-backend = "uv_build"\n'
    uv_project(tmp_path, PROJECT.replace("fixture", "mylib") + build)
    library = tmp_path / "src/mylib"
    library.mkdir(parents=True)
    (library / "__init__.py").write_text("def hello() -> str:\n    return 'hi'\n")
    (library / "cli.py").write_text("from mylib import hello\n\nvalue = hello()\n")
    installer.install(tmp_path)
    gates = tmp_path / "hard-eng.gates.json"
    older = json.loads(gates.read_text())
    command = next(
        check["command"]
        for check in older["packages"][0]["checks"]
        if check["role"] == "dependencies"
    )
    assert command[-2:] == ["--known-first-party", "mylib"]
    del command[-2:]
    gates.write_text(json.dumps(older))
    installer.install(tmp_path)
    group = json.loads(gates.read_text())["packages"][0]
    gate = next(check for check in group["checks"] if check["role"] == "dependencies")
    assert runner.run_gate(group, gate, 300, threading.Lock()) is False
    assert "PASS dependencies" in capsys.readouterr().out
    (tmp_path / "script.py").write_text("import yaml_missing_package\n")
    assert runner.run_gate(group, gate, 300, threading.Lock()) is True
    assert "DEP001 'yaml_missing_package'" in capsys.readouterr().out


def test_the_dart_sources_message_gives_a_step_that_passes(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "bun.lock").unlink()
    (tmp_path / "pubspec.yaml").write_text("name: app_fixture\n")
    (tmp_path / "pubspec.lock").touch()
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/main.dart").write_text("void main() {}\n")
    config = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, config)
    (tmp_path / "tool").mkdir()
    (tmp_path / "tool/build.dart").write_text("void build() {}\n")
    with pytest.raises(ValueError, match="outside its sources: tool;") as refusal:
        validate_required_checks(tmp_path, config)
    step = re.search(
        r"move each under lib/ \(for example (\w+) to (lib/\1)\)", str(refusal.value)
    )
    assert step is not None
    (tmp_path / step[1]).rename(tmp_path / step[2])
    validate_required_checks(tmp_path, config)

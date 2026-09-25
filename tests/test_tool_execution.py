"""Exercise native tool selection and execution through real subprocesses."""

import json
import os
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import ModuleType

import pytest
import tool_setup
import update
from conftest import commit, git
from gate_config import Gate, Group, validate_gate, validate_package_services
from project_setup import import_configuration

RECURSIVE_IMPORT_LINTER = """[importlinter]
root_package = example

[importlinter:contract:recursive-siblings]
name = No sibling dependency cycles
type = acyclic_siblings
ancestors =
    example
    example.**
depth = 0
"""
SPLIT_RECURSIVE_IMPORT_LINTER = """[importlinter]
root_package = example

[importlinter:contract:root-siblings]
name = No direct sibling dependency cycles
type = acyclic_siblings
ancestors =
    example
depth = 0

[importlinter:contract:descendant-siblings]
name = No descendant sibling dependency cycles
type = acyclic_siblings
ancestors =
    example.**
depth = 0
"""


def executable(directory: Path, name: str, output: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    binary = directory / name
    binary.write_text(f"#!/bin/sh\nprintf '%s\\n' '{output}' \"$@\"\n")
    binary.chmod(0o755)


def execute_provisioned_scanner(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    group: Group,
    scanner: str,
    package: str,
    *,
    stale_local: bool,
    expected_use_npm: bool,
) -> list[str]:
    managed = tmp_path / "managed"
    executable(managed, scanner, "managed")
    if stale_local:
        stale = tmp_path / "node_modules/.bin"
        executable(stale, scanner, "stale")
        monkeypatch.setenv("PATH", str(stale) + os.pathsep + os.environ["PATH"])

    def provision(
        _root: Path, batch: list[str], _timeout: float, *, use_npm: bool
    ) -> None:
        assert batch == [package]
        assert use_npm == expected_use_npm
        monkeypatch.setenv("PATH", str(managed) + os.pathsep + os.environ["PATH"])

    monkeypatch.setattr(tool_setup, "provision_batch", provision)
    tool_setup.provision_tools(tmp_path, [group], 30)
    command = runner.prepare_command(group, group["checks"][0], 30)
    return subprocess.check_output(command, cwd=tmp_path, text=True).splitlines()


def import_linter_project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "src/example"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("value = 1\n")
    project = tmp_path / "pyproject.toml"
    project.write_text('[project]\nname = "fixture"\nversion = "1"\n')
    (tmp_path / "uv.lock").touch()
    return project


@pytest.mark.parametrize("flag", [["--max-crap", "0"], ["--max-crap=0"]])
@pytest.mark.parametrize(
    "prefix",
    [
        ["fallow"],
        ["pnpm", "exec", "fallow"],
        ["pnpm", "dlx", "fallow@3.0.0"],
        ["pnpm", "dlx", "--package=fallow@latest", "--allow-build=fallow", "fallow"],
    ],
)
def test_gate_rejects_disabled_fallow_metric_before_execution(
    tmp_path: Path, flag: list[str], prefix: list[str]
) -> None:
    gate: Gate = {"name": "audit", "command": [*prefix, "audit", *flag]}
    with pytest.raises(ValueError, match="CRAP enforcement cannot be disabled"):
        validate_gate(gate, tmp_path, set())
    gate["command"] = [*prefix, "audit", "--max-crap", "30"]
    with pytest.raises(ValueError, match="require a native fallow report"):
        validate_gate(gate, tmp_path, set())
    gate["report"] = {"type": "fallow", "path": "audit.json"}
    with pytest.raises(ValueError, match="add --gate all"):
        validate_gate(gate, tmp_path, set())
    gate["command"] = [*prefix, "audit", "--gate=all", "--max-crap", "30"]
    validate_gate(gate, tmp_path, set())


def test_fallow_named_arguments_do_not_imply_tool_invocation(tmp_path: Path) -> None:
    validate_gate(
        {"name": "custom", "command": ["node", "check.mjs", "fallow", "audit"]},
        tmp_path,
        set(),
    )


@pytest.mark.parametrize(
    "prefix",
    [
        ["pnpm", "--dir", "child"],
        ["pnpm", "--dir=child"],
        ["pnpm", "-C", "child"],
        ["npm", "--prefix", "child"],
    ],
)
def test_package_directory_options_cannot_hide_suppression(
    tmp_path: Path, prefix: list[str]
) -> None:
    child = tmp_path / "child"
    child.mkdir()
    manifest = child / "package.json"
    manifest.write_text(json.dumps({"scripts": {"unit": "node --no-warnings --test"}}))
    gate: Gate = {"name": "unit", "command": [*prefix, "run", "unit"]}
    with pytest.raises(ValueError, match="suppress all Node warnings"):
        validate_gate(gate, tmp_path, set())
    manifest.write_text(json.dumps({"scripts": {"unit": "node --test"}}))
    validate_gate(gate, tmp_path, set())


def test_unresolved_package_selectors_fail_instead_of_skipping_validation(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="package selectors are not supported"):
        validate_gate(
            {"name": "unit", "command": ["pnpm", "--filter", "child", "run", "unit"]},
            tmp_path,
            set(),
        )


@pytest.mark.parametrize(
    "prefix",
    [
        "fallow",
        "pnpm exec fallow",
        "pnpm dlx fallow@3.0.0",
        "pnpm dlx --package=fallow@latest --allow-build=fallow fallow",
    ],
)
def test_existing_fallow_audit_must_be_the_enforced_gate(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prefix: str
) -> None:
    from project_setup import adapt_javascript

    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "check:fallow": f"{prefix} audit --format json --output-file reports/fallow.json"
                }
            }
        )
    )
    group: Group = {
        "path": ".",
        "language": "javascript",
        "checks": [
            {
                "name": "scan",
                "role": "dead-code-duplicates",
                "command": ["fallow"],
                "report": {"type": "fallow", "path": "coverage/fallow.json"},
            }
        ],
    }
    inherited = {"lockfiles", "vulnerabilities", "security"}
    with pytest.raises(ValueError, match="Wire check:fallow"):
        validate_package_services(tmp_path, group, {}, {}, inherited)
    adapt_javascript(tmp_path, group, "pnpm")
    assert len(group["checks"]) == 1
    assert group["checks"][0]["report"]["path"] == "reports/fallow.json"
    validate_package_services(tmp_path, group, {}, {}, inherited)
    assert execute_provisioned_scanner(
        runner,
        tmp_path,
        monkeypatch,
        group,
        "fallow",
        "npm:fallow@latest",
        stale_local=True,
        expected_use_npm=False,
    ) == [
        "managed",
        "audit",
        "--format",
        "json",
        "--output-file",
        "reports/fallow.json",
    ]


@pytest.mark.parametrize(
    "script",
    [
        "node --no-warnings --test",
        "NODE_NO_WARNINGS=1 node --test",
        "NODE_OPTIONS='--trace-warnings --no-warnings' node --test",
    ],
)
def test_gate_rejects_blanket_warnings_in_nested_package_scripts(
    tmp_path: Path, script: str
) -> None:
    manifest = tmp_path / "package.json"
    gate: Gate = {"name": "tests", "command": ["pnpm", "run", "verify"]}
    scripts = {"verify": "pnpm run unit", "unit": script}
    manifest.write_text(json.dumps({"scripts": scripts}))
    with pytest.raises(ValueError, match="suppress all Node warnings"):
        validate_gate(gate, tmp_path, set())
    scripts["unit"] = (
        "node --trace-warnings --disable-warning=ExperimentalWarning --test"
    )
    manifest.write_text(json.dumps({"scripts": scripts}))
    validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    "name,value", [("NODE_NO_WARNINGS", "1"), ("NODE_OPTIONS", "--no-warnings")]
)
def test_inherited_warning_suppression_blocks_before_command_execution(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    command = [sys.executable, "-c", "from pathlib import Path; Path('ran').touch()"]
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [{"name": "verify", "command": command}]})
    )
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError, match="suppress all Node warnings"):
        runner.check()
    assert not (tmp_path / "ran").exists()
    monkeypatch.delenv(name)
    assert runner.check() == 0
    assert (tmp_path / "ran").is_file()


@pytest.mark.parametrize("failure", ["", "exit", "unresolved"])
def test_native_tools_install_before_reading_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    calls: list[list[str]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        environment = kwargs["env"]
        assert isinstance(environment, dict)
        if "install" in command:
            assert environment["MISE_FETCH_REMOTE_VERSIONS_CACHE"] == "0s"
            warning = (
                "Failed to resolve tool version list" if failure == "unresolved" else ""
            )
            return subprocess.CompletedProcess(
                command, 7 if failure == "exit" else 0, "", warning
            )
        assert len(calls) == 2 and "install" in calls[0]
        assert environment["MISE_FETCH_REMOTE_VERSIONS_CACHE"] == "1h"
        assert command[-1] == "aqua:gitleaks/gitleaks@latest"
        return subprocess.CompletedProcess(command, 0, '{"PATH":""}', "")

    monkeypatch.setattr(subprocess, "run", run)
    groups: list[Group] = [
        {"path": ".", "checks": [{"name": "scan", "command": ["gitleaks"]}]}
    ]
    if failure:
        with pytest.raises((subprocess.CalledProcessError, ValueError)) as error:
            tool_setup.provision_tools(tmp_path, groups, 30)
        if failure == "exit":
            assert isinstance(error.value, subprocess.CalledProcessError)
            assert error.value.returncode == 7
        else:
            assert "could not be resolved" in str(error.value)
        assert len(calls) == 1
    else:
        tool_setup.provision_tools(tmp_path, groups, 30)
        assert len(calls) == 2


@pytest.mark.parametrize(
    ("scanner", "script", "package", "expected_use_npm", "arguments"),
    [
        (
            "dart-decimate",
            "dart-decimate check . --threshold 0 --strict --format json",
            'npm:dart-decimate[allow_builds=["dart-decimate"]]@latest',
            True,
            ["check", ".", "--threshold", "0", "--strict", "--format", "json"],
        ),
        (
            "react-doctor",
            "react-doctor --scope full --blocking warning --no-respect-inline-disables --json --json-out coverage/react.json",
            "npm:react-doctor@latest",
            False,
            [
                "--scope",
                "full",
                "--blocking",
                "warning",
                "--no-respect-inline-disables",
                "--json",
                "--json-out",
                "coverage/react.json",
            ],
        ),
    ],
)
@pytest.mark.parametrize("stale_local", [False, True])
def test_package_script_scanner_executes_provisioned_native_executable(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    scanner: str,
    script: str,
    package: str,
    expected_use_npm: bool,
    arguments: list[str],
    stale_local: bool,
) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"scripts": {"audit": script}}))
    group: Group = {
        "path": ".",
        "checks": [{"name": scanner, "command": ["pnpm", "run", "audit"]}],
    }
    assert execute_provisioned_scanner(
        runner,
        tmp_path,
        monkeypatch,
        group,
        scanner,
        package,
        stale_local=stale_local,
        expected_use_npm=expected_use_npm,
    ) == ["managed", *arguments]


def test_package_script_dart_boundary_gate_checks_native_configuration(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "audit": "dart-decimate check . --boundary-violations --strict"
                }
            }
        )
    )
    group: Group = {"path": ".", "language": "dart", "checks": []}
    gate: Gate = {"name": "boundaries", "command": ["pnpm", "run", "audit"]}
    calls: list[list[str]] = []

    def native_config(command: list[str], **_kwargs: object) -> str:
        calls.append(command)
        return json.dumps({"config": {"boundaries": []}})

    monkeypatch.setattr(subprocess, "check_output", native_config)
    with pytest.raises(ValueError, match="nonempty project from/disallow prefixes"):
        runner.prepare_command(group, gate, 5)
    assert calls == [["dart-decimate", "config", ".", "--format", "json"]]


@pytest.mark.parametrize(
    ("name", "configuration"),
    [
        (".importlinter", "[importlinter]\nroot_package = example\n"),
        (
            "setup.cfg",
            "[metadata]\nname = fixture\n\n[importlinter]\nroot_package = example\n",
        ),
    ],
)
def test_installer_rejects_import_linter_priority_owner_without_partial_write(
    installer: ModuleType, tmp_path: Path, name: str, configuration: str
) -> None:
    project = import_linter_project(tmp_path)
    original = project.read_text()
    (tmp_path / name).write_text(configuration)

    with pytest.raises(ValueError, match=rf"prioritizes {name}"):
        installer.install(tmp_path)

    assert project.read_text() == original
    assert (tmp_path / name).read_text() == configuration
    assert not (tmp_path / ".hooks").exists()


@pytest.mark.parametrize(
    "configurations",
    [
        {".importlinter": RECURSIVE_IMPORT_LINTER},
        {".importlinter": SPLIT_RECURSIVE_IMPORT_LINTER},
        {"setup.cfg": "[metadata]\nname = fixture\n\n" + RECURSIVE_IMPORT_LINTER},
        {
            "setup.cfg": "[metadata]\nname = fixture\n\n" + RECURSIVE_IMPORT_LINTER,
            ".importlinter": "[importlinter]\nroot_package = example\n",
        },
    ],
    ids=[
        "dotfile",
        "dotfile-split-recursive-contracts",
        "setup-cfg",
        "setup-cfg-prioritizes-over-dotfile",
    ],
)
def test_installer_accepts_effective_import_linter_recursive_contract(
    installer: ModuleType, tmp_path: Path, configurations: dict[str, str]
) -> None:
    project = import_linter_project(tmp_path)
    for name, configuration in configurations.items():
        (tmp_path / name).write_text(configuration)

    installer.install(tmp_path)

    assert "[tool.importlinter]" not in project.read_text()
    assert {
        name: (tmp_path / name).read_text() for name in configurations
    } == configurations


def test_unrelated_setup_cfg_does_not_block_toml_import_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "src/example"
    source.mkdir(parents=True)
    (source / "__init__.py").write_text("value = 1\n")
    (tmp_path / "setup.cfg").write_text("[metadata]\nname = fixture\n")

    content = import_configuration(
        tmp_path,
        {"path": ".", "checks": [], "sources": ["src"]},
        '[project]\nname = "fixture"\nversion = "1"\n',
    )

    assert "[tool.importlinter]" in content


def test_installer_rejects_old_manifest_without_partial_scaffold(
    installer: ModuleType, tmp_path: Path
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    manifest = tmp_path / "hard-eng.gates.json"
    original = (
        '{"checks": [{"name": "existing", "command": ["python3", "verify.py"]}]}\n'
    )
    manifest.write_text(original)
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname="existing-app"\nversion="1.0"\n'
    )
    with pytest.raises(TypeError, match="rerun the Hard Eng installer"):
        installer.install(tmp_path)
    assert manifest.read_text() == original
    assert not (tmp_path / ".hooks").exists()


def test_installed_check_provisions_yaml_and_keeps_real_gate_failures(
    tmp_path: Path,
) -> None:
    original = Path(__file__).resolve().parents[1]
    shutil.copytree(original / ".hooks", tmp_path / ".hooks")
    for name in ("PRODUCT.md", "DESIGN.md"):
        shutil.copyfile(original / name, tmp_path / name)
    (tmp_path / "package.json").write_text('{"private":true}')
    (tmp_path / "pnpm-workspace.yaml").write_text("packages: ['apps/*']\n")
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [{"path": ".", "checks": []}],
                "shared": [
                    {
                        "name": "fixture",
                        "command": ["python3", "-c", "raise SystemExit(1)"],
                    }
                ],
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    environment = tmp_path / "empty-python"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment)], check=True
    )
    python = str(environment / "bin/python")
    command = [python, "-I", "-c", "import yaml"]
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0
    result = subprocess.run(
        [python, str(tmp_path / ".hooks/hard-eng.py"), "check"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "No module named 'yaml'" not in result.stderr
    assert "missing" in result.stderr.lower() and "shared" in result.stderr.lower()
    assert subprocess.run(command, capture_output=True, check=False).returncode != 0


def test_candidate_provisions_yaml_without_host_site_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = tmp_path / "source", tmp_path / "target"
    original = Path(__file__).resolve().parents[1]
    (source / ".agents/skills").mkdir(parents=True)
    git(source, "init", "-q")
    (target / ".agents/skills").mkdir(parents=True)
    for name in ("pyproject.toml", "uv.lock"):
        shutil.copyfile(original / name, source / name)
    shutil.copytree(original / ".hooks", target / ".hooks")
    (target / ".hooks/hard-eng.py").write_text(
        "from pathlib import Path\n"
        "from project_setup import workspace_members\n"
        "def check(base, verify_plan):\n"
        "    assert base and not verify_plan\n"
        "    assert workspace_members(Path.cwd(), 'javascript') == ['apps/*']\n"
        "    return 0\n"
    )
    (target / "pnpm-workspace.yaml").write_text("packages: ['apps/*']\n")
    (target / "hard-eng.gates.json").write_text(json.dumps({"packages": []}))
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
    subprocess.run(["git", "add", "."], cwd=target, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "synthetic workspace",
        ],
        cwd=target,
        check=True,
    )
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "clone", "--bare", str(target), str(remote)], check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", str(remote)], cwd=target, check=True
    )
    environment = tmp_path / "empty-python"
    subprocess.run(
        ["uv", "venv", "--python", sys.executable, str(environment)], check=True
    )
    python = str(environment / "bin/python")
    probe = subprocess.run(
        [python, "-I", "-c", "import yaml"], capture_output=True, check=False
    )
    assert probe.returncode != 0 and b"No module named 'yaml'" in probe.stderr
    monkeypatch.setattr(update.sys, "executable", python)
    update.verify_candidate(
        target, source, {"project.txt": "candidate"}, {}, tmp_path / "candidate"
    )
    assert not (target / "project.txt").exists()
    assert (source / "uv.lock").read_bytes() == (original / "uv.lock").read_bytes()
    assert (
        subprocess.run(
            [python, "-I", "-c", "import yaml"], capture_output=True, check=False
        ).returncode
        != 0
    )


def test_configuration_candidate_without_origin_uses_head(
    release: tuple[Path, Path, str], capfd: pytest.CaptureFixture[str]
) -> None:
    source, target, _ = release
    (target / "package.json").unlink()
    commit(target, "application without task plan")
    config = json.loads((target / "hard-eng.gates.json").read_text())
    config["shared"][0]["command"] = [
        "python3",
        "-c",
        "print('APPLICATION_SCOPE_CHECK')",
    ]

    update.verify_candidate(
        target,
        source,
        {"hard-eng.gates.json": json.dumps(config)},
        {},
        target.parent / "candidate",
    )

    assert git(target, "remote") == ""
    assert "APPLICATION_SCOPE_CHECK" in capfd.readouterr().err


@pytest.mark.parametrize("exit_code", [0, 7])
def test_native_uv_gate_processes_overlap_with_shared_cache(
    runner: ModuleType, tmp_path: Path, exit_code: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("UV_CACHE_DIR", str(tmp_path / "uv-cache"))
    code = """import pathlib, time, sys
index = int(sys.argv[1])
pathlib.Path(f'start-{index}').touch()
deadline = time.monotonic() + 3
while not pathlib.Path(f'start-{1-index}').exists():
    if time.monotonic() > deadline:
        raise RuntimeError('Independent native uv gates did not overlap')
    time.sleep(0.01)
pathlib.Path(str(index)).touch()
sys.exit(int(sys.argv[2]))
"""
    output_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                runner.run_gate,
                {"path": "."},
                {
                    "name": str(index),
                    "command": [
                        "uv",
                        "run",
                        "--no-project",
                        "--python",
                        sys.executable,
                        "python",
                        "-c",
                        code,
                        str(index),
                        str(exit_code),
                    ],
                },
                5,
                output_lock,
            )
            for index in range(2)
        ]
        assert [future.result() for future in futures] == [bool(exit_code)] * 2
    assert all((tmp_path / str(index)).exists() for index in range(2))

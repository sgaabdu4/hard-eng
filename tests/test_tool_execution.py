"""Exercise shared-cache exclusion through real gate subprocesses."""

import json
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
from gate_config import Gate, Group, validate_gate, validate_package_services


@pytest.mark.parametrize("flag", [["--max-crap", "0"], ["--max-crap=0"]])
def test_gate_rejects_disabled_fallow_metric_before_execution(
    tmp_path: Path, flag: list[str]
) -> None:
    gate: Gate = {"name": "audit", "command": ["fallow", "audit", *flag]}
    with pytest.raises(ValueError, match="CRAP enforcement cannot be disabled"):
        validate_gate(gate, tmp_path, set())
    gate["command"] = ["fallow", "audit", "--max-crap", "30"]
    with pytest.raises(ValueError, match="require a native fallow report"):
        validate_gate(gate, tmp_path, set())
    gate["report"] = {"type": "fallow", "path": "audit.json"}
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


def test_existing_fallow_audit_must_be_the_enforced_gate(tmp_path: Path) -> None:
    from project_setup import adapt_javascript

    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "check:fallow": "fallow audit --format json --output-file coverage/fallow.json"
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
    validate_package_services(tmp_path, group, {}, {}, inherited)


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


@pytest.mark.parametrize("executable", ["uv", "uvx"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_uv_gate_processes_do_not_share_cache_concurrently(
    runner: ModuleType, tmp_path: Path, executable: str, exit_code: int
) -> None:
    binary = tmp_path / executable
    binary.symlink_to(sys.executable)
    code = (
        "import pathlib,time,sys;"
        "cache=pathlib.Path('cache-write');"
        "cache.mkdir();time.sleep(0.1);cache.rmdir();"
        "pathlib.Path(sys.argv[1]).touch();sys.exit(int(sys.argv[2]))"
    )
    output_lock = threading.Lock()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(
                runner.run_gate,
                {"path": "."},
                {
                    "name": str(index),
                    "command": [str(binary), "-c", code, str(index), str(exit_code)],
                },
                5,
                output_lock,
            )
            for index in range(2)
        ]
        assert [future.result() for future in futures] == [bool(exit_code)] * 2
    assert all((tmp_path / str(index)).exists() for index in range(2))

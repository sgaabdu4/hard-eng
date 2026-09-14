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
from gate_config import Group


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

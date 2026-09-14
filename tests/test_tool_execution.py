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
import update


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

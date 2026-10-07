import fcntl
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]
PNPM = """#!{python}
import json, os, sys, time
from pathlib import Path
state = Path({state!r})
if sys.argv[1] == "view":
    if (state / "offline").exists():
        raise SystemExit("network unreachable")
    print(json.dumps((state / "latest").read_text().strip()))
    raise SystemExit
target = Path(sys.argv[sys.argv.index("--dir") + 1])
version = sys.argv[-1].rsplit("@", 1)[1]
with (state / "adds").open("a") as log:
    log.write(version + "\\n")
time.sleep(float(os.environ.get("FAKE_ADD_SECONDS", "0")))
if (state / "fail").exists():
    raise SystemExit("registry unavailable")
binary = target / "node_modules/@jdxcode/mise/bin/mise"
binary.parent.mkdir(parents=True)
reported = "0.0.0" if (state / "corrupt").exists() else version
binary.write_text(
    "#!/bin/sh\\n"
    f'[ "$1" = --version ] && echo "{{reported}} test" && exit 0\\n'
    '[ "$2" = env ] && echo \\'{{"PATH": ""}}\\'\\n'
    "exit 0\\n"
)
binary.chmod(0o755)
"""
PROVISION = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import tool_setup
tool_setup.provision_tools(
    Path(sys.argv[2]),
    [{"path": ".", "checks": [{"name": "secrets", "command": ["gitleaks"]}]}],
    60,
)
"""


@pytest.fixture
def registry(tmp_path: Path) -> Path:
    state = tmp_path / "registry"
    bin_directory = tmp_path / "bin"
    state.mkdir()
    bin_directory.mkdir()
    (state / "latest").write_text("2026.9.13")
    pnpm = bin_directory / "pnpm"
    pnpm.write_text(PNPM.format(python=sys.executable, state=str(state)))
    pnpm.chmod(0o755)
    return state


def launch(
    tmp_path: Path, add_seconds: float = 0, quick: bool = False
) -> subprocess.Popen[str]:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("MISE_", "PNPM_CONFIG_", "NPM_CONFIG_"))
    }
    return subprocess.Popen(
        [
            sys.executable,
            "-c",
            PROVISION,
            str(SOURCE / ".hooks"),
            str(tmp_path),
            *(["--quick"] if quick else []),
        ],
        env={
            **environment,
            "RUNNER_TEMP": str(tmp_path / "runner"),
            "PATH": str(tmp_path / "bin") + os.pathsep + environment["PATH"],
            "FAKE_ADD_SECONDS": str(add_seconds),
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def provision(tmp_path: Path, quick: bool = False) -> subprocess.CompletedProcess[str]:
    process = launch(tmp_path, quick=quick)
    output, _ = process.communicate(timeout=60)
    return subprocess.CompletedProcess(process.args, process.returncode, output)


def launchers(tmp_path: Path) -> list[str]:
    return sorted(
        path.name
        for path in (tmp_path / "runner/hard-eng-tools/mise-launcher").iterdir()
        if path.is_dir()
    )


def adds(registry: Path) -> list[str]:
    return (registry / "adds").read_text().split()


def test_unchanged_latest_version_is_installed_once(
    tmp_path: Path, registry: Path
) -> None:
    for _ in range(3):
        assert provision(tmp_path).returncode == 0
    assert adds(registry) == ["2026.9.13"]
    assert launchers(tmp_path) == ["2026.9.13"]


def test_concurrent_checks_share_one_installation(
    tmp_path: Path, registry: Path
) -> None:
    processes = [launch(tmp_path, add_seconds=1) for _ in range(4)]
    for process in processes:
        output, _ = process.communicate(timeout=60)
        assert process.returncode == 0, output
    assert adds(registry) == ["2026.9.13"]
    assert launchers(tmp_path) == ["2026.9.13"]


def test_new_version_replaces_unheld_launchers_only(
    tmp_path: Path, registry: Path
) -> None:
    owned = tmp_path / "runner/hard-eng-tools"
    unrelated = owned / "pnpm/cache/dlx/earlier/pkg"
    unrelated.mkdir(parents=True)
    (registry / "latest").write_text("2026.9.11")
    assert provision(tmp_path).returncode == 0
    with (owned / "mise-launcher/2026.9.11.lock").open("a") as running_check:
        fcntl.flock(running_check, fcntl.LOCK_SH)
        for version in ("2026.9.12", "2026.9.13"):
            (registry / "latest").write_text(version)
            assert provision(tmp_path).returncode == 0
            assert launchers(tmp_path) == ["2026.9.11", version]
    assert provision(tmp_path).returncode == 0
    assert launchers(tmp_path) == ["2026.9.13"]
    assert adds(registry) == ["2026.9.11", "2026.9.12", "2026.9.13"]
    assert unrelated.is_dir()


@pytest.mark.parametrize("marker", ["fail", "corrupt"])
def test_failed_installation_leaves_no_launcher(
    tmp_path: Path, registry: Path, marker: str
) -> None:
    (registry / marker).touch()
    result = provision(tmp_path)
    assert result.returncode != 0
    assert "registry unavailable" in result.stdout or "installation check" in (
        result.stdout
    )
    assert not list((tmp_path / "runner/hard-eng-tools/mise-launcher").glob("[!.]*/"))
    assert not list((tmp_path / "runner/hard-eng-tools/mise-launcher").glob(".*"))
    (registry / marker).unlink()
    assert provision(tmp_path).returncode == 0
    assert launchers(tmp_path) == ["2026.9.13"]


def test_interrupted_installation_is_replaced_cleanly(
    tmp_path: Path, registry: Path
) -> None:
    interrupted = launch(tmp_path, add_seconds=30)
    while not (registry / "adds").exists():
        time.sleep(0.05)
    os.killpg(interrupted.pid, signal.SIGKILL)
    interrupted.wait()
    storage = tmp_path / "runner/hard-eng-tools/mise-launcher"
    assert [path.name[:9] for path in storage.iterdir() if path.is_dir()] == [
        ".staging-"
    ]
    assert provision(tmp_path).returncode == 0
    assert [path.name for path in storage.iterdir() if path.is_dir()] == ["2026.9.13"]


def test_tools_are_provisioned_outside_a_project_that_pins_pnpm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import Mock

    import tool_setup
    from conftest import use_installed_mise
    from gate_config import Group

    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"packageManager": "pnpm@11.8.0"}')
    use_installed_mise(tmp_path, monkeypatch)
    monkeypatch.setenv("RUNNER_TEMP", str(tmp_path / "runner"))
    native = Mock(return_value=subprocess.CompletedProcess([], 0, '{"PATH": ""}', ""))
    monkeypatch.setattr(subprocess, "run", native)
    react: Group = {
        "path": ".",
        "checks": [{"name": "doctor", "command": ["react-doctor"]}],
    }
    tool_setup.provision_tools(project, [react], 30)
    directories = [Path(call.kwargs["cwd"]) for call in native.call_args_list]
    assert directories == [tmp_path / "runner/hard-eng-tools"] * 2


def test_dead_code_gate_treats_console_script_targets_as_used(tmp_path: Path) -> None:
    import tool_setup

    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[project.scripts]\ndemo = "demo:main"\n'
        'other = "demo.cli:run_app"\n'
    )
    command = ["vulture", "src", "--min-confidence", "60"]
    assert tool_setup.managed_command(command, tmp_path) == [
        "uvx",
        "vulture@latest",
        *command[1:],
        "--ignore-names",
        "main,run_app",
    ]
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    assert tool_setup.managed_command(command, tmp_path)[2:] == command[1:]


def test_quick_check_uses_installed_tools_while_offline(
    tmp_path: Path, registry: Path
) -> None:
    assert provision(tmp_path).returncode == 0
    (registry / "offline").touch()
    assert provision(tmp_path).returncode != 0
    result = provision(tmp_path, quick=True)
    assert result.returncode == 0, result.stdout
    assert adds(registry) == ["2026.9.13"]


def test_quick_check_offline_without_tools_says_to_connect_once(
    tmp_path: Path, registry: Path
) -> None:
    (registry / "offline").touch()
    result = provision(tmp_path, quick=True)
    assert result.returncode != 0
    assert "Tools are not installed yet" in result.stdout
    assert "run the full check" in result.stdout


def test_quick_check_runs_python_scanners_from_the_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import tool_setup

    command = ["ruff", "check"]
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check"])
    assert tool_setup.managed_command(command)[:2] == ["uvx", "ruff@latest"]
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "check", "--quick"])
    assert tool_setup.managed_command(command)[:3] == [
        "uvx",
        "--offline",
        "ruff@latest",
    ]

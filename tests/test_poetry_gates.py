import importlib.util
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest
import tool_setup
from gate_config import Group
from python_setup import configure_python, python_gate_command

RETIRED_PREFIX = ["poetry", "run", "uv", "run", "--no-project", "--active"]
PROJECT = '[project]\nname = "demo"\nversion = "0"\n'


def test_a_poetry_gate_stays_in_the_active_environment_when_uv_has_a_pinned_path(
    tmp_path: Path,
) -> None:
    environment = tmp_path / "environment"
    venv.create(environment, with_pip=False)
    source = tmp_path / "source"
    source.mkdir()
    (source / "installed_module.py").write_text("")
    packages = next(environment.glob("lib/python*/site-packages"))
    (packages / "demo.pth").write_text(f"{source}\n")
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(PROJECT)
    pin = tmp_path / "config/uv/.python-version"
    pin.parent.mkdir(parents=True)
    pin.write_text(f"{sys.executable}\n")
    command = python_gate_command(["pytest"], "poetry")
    assert command[:2] == ["poetry", "run"]
    active = {
        **os.environ,
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "VIRTUAL_ENV": str(environment),
        "PATH": f"{environment / 'bin'}{os.pathsep}{os.environ['PATH']}",
    }
    result = subprocess.run(
        [
            *command[2 : command.index("--with")],
            "python",
            "-c",
            "import installed_module",
        ],
        cwd=project,
        env=active,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert result.returncode == 0, result.stderr


def test_the_check_drops_the_environment_that_its_launcher_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert importlib.util.find_spec("yaml"), "a rerun would replace this process"
    monkeypatch.setenv("VIRTUAL_ENV", "/nonexistent/throwaway")
    tool_setup.ensure_python_runtime()
    left = os.environ.get("VIRTUAL_ENV")
    assert left is None


def test_setup_gives_an_installed_poetry_gate_the_prefix_that_works(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        PROJECT + '\n[tool.pyrefly]\npreset = "strict"\n'
    )
    (tmp_path / "poetry.lock").touch()
    rest = ["--with", "pytest", "--upgrade-package", "pytest", "pytest", "-q"]
    package: Group = {
        "path": ".",
        "language": "python",
        "sources": ["demo"],
        "checks": [
            {"name": "tests", "role": "tests", "command": [*RETIRED_PREFIX, *rest]}
        ],
    }
    configure_python(tmp_path, tmp_path, package, {})
    command = package["checks"][0]["command"]
    assert command[:6] == python_gate_command(["pytest"], "poetry")[:6]
    assert command[:6] != RETIRED_PREFIX
    assert command[6:8] == ["--with", "pytest"]
    assert command[-1] == "-q"

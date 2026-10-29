"""The generated workflow keeps tool and cache directories a runner already exports."""

import os
import subprocess
from pathlib import Path
from types import ModuleType

import yaml
from ci_setup import configure_ci
from conftest import SOURCE
from test_swift import flutter_app, generated_workflow

WORKFLOW = ".github/workflows/hard-eng.yml"
DIRECTORIES = {
    "MISE_DATA_DIR": "hard-eng-tools/mise/data",
    "MISE_CACHE_DIR": "hard-eng-tools/mise/cache",
    "MISE_STATE_DIR": "hard-eng-tools/mise/state",
    "BUN_INSTALL_CACHE_DIR": "hard-eng-tools/bun/cache",
}


def exported(workflow: str, runner: Path, preset: dict[str, str]) -> dict[str, str]:
    """The variables the impact step hands to later steps, as GitHub reads them."""
    jobs = yaml.safe_load(workflow)["jobs"]
    run = next(s["run"] for s in jobs["hard-eng"]["steps"] if s.get("id") == "impact")
    temporary, github_env = runner / "temp", runner / "github_env"
    temporary.mkdir(parents=True)
    environment = {
        key: value for key, value in os.environ.items() if key not in DIRECTORIES
    }
    environment |= {
        **preset,
        "RUNNER_TEMP": str(temporary),
        "RUNNER_ARCH": "X64",
        "BASE_SHA": "none",
        "GITHUB_ENV": str(github_env),
        "GITHUB_OUTPUT": str(runner / "github_output"),
    }
    result = subprocess.run(
        ["bash", "-c", run], check=False, cwd=runner, env=environment
    )
    assert result.returncode == 0
    lines = github_env.read_text().splitlines()
    return dict(
        line.split("=", 1) for line in lines if line.startswith(tuple(DIRECTORIES))
    )


def test_unset_directories_use_the_runner_temp_paths(tmp_path: Path) -> None:
    workflow = (SOURCE / WORKFLOW).read_text()
    assert exported(workflow, tmp_path, {}) == {
        name: f"{tmp_path}/temp/{tail}" for name, tail in DIRECTORIES.items()
    }


def test_directories_the_runner_exports_are_kept(tmp_path: Path) -> None:
    workflow = (SOURCE / WORKFLOW).read_text()
    preset = {
        "MISE_DATA_DIR": "/opt/tools/data",
        "BUN_INSTALL_CACHE_DIR": "/opt/tools/bun",
    }
    assert exported(workflow, tmp_path, preset) == {
        "MISE_DATA_DIR": "/opt/tools/data",
        "MISE_CACHE_DIR": f"{tmp_path}/temp/hard-eng-tools/mise/cache",
        "MISE_STATE_DIR": f"{tmp_path}/temp/hard-eng-tools/mise/state",
        "BUN_INSTALL_CACHE_DIR": "/opt/tools/bun",
    }


def test_older_workflow_keeps_runner_directories_after_the_update(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = installer.gate_config(root)
    current = generated_workflow(root, config)
    older = current
    for name, tail in DIRECTORIES.items():
        older = older.replace(
            f'echo "{name}=${{{name}:-$RUNNER_TEMP/{tail}}}"',
            f'echo "{name}=$RUNNER_TEMP/{tail}"',
        )
    assert older != current
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(older)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    assert changes == {WORKFLOW: current}
    path.write_text(current)
    changes.clear()
    configure_ci(root, SOURCE, config, changes)
    assert changes == {}


def test_a_custom_tool_directory_stays_when_the_update_arrives(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = installer.gate_config(root)
    custom = generated_workflow(root, config).replace(
        "${MISE_DATA_DIR:-$RUNNER_TEMP/hard-eng-tools/mise/data}", "/srv/tools/data"
    )
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    assert changes == {}

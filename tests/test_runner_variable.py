"""Generated workflows take their Linux runner from the CI_RUNS_ON repository variable."""

import os
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
import yaml
from ci_setup import configure_ci
from conftest import SOURCE
from gate_config import GateConfig
from test_apple_jobs import previous_generation
from test_swift import LINUX_RUNNER, app_config, flutter_app, generated_workflow

WORKFLOW = ".github/workflows/hard-eng.yml"


def hosted(plain: str, *, swift: bool) -> str:
    """The workflow as releases before the CI_RUNS_ON variable generated it."""
    if swift:
        return previous_generation(plain, variable=False)
    return plain.replace(
        f"    runs-on: {LINUX_RUNNER}\n", "    runs-on: ubuntu-latest\n"
    )


@pytest.mark.parametrize("name", ["hard-eng.yml", "pr-text.yml"])
def test_shipped_workflows_take_their_runner_from_the_variable(name: str) -> None:
    workflow = yaml.safe_load((SOURCE / ".github/workflows" / name).read_text())
    assert {job["runs-on"] for job in workflow["jobs"].values()} == {LINUX_RUNNER}


def test_a_failed_impact_script_still_runs_the_swift_job(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    jobs = yaml.safe_load(generated_workflow(root, app_config(installer, root)))["jobs"]
    run = next(s["run"] for s in jobs["impact"]["steps"] if s.get("id") == "impact")
    output = tmp_path / "output"
    environment = {**os.environ, "BASE_SHA": "none", "GITHUB_OUTPUT": str(output)}
    result = subprocess.run(
        ["bash", "-c", run],
        check=False,
        cwd=tmp_path,
        env=environment,
        capture_output=True,
    )
    assert result.returncode == 0
    assert output.read_text() == "runner=ubuntu-latest\napple=true\n"


@pytest.mark.parametrize(
    ("swift_before", "swift_after"), [(False, False), (True, True), (False, True)]
)
def test_older_workflow_moves_to_the_runner_variable(
    installer: ModuleType, tmp_path: Path, swift_before: bool, swift_after: bool
) -> None:
    root = tmp_path / "app"
    flutter_app(root)

    def configured(swift: bool) -> GateConfig:
        return app_config(installer, root) if swift else installer.gate_config(root)

    current = generated_workflow(root, configured(swift_after))
    plain = generated_workflow(root, installer.gate_config(root))
    older = hosted(plain, swift=swift_before)
    assert older != plain
    path = root / WORKFLOW
    path.parent.mkdir(parents=True)
    path.write_text(older)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, configured(swift_after), changes)
    assert changes == {WORKFLOW: current}
    path.write_text(current)
    changes.clear()
    configure_ci(root, SOURCE, configured(swift_after), changes)
    assert changes == {}


def test_a_custom_runner_stays_when_the_variable_arrives(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "app"
    flutter_app(root)
    config = installer.gate_config(root)
    path = root / WORKFLOW
    custom = generated_workflow(root, config).replace(
        LINUX_RUNNER, "[self-hosted, linux]"
    )
    path.parent.mkdir(parents=True)
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(root, SOURCE, config, changes)
    assert changes == {}

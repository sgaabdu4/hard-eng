"""Deployment, shell and workflow checks are added only for files the project has."""

import json
from pathlib import Path
from types import ModuleType

import hook_chain
import pytest
from gate_config import GateConfig, load_groups
from test_runner import native_gate_fixture
from test_setup import repository


@pytest.mark.parametrize(
    "name",
    [
        "Dockerfile",
        "Containerfile",
        "infra/main.tf",
        "infra/Chart.yaml",
        "main.tf.json",
        "dev.tfvars",
        "tfplan",
        "dev.tfplan",
    ],
)
def test_deployment_detection(installer: ModuleType, tmp_path: Path, name: str) -> None:
    repository(tmp_path)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("fixture\n")
    config: GateConfig = {"packages": [], "shared": []}
    installer.configure_deployment(tmp_path, config)
    installer.configure_deployment(tmp_path, config)
    assert config["shared"] == [
        {
            "name": "trivy-config",
            "role": "deployment",
            "command": ["trivy", "config", "--exit-code", "1", "--format", "json", "."],
            "report": {"type": "trivy", "path": "coverage/trivy.json", "stdout": True},
        }
    ]


def test_no_deployment_from_ordinary_yaml_or_ignored_file(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "settings.yaml").write_text("hello: world\n")
    (tmp_path / ".gitignore").write_text("Dockerfile\n")
    (tmp_path / "Dockerfile").write_text("FROM alpine:latest\n")
    config: GateConfig = {"packages": [], "shared": []}
    installer.configure_deployment(tmp_path, config)
    assert not config["shared"]


def test_shell_and_workflow_detection(installer: ModuleType, tmp_path: Path) -> None:
    repository(tmp_path)
    config: GateConfig = {"packages": [], "shared": []}
    installer.configure_shellcheck(tmp_path, config)
    installer.configure_workflows(tmp_path, config)
    assert not config["shared"]
    for name, source in {
        "a.sh": "#!/bin/sh\n",
        "space name.bash": "echo ok\n",
        "helper": "#!/usr/bin/env bash\n",
        "zsh": "#!/bin/zsh\n",
    }.items():
        (tmp_path / name).write_text(source)
    workflows = tmp_path / ".github/workflows"
    workflows.mkdir(parents=True)
    (workflows / "test.yml").write_text("on: push\n")
    for _ in range(2):
        installer.configure_shellcheck(tmp_path, config)
        installer.configure_workflows(tmp_path, config)
    gates = {gate["role"]: gate for gate in config["shared"]}
    assert gates["shell"]["command"] == [
        "shellcheck",
        "--",
        "a.sh",
        "helper",
        "space name.bash",
    ]
    assert gates["workflows"]["command"] == ["actionlint", "-no-color"]
    assert "--strict-collection" in gates["ci-security"]["command"]
    assert len(config["shared"]) == 3


def test_existing_checks_are_not_replaced(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    gates = [
        {"name": role, "role": role, "command": ["custom"]}
        for role in ("shell", "workflows", "ci-security", "deployment")
    ]
    config = {"shared": gates.copy()}
    for configure in (
        installer.configure_shellcheck,
        installer.configure_workflows,
        installer.configure_deployment,
    ):
        configure(tmp_path, config)
    assert config["shared"] == gates


def test_own_hook_launcher_needs_no_shellcheck_entry(
    runner: ModuleType, installer: ModuleType, tmp_path: Path
) -> None:
    native_gate_fixture(tmp_path, installer, "python")
    (tmp_path / "helper.sh").write_text("echo helper\n")
    gates = tmp_path / "hard-eng.gates.json"
    config = json.loads(gates.read_text())
    installer.configure_shellcheck(tmp_path, config)
    gates.write_text(json.dumps(config))
    (tmp_path / ".githooks").mkdir()
    (tmp_path / ".githooks/post-checkout").write_text(hook_chain.WORKTREE_LAUNCHER)
    load_groups(tmp_path)
    (tmp_path / ".githooks/pre-commit").write_text("#!/bin/sh\necho project\n")
    with pytest.raises(ValueError, match="shellcheck omits .githooks/pre-commit"):
        load_groups(tmp_path)

"""Installer outcomes: preserve project work and install only applicable checks."""

import json
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import GateConfig
from project_setup import import_configuration, javascript_manager


@pytest.mark.parametrize(
    "manager,lock,flag",
    [
        ("npm", "package-lock.json", "ci"),
        ("pnpm", "pnpm-lock.yaml", "--frozen-lockfile"),
        ("yarn", "yarn.lock", "--immutable"),
        ("bun", "bun.lock", "--frozen-lockfile"),
    ],
)
def test_existing_package_manager_is_selected(
    tmp_path: Path, manager: str, lock: str, flag: str
) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": manager + "@2.0.0"})
    )
    (tmp_path / lock).write_text("fixture\n")
    selected, command, selected_lock = javascript_manager(tmp_path)
    assert selected == manager and selected_lock == lock
    assert flag in command


def test_ambiguous_lockfiles_are_not_guessed(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text("{}")
    for name in ("package-lock.json", "yarn.lock"):
        (tmp_path / name).touch()
    with pytest.raises(ValueError, match="Ambiguous"):
        javascript_manager(tmp_path)


def test_react_and_existing_project_scripts_are_gated(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "packageManager": "pnpm@10.0.0",
                "dependencies": {"react": "19"},
                "scripts": {
                    "build": "project-build",
                    "test:integration": "project-integration",
                    "check:generated": "project-generator-check",
                },
            }
        )
    )
    (tmp_path / "src").mkdir()
    (tmp_path / "src/app.tsx").write_text("export const value = 1;\n")
    config = installer.gate_config(tmp_path)
    checks = {gate["role"]: gate for gate in config["packages"][0]["checks"]}
    assert checks["lockfiles"]["command"] == ["pnpm", "install", "--frozen-lockfile"]
    assert checks["build"]["command"] == ["pnpm", "run", "build"]
    assert checks["integration"]["command"] == ["pnpm", "run", "test:integration"]
    assert checks["generated"]["command"] == ["pnpm", "run", "check:generated"]
    assert checks["react"]["report"]["type"] == "react-doctor"
    assert checks["tests"]["command"][0] == "pnpm"


def test_python_packages_receive_recursive_import_contract(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    package = tmp_path / "src/example"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("value = 1\n")
    installer.install(tmp_path)
    content = (tmp_path / "pyproject.toml").read_text()
    assert 'root_packages = ["example"]' in content
    assert 'ancestors = ["example", "example.**"]' in content
    assert "depth = 0" in content
    assert (
        import_configuration(
            tmp_path, {"path": ".", "checks": [], "sources": ["src"]}, content
        )
        == content
    )


def test_standalone_python_does_not_invent_import_architecture(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "pyproject.toml").write_text('[project]\nname="fixture"\nversion="1"\n')
    (tmp_path / "main.py").write_text("value = 1\n")
    package = installer.gate_config(tmp_path)["packages"][0]
    assert package["sources"] == ["main.py"]
    assert "imports" not in {gate["role"] for gate in package["checks"]}


def test_plain_dart_uses_native_coverage_tool(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    (tmp_path / "pubspec.yaml").write_text(
        'name: fixture\nenvironment:\n  sdk: ">=3.0.0 <4.0.0"\n'
    )
    result = subprocess.run(
        ["python3", str(installer.SOURCE / "setup.py"), str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    config = json.loads((tmp_path / "hard-eng.gates.json").read_text())
    checks = {gate["role"]: gate for gate in config["packages"][0]["checks"]}
    assert checks["lockfiles"]["command"] == [
        "dart",
        "pub",
        "get",
        "--enforce-lockfile",
    ]
    assert checks["tests"]["command"][:3] == [
        "dart",
        "run",
        "coverage:test_with_coverage",
    ]
    assert checks["tests"]["report"]["stdout"] is False


def test_workspace_installs_once_and_keeps_child_source_scope(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": "pnpm@10.0.0", "workspaces": ["packages/*"]})
    )
    (tmp_path / "pnpm-lock.yaml").touch()
    child = tmp_path / "packages/app"
    (child / "src").mkdir(parents=True)
    (child / "package.json").write_text('{"name":"app"}')
    (child / "src/main.ts").write_text("export const value = 1;\n")
    config = installer.gate_config(tmp_path)
    root, app = config["packages"]
    assert "language" not in root
    assert app["sources"] == ["src"]
    assert (
        sum(
            gate.get("role") == "lockfiles"
            for package in config["packages"]
            for gate in package["checks"]
        )
        == 1
    )
    tests = next(gate for gate in app["checks"] if gate.get("role") == "tests")
    assert tests["command"] == ["pnpm", "run", "test:coverage"]


def repository(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / "package.json").write_text('{"private":true}')


def snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    }


def test_install_preserves_project_and_repeats(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "AGENTS.md").write_text("# Project rules\n\nKeep this.\n")
    installer.install(tmp_path)
    before = snapshot(tmp_path)
    installer.install(tmp_path)
    assert snapshot(tmp_path) == before
    instructions = (tmp_path / "AGENTS.md").read_text()
    assert instructions.count("<!-- hard-eng:start -->") == 1
    assert instructions.endswith("# Project rules\n\nKeep this.\n")
    assert not (tmp_path / "DECISION.md").exists()
    assert not (tmp_path / "AGENTS.override.md").exists()
    assert (tmp_path / ".git/hooks/pre-push").stat().st_mode & 0o111
    assert (tmp_path / ".hooks/reports.py").is_file()


@pytest.mark.parametrize(
    "name", [".hooks/reports.py", ".agents/skills/he/SKILL.md", ".git/hooks/pre-push"]
)
def test_conflict_writes_nothing(
    installer: ModuleType, tmp_path: Path, name: str
) -> None:
    repository(tmp_path)
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("local work\n")
    before = snapshot(tmp_path)
    with pytest.raises(ValueError):
        installer.install(tmp_path)
    assert snapshot(tmp_path) == before
    assert target.read_text() == "local work\n"


def test_symlink_destination_is_preserved(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / ".hooks").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symlink"):
        installer.install(tmp_path)
    assert list(outside.iterdir()) == []


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


def test_conflicting_python_typing_is_not_overwritten(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    (tmp_path / "package.json").unlink()
    content = (
        '[project]\nname = "fixture"\nversion = "1"\n[tool.pyrefly]\npreset="default"\n'
    )
    (tmp_path / "pyproject.toml").write_text(content)
    with pytest.raises(ValueError, match="strict"):
        installer.install(tmp_path)
    assert (tmp_path / "pyproject.toml").read_text() == content
    assert not (tmp_path / ".hooks").exists()


def test_missing_project_manifest_fails(installer: ModuleType, tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    with pytest.raises(ValueError, match="manifest"):
        installer.install(tmp_path)


def test_hook_registrations_only_use_session_and_stop(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    installer.install(tmp_path)
    for path, events in (
        (".claude/settings.json", {"SessionStart", "Stop"}),
        (".codex/hooks.json", {"SessionStart", "Stop"}),
        (".github/hooks/hard-eng.json", {"sessionStart", "agentStop"}),
    ):
        assert set(json.loads((tmp_path / path).read_text())["hooks"]) == events

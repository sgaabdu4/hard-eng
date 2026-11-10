"""A required check that writes no report must name the tool of its role."""

import json
from pathlib import Path

import gate_config
import pytest
from conftest import SOURCE
from gate_config import Group

TEMPLATES = SOURCE / ".agents/skills/he/templates"
SCRIPTS = {
    "lint": "biome ci . --error-on-warnings",
    "noop": "true",
    "test:coverage": "bun test --coverage",
    "test:performance": "bun test performance",
}


def template_group(root: Path, language: str) -> Group:
    template = json.loads((TEMPLATES / f"hard-eng.{language}.json").read_text())
    (group,) = template["packages"]
    folder = root / group["path"]
    folder.mkdir(exist_ok=True)
    (folder / "package.json").write_text(json.dumps({"scripts": SCRIPTS}))
    if language == "swift":
        group["performance_exception"] = "Fixture shell code with no workload."
    return group


def swap(group: Group, role: str, command: list[str]) -> Group:
    swapped = group.copy()
    swapped["checks"] = [gate.copy() for gate in group["checks"]]
    for gate in swapped["checks"]:
        if gate.get("role") == role:
            gate["command"] = command
    return swapped


@pytest.mark.parametrize(
    ("language", "role", "command", "tool"),
    [
        ("python", "format", ["true"], "ruff format"),
        ("python", "types", ["sh", "-c", "exit 0"], "pyrefly check"),
        ("python", "dead-code", ["echo", "ruff", "check"], "vulture"),
        ("javascript", "format-lint", ["bun", "run", "noop"], "biome ci"),
        ("javascript", "types", ["biome", "lint"], "tsc"),
        ("dart", "types", ["dart", "--version"], "dart analyze"),
        ("swift", "format-lint", ["swift", "--version"], "swift format lint"),
    ],
)
def test_required_check_must_name_its_tool(
    tmp_path: Path, language: str, role: str, command: list[str], tool: str
) -> None:
    group = swap(template_group(tmp_path, language), role, command)
    with pytest.raises(ValueError) as refusal:
        gate_config.validate_group(tmp_path, group, set())
    message = str(refusal.value)
    assert f"the {role} check must run `{tool}`" in message
    assert " ".join(command) in message
    unowned: Group = {
        "path": ".",
        "checks": [gate for gate in group["checks"] if gate.get("role") == role],
    }
    assert gate_config.validate_group(tmp_path, unowned, set()) == 1


def test_a_shared_scan_must_name_its_tool() -> None:
    config = gate_config.parse_config((SOURCE / "hard-eng.gates.json").read_text())
    gate_config.validate_required_checks(SOURCE, config)
    for gate in config["shared"]:
        if gate["role"] == "workflows":
            gate["command"] = ["true"]
    with pytest.raises(ValueError, match="the workflows check must run `actionlint`"):
        gate_config.validate_required_checks(SOURCE, config)


@pytest.mark.parametrize(
    ("language", "role", "command"),
    [
        ("python", "lint", ["uvx", "ruff@latest", "check", "."]),
        ("python", "format", ["bash", "-c", "exec uvx ruff@0.14.0 format --check ."]),
        ("javascript", "format-lint", ["bun", "run", "lint"]),
        ("javascript", "types", ["bunx", "tsc", "--noEmit"]),
        ("dart", "types", ["fvm", "dart", "analyze", "--fatal-infos", "."]),
    ],
)
def test_wrapped_tool_commands_load(
    tmp_path: Path, language: str, role: str, command: list[str]
) -> None:
    group = swap(template_group(tmp_path, language), role, command)
    assert gate_config.validate_group(tmp_path, group, set()) == len(group["checks"])


@pytest.mark.parametrize("language", ["python", "javascript", "dart", "swift"])
def test_own_gates_and_shipped_templates_name_their_tools(
    tmp_path: Path, language: str
) -> None:
    group = template_group(tmp_path, language)
    assert gate_config.validate_group(tmp_path, group, set()) == len(group["checks"])
    assert gate_config.load_groups(SOURCE)

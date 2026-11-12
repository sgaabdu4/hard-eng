"""A required check that writes no report must name the tool of its role."""

import json
import re
from pathlib import Path

import gate_config
import pytest
import update
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
def test_shipped_templates_name_their_tools(tmp_path: Path, language: str) -> None:
    group = template_group(tmp_path, language)
    assert gate_config.validate_group(tmp_path, group, set()) == len(group["checks"])


def test_this_repository_gates_name_their_tools() -> None:
    assert gate_config.load_groups(SOURCE)


def test_fixture_gh_ignores_the_developers_sign_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    # A failed assert on the value itself would print a real token.
    signed_in = bool(update.github_token())
    assert not signed_in


def test_gate_validation_rejects_javascript_package_manager_drift(
    tmp_path: Path,
) -> None:
    """HE-PERFORMANCE-SUITE: a package needs a performance suite or a reviewed exception."""
    (tmp_path / "package.json").write_text('{"packageManager":"bun@1.3.0"}')
    (tmp_path / "bun.lock").touch()
    group: Group = {
        "path": ".",
        "language": "javascript",
        "sources": ["src"],
        "checks": [
            {"name": "types", "role": "types", "command": ["tsc"]},
            {"name": "typing", "role": "typing-style", "command": ["biome", "lint"]},
            {"name": "format", "role": "format-lint", "command": ["biome", "ci"]},
            {"name": "focused", "role": "focused-tests", "command": ["biome", "lint"]},
            {"name": "tests", "role": "tests", "command": ["node", "test.js"]},
            {
                "name": "dead-code",
                "role": "dead-code-duplicates",
                "command": ["fallow", "--fail-on-issues"],
            },
            {
                "name": "performance",
                "role": "performance",
                "command": ["node", "test.js"],
                "report": {
                    "type": "performance-junit",
                    "path": "coverage/performance.xml",
                },
            },
        ],
    }
    assert gate_config.validate_group(tmp_path, group, set()) == 7
    performance = group["checks"].pop()
    with pytest.raises(ValueError, match="mandatory performance"):
        gate_config.validate_group(tmp_path, group, set())
    group["performance_exception"] = "Reviewed fixture: no product workload."
    assert gate_config.validate_group(tmp_path, group, set()) == 6
    group["checks"].append(performance)
    performance["parallel"] = True
    with pytest.raises(ValueError, match="serially"):
        gate_config.validate_group(tmp_path, group, set())
    performance["parallel"] = False
    report = performance.pop("report")
    with pytest.raises(ValueError, match="supported native report"):
        gate_config.validate_group(tmp_path, group, set())
    performance["report"] = report
    (tmp_path / "package-lock.json").touch()
    with pytest.raises(ValueError, match="Bun is required"):
        gate_config.validate_group(tmp_path, group, set())
    (tmp_path / "package-lock.json").unlink()
    group["checks"][0]["command"] = ["npm", "run", "typecheck"]
    with pytest.raises(ValueError, match="must use Bun"):
        gate_config.validate_group(tmp_path, group, set())
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "packageManager": "bun@1.3.0",
                "scripts": {"typecheck": "bun run unit", "unit": "npx c8 test"},
            }
        )
    )
    group["checks"][0]["command"] = ["bun", "run", "typecheck"]
    with pytest.raises(ValueError, match="must use Bun, not: npx"):
        gate_config.validate_group(tmp_path, group, set())


def test_the_shipped_format_gate_covers_each_installed_workflow() -> None:
    gates = json.loads((SOURCE / "hard-eng.gates.json").read_text())
    named = {check["name"]: check["command"] for check in gates["shared"]}
    installed = set(
        re.findall(
            r"\.github/(?:workflows/)?[\w-]+\.yml",
            (SOURCE / ".hooks/ci_setup.py").read_text(),
        )
    )
    assert ".github/workflows/hard-eng.yml" in installed
    assert ".github/hard-eng.yml" in installed
    for path in installed:
        assert path in named["shipped-format"], path

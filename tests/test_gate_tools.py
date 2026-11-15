"""A required check that writes no report must name the tool of its role."""

import json
import re
import subprocess
from pathlib import Path

import gate_config
import pytest
import reports
import update
from conftest import SOURCE
from dart_boundaries import validate_dart_boundaries
from fallow_report import Report, validate_scanner_command
from gate_config import Group, JsonObject, JsonValue
from project_setup import strict_scanner_flags

from setup import configure_dart_scanner

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
        ("python", "dead-code", ["true"], "vulture"),
        ("python", "dead-code", ["skylos", "src", "--strict"], "vulture"),
        ("python", "dead-code", ["uvx", "skylos@latest", "src", "--json"], "vulture"),
        ("python", "dead-code", ["uvx", "skylos-lint@latest", "--strict"], "vulture"),
        ("python", "lint", ["uvx", "skylos@latest", "--strict"], "ruff check"),
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
        (
            "python",
            "dead-code",
            [
                "bash",
                "-c",
                "shopt -s globstar; exec uvx skylos@latest src/**/*.py --strict",
            ],
        ),
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


def javascript_group() -> Group:
    return {
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


def test_gate_validation_rejects_javascript_package_manager_drift(
    tmp_path: Path,
) -> None:
    """HE-PERFORMANCE-SUITE: a package needs a performance suite or a reviewed exception."""
    (tmp_path / "package.json").write_text('{"packageManager":"bun@1.3.0"}')
    (tmp_path / "bun.lock").touch()
    group = javascript_group()
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


def test_a_react_package_without_its_react_gate_is_refused(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": "bun@1.3.0", "dependencies": {"react": "19"}})
    )
    (tmp_path / "bun.lock").touch()
    group = javascript_group()
    shared = {"lockfiles", "vulnerabilities", "freshness", "security"}
    with pytest.raises(ValueError, match="missing mandatory checks: react;"):
        gate_config.validate_package_services(tmp_path, group, {}, {}, shared)
    group["checks"].append(
        {
            "name": "react-doctor",
            "role": "react",
            "command": [
                "react-doctor",
                "--blocking",
                "warning",
                "--no-respect-inline-disables",
                "--json-out",
                "coverage/react-doctor.json",
            ],
            "report": {"type": "react-doctor", "path": "coverage/react-doctor.json"},
        }
    )
    gate_config.validate_package_services(tmp_path, group, {}, {}, shared)


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


@pytest.mark.parametrize("reports_folder", [False, True])
def test_the_import_order_of_the_coverage_package_does_not_depend_on_the_reports_folder(
    tmp_path: Path, reports_folder: bool
) -> None:
    name = "tests/test_shard_coverage_minimum.py"
    for source in ("pyproject.toml", name):
        (tmp_path / source).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / source).write_text((SOURCE / source).read_text())
    if reports_folder:
        (tmp_path / "coverage").mkdir()
    gates = json.loads((SOURCE / "hard-eng.gates.json").read_text())
    (command,) = (
        check["command"]
        for group in gates["packages"]
        for check in group["checks"]
        if check["name"] == "lint"
    )
    result = subprocess.run(
        [*command[:3], "--select", "I001", name],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout


def clean_typescript_report(health: JsonObject | None) -> JsonObject:
    summary: JsonObject = {"files_analyzed": 4, "functions_analyzed": 3}
    summary |= {"max_cyclomatic_threshold": 20, "max_cognitive_threshold": 15}
    summary |= {"max_crap_threshold": 30.0, "functions_above_threshold": 0}
    summary |= {"severity_critical_count": 0, "severity_high_count": 0}
    summary |= {"severity_moderate_count": 0}
    clean: JsonObject = {"findings": [], "summary": summary}
    check: JsonObject = {"total_issues": 0, "summary": {"total_issues": 0}}
    check["entry_points"] = {"total": 1}
    stats: JsonObject = {"clone_groups": 0, "duplication_percentage": 0}
    groups: list[JsonValue] = []
    stats |= {"total_files": 1, "total_lines": 5, "total_tokens": 30}
    report: JsonObject = {"kind": "combined", "check": check}
    report["dupes"] = {"clone_groups": groups, "stats": stats}
    report["health"] = clean if health is None else {**clean, **health}
    kinds = ("rule-packs-not-configured", "coverage-auto-detected", "shallow-clone")
    kinds += ("change-coupling-skipped", "hotspots-skipped")
    notes: list[JsonValue] = [{"path": ".", "kind": kind} for kind in kinds]
    report["workspace_diagnostics"] = notes
    return report


def test_the_typescript_scanner_gate_fails_complex_and_crap_code(
    tmp_path: Path,
) -> None:
    """The TypeScript Fallow gate asks for health, so it fails the complexity and CRAP code that the Dart gate fails."""
    group = template_group(tmp_path, "javascript")
    (gate,) = [g for g in group["checks"] if g["role"] == "dead-code-duplicates"]
    command = gate["command"]
    assert command[command.index("--only") + 1] == "dead-code,dupes,health"

    old = ["fallow", "--only", "dead-code,dupes", "--fail-on-issues"]
    report: Report = {"type": "fallow", "path": "coverage/fallow.json"}
    with pytest.raises(ValueError, match="health"):
        validate_scanner_command(old, report)
    package: Group = {"path": ".", "checks": [{"name": "scan", "command": [*old]}]}
    strict_scanner_flags(package)
    assert package["checks"][0]["command"] == [*old[:2], "dead-code,dupes,health"] + [
        "--fail-on-issues"
    ]
    validate_scanner_command(package["checks"][0]["command"], report)

    path = tmp_path / "fallow.json"
    path.write_text(json.dumps(clean_typescript_report(None)))
    reports.validate_fallow(path)
    found: JsonObject = {"findings": [{"path": "a.ts", "exceeded": "crap"}]}
    off: JsonObject = {"summary": {"max_crap_threshold": 0}}
    for health in (found, off):
        path.write_text(json.dumps(clean_typescript_report(health)))
        with pytest.raises(ValueError, match="CRAP|complexity"):
            reports.validate_fallow(path)
    for key in (
        "max_cyclomatic_threshold",
        "max_cognitive_threshold",
        "max_crap_threshold",
    ):
        raised = clean_typescript_report(None)
        health = raised["health"]
        assert isinstance(health, dict)
        summary = health["summary"]
        assert isinstance(summary, dict)
        summary[key] = 1000.0
        path.write_text(json.dumps(raised))
        with pytest.raises(ValueError, match=rf"{key} is above"):
            reports.validate_fallow(path)
    skipped = ["fallow", "--skip", "health", "--fail-on-issues"]
    with pytest.raises(ValueError, match="health"):
        validate_scanner_command(skipped, report)


def test_a_dart_scanner_gate_needs_the_fallow_equal_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dart Decimate 0.0.76 fails a CRAP score equal to its limit, so 30 fails what Fallow's 30 fails."""
    for folder in ("domain", "ui"):
        (tmp_path / "lib" / folder).mkdir(parents=True)
        (tmp_path / "lib" / folder / "page.dart").write_text("void main() {}\n")
    boundaries: list[JsonValue] = [{"from": "lib/domain", "disallow": "lib/ui"}]
    command = ["dart-decimate", "check", ".", "--strict"]

    def check_with(health: JsonObject) -> None:
        config: JsonObject = {"boundaries": boundaries, "health": health}

        def native_config(*_args: object, **_kwargs: object) -> str:
            return json.dumps({"config": config})

        monkeypatch.setattr(subprocess, "check_output", native_config)
        validate_dart_boundaries(command, tmp_path, 5)

    refused: list[JsonObject] = [{}, {"max_crap": None}, {"max_crap": 31}]
    refused.append({"max_crap": 0})
    for health in refused:
        with pytest.raises(ValueError, match=r'"health": \{"max_crap": 30\}'):
            check_with(health)
    for limit in (30, 12):
        check_with({"max_crap": limit})

    changes: dict[str, str] = {}
    configure_dart_scanner(tmp_path, tmp_path, changes)
    written = json.loads(changes[".dart-decimaterc.json"])
    assert written["health"] == {"max_crap": 30}
    starter = SOURCE / ".agents/starters/flutter/.dart-decimaterc.json"
    assert json.loads(starter.read_text())["health"] == {"max_crap": 30}

"""The combined Fallow scan checks the boundary rules, so no separate boundaries gate is mandatory and Hard Eng retires the one it added."""

import json
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import Gate, validate_required_checks
from test_setup import repository, snapshot


@pytest.mark.parametrize(
    "source",
    ["src/app.ts", "src/app.tsx", "src/app.mts", "src/app.cts", "src/app.js"],
)
def test_a_typescript_package_needs_no_separate_boundary_gate(
    installer: ModuleType, tmp_path: Path, source: str
) -> None:
    """The combined Fallow scan, which every JavaScript package must run, checks the boundary rules."""
    repository(tmp_path)
    target = tmp_path / source
    target.parent.mkdir()
    target.write_text("export const value = 1;\n")
    config = installer.gate_config(tmp_path)
    package = config["packages"][0]
    assert not [gate for gate in package["checks"] if gate.get("role") == "boundaries"]
    assert any(gate.get("role") == "dead-code-duplicates" for gate in package["checks"])
    validate_required_checks(tmp_path, config)


GENERATED_BOUNDARY = {
    "name": "lint:boundaries",
    "role": "boundaries",
    "command": ["bun", "run", "lint:boundaries"],
}
OLD_STARTER = '{\n\t"scripts": {\n\t\t"lint:boundaries": "fallow architecture --fail-on-issues"\n\t}\n}\n'


def with_boundary_gate(
    installer: ModuleType, root: Path, manifest: str, extra: Gate | None
) -> dict[str, list[dict[str, object]]]:
    repository(root)
    (root / "package.json").write_text(manifest)
    (root / "app.ts").write_text("export const value = 1;\n")
    config = installer.gate_config(root)
    config["packages"][0]["checks"].append(extra or GENERATED_BOUNDARY)
    (root / "hard-eng.gates.json").write_text(json.dumps(config))
    installer.install(root)
    return json.loads((root / "hard-eng.gates.json").read_text())["packages"][0]


def test_an_update_removes_the_boundary_gate_and_starter_script_it_added(
    installer: ModuleType, tmp_path: Path
) -> None:
    """Hard Eng added a `lint:boundaries` gate and an old starter script; both go, and a second update changes nothing."""
    package = with_boundary_gate(installer, tmp_path, OLD_STARTER, None)
    assert not any(gate.get("role") == "boundaries" for gate in package["checks"])
    assert "lint:boundaries" not in (tmp_path / "package.json").read_text()
    json.loads((tmp_path / "package.json").read_text())
    before = snapshot(tmp_path)
    installer.install(tmp_path)
    assert snapshot(tmp_path) == before


def test_an_update_keeps_a_project_own_boundary_gate(
    installer: ModuleType, tmp_path: Path
) -> None:
    own: Gate = {
        "name": "project-architecture",
        "role": "boundaries",
        "command": ["bun", "run", "project-architecture"],
    }
    package = with_boundary_gate(installer, tmp_path, '{"scripts": {}}', own)
    assert own in package["checks"]
    custom = '{"scripts": {"lint:boundaries": "node check-boundaries.mjs"}}'
    package = with_boundary_gate(installer, tmp_path / "again", custom, None)
    assert GENERATED_BOUNDARY in package["checks"]
    assert "node check-boundaries.mjs" in (tmp_path / "again/package.json").read_text()


def test_a_boundaries_script_makes_no_gate_mandatory(
    installer: ModuleType, tmp_path: Path
) -> None:
    """The mandatory-check message and the boundaries refusal must never ask for what the other refuses."""
    repository(tmp_path)
    (tmp_path / "package.json").write_text(OLD_STARTER)
    (tmp_path / "app.ts").write_text("export const value = 1;\n")
    config = installer.gate_config(tmp_path)
    assert not any(
        gate.get("role") == "boundaries" for gate in config["packages"][0]["checks"]
    )
    validate_required_checks(tmp_path, config)

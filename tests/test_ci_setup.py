"""Generated job deadlines honor the consumer's existing shipping budget."""

import json
from pathlib import Path

import pytest
import yaml
from gate_config import GateConfig
from project_setup import configure_ci
from shipping import ShippingError

SOURCE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("seconds,minutes", [(600, 10), (601, 11), (60, 1), (None, 3)])
def test_generated_ci_timeout(
    tmp_path: Path, seconds: int | None, minutes: int
) -> None:
    config: GateConfig = {"packages": [], "shared": []}
    if seconds is not None:
        config["shipping"] = {
            "base": "main",
            "checks": ["hard-eng"],
            "ui_paths": [],
            "ci_seconds": seconds,
            "pre_push_seconds": 600,
            "delivery": [],
        }
    (tmp_path / "hard-eng.gates.json").write_text(json.dumps(config))
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    workflow = changes[".github/workflows/hard-eng.yml"]
    assert yaml.safe_load(workflow)["jobs"]["hard-eng"]["timeout-minutes"] == minutes
    assert '--base "$BASE_SHA"' in workflow


def test_existing_workflow_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    content = "# Project-owned workflow\njobs:\n  custom:\n    timeout-minutes: 17\n"
    path.write_text(content)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    assert changes == {}
    assert path.read_text() == content


@pytest.mark.parametrize("named", [False, True])
def test_known_action_pins_migrate_without_replacing_custom_workflow(
    tmp_path: Path,
    named: bool,
) -> None:
    path = tmp_path / ".github/workflows/hard-eng.yml"
    path.parent.mkdir(parents=True)
    old = (
        (SOURCE / ".github/workflows/hard-eng.yml")
        .read_text()
        .replace(
            "3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1",
            "fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09 # v5",
        )
        .replace(
            "703c52620218391530e48b9e8870d5c0082e1b9b # v2.1.0",
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c # v2.0.0",
        )
    )
    custom = "# Project-owned note\n" + old.replace(
        "timeout-minutes: 3", "timeout-minutes: 10"
    )
    if named:
        custom = custom.replace("- uses:", "- name: Configure tool\n        uses:")
    path.write_text(custom)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    expected = "# Project-owned note\n" + (
        SOURCE / ".github/workflows/hard-eng.yml"
    ).read_text().replace("timeout-minutes: 3", "timeout-minutes: 10")
    if named:
        expected = expected.replace("- uses:", "- name: Configure tool\n        uses:")
    assert changes[str(path.relative_to(tmp_path))] == expected
    path.write_text(expected)
    repeated: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, repeated)
    assert repeated == {}
    path.write_text(
        custom.replace("fbc6f3992d24b796d5a048ff273f7fcc4a7b6c09", "a" * 40).replace(
            "c9883cc79df532ad1a7b81bf9ab944ceb090d65c", "b" * 40
        )
    )
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, repeated)
    assert repeated == {}


def test_invalid_shipping_budget_is_rejected(tmp_path: Path) -> None:
    (tmp_path / "hard-eng.gates.json").write_text('{"shipping": {"ci_seconds": 0}}')
    with pytest.raises(ShippingError):
        configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, {})


def test_dart_workflow_uses_packaged_scanner_without_rust(tmp_path: Path) -> None:
    (tmp_path / "pubspec.yaml").write_text("name: fixture\ndependencies: {}\n")
    config: GateConfig = {
        "packages": [{"path": ".", "language": "dart", "checks": []}],
        "shared": [],
    }
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, config, changes)
    workflow = changes[".github/workflows/hard-eng.yml"]
    assert "dart@latest" in workflow
    assert "rust@latest" not in workflow

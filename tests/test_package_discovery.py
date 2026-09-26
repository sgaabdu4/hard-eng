"""Keep deployment copies out of package ownership without hiding real owners."""

import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from gate_config import (
    package_manifests,
    validate_manifest_groups,
    validate_required_checks,
)


@pytest.mark.parametrize("manifest", ["pubspec.yaml", "package.json", "pyproject.toml"])
@pytest.mark.parametrize("attribute", ["linguist-generated", "linguist-vendored"])
def test_generated_package_ownership(
    tmp_path: Path, manifest: str, attribute: str
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    files = [tmp_path / owner / manifest for owner in ("canonical", "copy", "real")]
    for path in files:
        path.parent.mkdir()
        path.touch()
    attributes = tmp_path / ".gitattributes"
    attributes.write_text(f"copy/** {attribute}\nreal/** {attribute}=false\n")
    manifests = package_manifests(tmp_path, files)
    assert {owner for owner, _ in manifests} == {"canonical", "real"}
    with pytest.raises(ValueError, match="missing from gate configuration"):
        validate_manifest_groups(tmp_path, {"packages": [], "shared": []}, manifests)
    attributes.unlink()
    assert {owner for owner, _ in package_manifests(tmp_path, files)} == {
        "canonical",
        "copy",
        "real",
    }


def test_fixture_manifest_ownership(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    root = tmp_path / "pubspec.yaml"
    fixture = tmp_path / "tests/fixtures/example/pubspec.yaml"
    fixture.parent.mkdir(parents=True)
    root.write_text("name: root\n")
    fixture.write_text("name: example_fixture\n")

    def owners() -> set[str]:
        return {owner for owner, _ in package_manifests(tmp_path, [root, fixture])}

    assert owners() == {"."}
    root.write_text("name: root\nworkspace: [tests/fixtures/example]\n")
    assert owners() == {".", "tests/fixtures/example"}
    root.write_text("name: root\n")
    (fixture.parent / "pubspec.lock").touch()
    assert owners() == {".", "tests/fixtures/example"}


def test_test_support_package_keeps_only_dependency_checks(
    installer: ModuleType, tmp_path: Path
) -> None:
    """A committed test runner package is gated with its parent, not as a product."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib/app.dart").write_text("int one() => 1;\n")
    runner = tmp_path / "test/browser_runner"
    runner.mkdir(parents=True)
    for directory in (tmp_path, runner):
        (directory / "pubspec.yaml").write_text(f"name: {directory.name}_fixture\n")
        (directory / "pubspec.lock").touch()
    config = installer.gate_config(tmp_path)
    support = next(
        group for group in config["packages"] if group["path"] == "test/browser_runner"
    )
    assert "language" not in support and "sources" not in support
    assert [gate["role"] for gate in support["checks"]] == [
        "vulnerabilities",
        "lockfiles",
    ]
    assert support["checks"][1]["command"] == [
        "dart",
        "pub",
        "get",
        "--enforce-lockfile",
    ]
    validate_required_checks(tmp_path, config)
    support["sources"] = ["lib"]
    with pytest.raises(ValueError, match="package language must be dart"):
        validate_required_checks(tmp_path, config)
    config["packages"].remove(support)
    with pytest.raises(ValueError, match="test-support package without language"):
        validate_required_checks(tmp_path, config)


def test_test_support_needs_a_covering_dart_parent(
    installer: ModuleType, tmp_path: Path
) -> None:
    """Without a parent Dart package nothing else analyzes a test-path package."""
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    runner = tmp_path / "tests/runner"
    member = tmp_path / "tests/runner/packages/member"
    member.mkdir(parents=True)
    (runner / "pubspec.yaml").write_text(
        "name: runner_fixture\nworkspace: [packages/member]\n"
    )
    (runner / "pubspec.lock").touch()
    (member / "pubspec.yaml").write_text(
        "name: member_fixture\nresolution: workspace\n"
    )
    (member / "lib").mkdir()
    (member / "lib/member.dart").write_text("int one() => 1;\n")
    standalone = installer.gate_config(tmp_path)
    assert {
        group["path"]: group.get("language") for group in standalone["packages"]
    } == {"tests/runner": None, "tests/runner/packages/member": "dart"}
    (tmp_path / "pubspec.yaml").write_text("name: app_fixture\n")
    (tmp_path / "pubspec.lock").touch()
    nested = installer.gate_config(tmp_path)
    validate_required_checks(tmp_path, nested)
    assert {group["path"]: group.get("language") for group in nested["packages"]} == {
        ".": "dart",
        "tests/runner": None,
        "tests/runner/packages/member": None,
    }

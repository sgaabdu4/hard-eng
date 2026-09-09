"""Repository configuration and downloaded-tool integrity contracts."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest

from hard_eng import common, config, tools
from hard_eng.common import GateError, Json


def manifest(root: Path) -> Json:
    (root / "app.py").write_text("answer = 42\n")
    checks: list[Json] = []
    for role in sorted(config.LANGUAGE_ROLES["python"]):
        item: Json = {"name": role, "role": role, "command": ["python3", "check.py"]}
        if role == "tests":
            item["report"] = {"type": "python-tests", "tests": "junit.xml", "coverage": "coverage.json"}
        checks.append(item)
    shared = [{"name": role, "role": role, "command": [role]} for role in sorted(config.shared_roles(root))]
    return {
        "version": 1,
        "packages": [
            {"name": "app", "path": ".", "language": "python", "sources": ["app.py"], "checks": checks}
        ],
        "shared": shared,
    }


def test_valid_manifest_loads_and_missing_required_gate_fails(tmp_path: Path) -> None:
    data = manifest(tmp_path)
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    loaded = config.load(tmp_path)
    assert loaded.packages[0].name == "app"
    assert {gate.role for gate in loaded.shared} == config.shared_roles(tmp_path)
    empty_checks: list[Json] = []
    data["shared"] = empty_checks
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    with pytest.raises(GateError, match="Missing shared checks"):
        config.load(tmp_path)


@pytest.mark.parametrize(
    "field,value",
    [("language", "ruby"), ("sources", []), ("depends_on", ["missing"]), ("checks", []), ("name", "")],
)
def test_invalid_package_contract_fails(tmp_path: Path, field: str, value: object) -> None:
    data = manifest(tmp_path)
    package = common.object_value(common.array(data["packages"], "packages")[0], "package")
    package[field] = value
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    with pytest.raises(GateError):
        config.load(tmp_path)


def test_workflow_repository_requires_both_checks(tmp_path: Path) -> None:
    (tmp_path / ".github/workflows").mkdir(parents=True)
    assert {"workflows", "workflow-security"} <= config.shared_roles(tmp_path)


def test_history_scan_opt_out_preserves_current_file_scan_and_default(tmp_path: Path) -> None:
    data = manifest(tmp_path)
    data["shared"] = [
        item
        for item in common.array(data["shared"], "shared")
        if common.object_value(item, "check")["role"] != "secrets-history"
    ]
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    with pytest.raises(GateError, match="secrets-history"):
        config.load(tmp_path)
    data["scan_git_history"] = False
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    assert "secrets-files" in {check.role for check in config.load(tmp_path).shared}
    data["shared"] = [
        item
        for item in common.array(data["shared"], "shared")
        if common.object_value(item, "check")["role"] != "secrets-files"
    ]
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    with pytest.raises(GateError, match="secrets-files"):
        config.load(tmp_path)


def test_react_and_build_cannot_omit_their_checks(tmp_path: Path) -> None:
    data: Json = {
        "name": "app",
        "path": ".",
        "language": "javascript",
        "sources": ["app.ts"],
        "react": True,
        "build": True,
        "checks": [
            {"name": role, "role": role, "command": ["npm", "test"]}
            for role in config.LANGUAGE_ROLES["javascript"]
        ],
    }
    (tmp_path / "app.ts").write_text("export const n = 1;\n")
    with pytest.raises(GateError, match="missing checks"):
        config.package(data, tmp_path)


def test_duplicate_check_names_cannot_hide_missing_results(tmp_path: Path) -> None:
    data = manifest(tmp_path)
    shared = common.array(data["shared"], "shared")
    shared.append(shared[0])
    common.write_json(tmp_path / "hard-eng.gates.json", data)
    with pytest.raises(GateError, match="Check names must be unique"):
        config.load(tmp_path)


def test_binary_install_keeps_archive_paths_inside_its_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools, "state_dir", Path)

    def asset_name(_name: str, _version: str) -> str:
        return "tool.tar.gz"

    monkeypatch.setattr(tools, "asset_name", asset_name)
    payload = io.BytesIO()
    source = tmp_path / "payload"
    source.write_bytes(b"tool")
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        # Only the requested regular executable is read; archive paths are never extracted.
        archive.add(source, arcname="../../gitleaks", recursive=False)
    body = payload.getvalue()

    def download(_url: str) -> bytes:
        return body

    monkeypatch.setattr(tools, "download", download)
    asset = {
        "name": "tool.tar.gz",
        "browser_download_url": "https://example.test/tool",
    }
    result = Path(tools.binary(tmp_path, "gitleaks", "v1", {"assets": [asset]}))
    assert result.read_bytes() == b"tool"
    assert result.is_relative_to(tmp_path / "tools/gitleaks/v1")
    assert not (tmp_path / "gitleaks").exists()

"""Service selection and preservation across native harness configuration."""

import json
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
from test_setup import repository


def executable_launcher(root: Path, relative: str) -> str:
    launcher = root / relative
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text("#!/bin/sh\nexit 0\n")
    launcher.chmod(0o755)
    return "./" + relative


def appwrite_project(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository(root)
    (root / "app.py").write_text("import appwrite\n")
    monkeypatch.delenv("APPWRITE_ENDPOINT", raising=False)


def assert_preserved_pending_stdio_server(
    target: Path,
    original: str,
    changes: dict[str, str],
    service: str,
    command: str,
) -> None:
    assert target.read_text() == original
    assert json.loads(changes[".mcp.json"])["mcpServers"][service] == {
        "command": command
    }
    assert service not in json.loads(changes[".github/mcp.json"])["mcpServers"]
    assert service not in tomllib.loads(changes[".codex/config.toml"])["mcp_servers"]


def test_appwrite_unresolved_setup_installs_framework_and_reports_pending(
    installer: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    installer.install(tmp_path)
    assert (
        "MCP setup pending: Appwrite needs the deployed endpoint"
        in capsys.readouterr().out
    )
    assert (tmp_path / ".hooks/hard-eng.py").is_file()
    assert (
        "appwrite" not in json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
    )


def test_mcp_setup_leaves_unmanaged_vscode_jsonc_untouched(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    target = tmp_path / ".vscode/mcp.json"
    target.parent.mkdir()
    original = '{\n  // VS Code MCP configuration\n  "servers": {}\n}\n'
    target.write_text(original)

    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)

    assert target.read_text() == original
    assert ".vscode/mcp.json" not in changes


@pytest.mark.parametrize(
    "host", ["sentry.io", "de.sentry.io", "us.sentry.io", "sentry.example.test"]
)
def test_sentry_host_selection_and_repeat_setup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, host: str
) -> None:
    from mcp_setup import sentry_server

    monkeypatch.delenv("SENTRY_HOST", raising=False)
    monkeypatch.delenv("SENTRY_MCP_URL", raising=False)
    assert sentry_server(tmp_path) is None
    monkeypatch.setenv("SENTRY_HOST", host)
    cloud = host.endswith("sentry.io")
    if cloud:
        monkeypatch.setenv("SENTRY_MCP_URL", "https://mcp.sentry.dev/mcp/example/app")
    if not cloud:
        assert sentry_server(tmp_path) is None
        executable_launcher(tmp_path, "scripts/sentry-mcp")
    server = sentry_server(tmp_path)
    assert server == (
        {"url": "https://mcp.sentry.dev/mcp/example/app"}
        if cloud
        else {"command": "./scripts/sentry-mcp"}
    )
    (tmp_path / ".mcp.json").write_text(json.dumps({"mcpServers": {"sentry": server}}))
    monkeypatch.delenv("SENTRY_HOST")
    monkeypatch.delenv("SENTRY_MCP_URL", raising=False)
    assert sentry_server(tmp_path) == server


def test_legacy_dart_mcp_requires_targeted_migration(
    installer: ModuleType, tmp_path: Path
) -> None:
    repository(tmp_path)
    target = tmp_path / ".mcp.json"
    original = json.dumps(
        {
            "mcpServers": {
                "dart": {"command": "dart", "args": ["run", "dart_mcp_server@"]}
            }
        }
    )
    target.write_text(original)
    with pytest.raises(ValueError, match="Legacy Dart MCP entry"):
        installer.install(tmp_path)
    assert target.read_text() == original
    assert not (tmp_path / ".hooks").exists()


@pytest.mark.parametrize("cloud", [True, False])
def test_appwrite_target_survives_repeat_setup_without_reasking(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cloud: bool
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    monkeypatch.setenv(
        "APPWRITE_ENDPOINT",
        "https://cloud.appwrite.io/v1" if cloud else "https://backend.example.test/v1",
    )
    if not cloud:
        installer.install(tmp_path)
        assert (
            "appwrite"
            not in json.loads((tmp_path / ".mcp.json").read_text())["mcpServers"]
        )
        executable_launcher(tmp_path, "scripts/appwrite-mcp")
    installer.install(tmp_path)
    names = (".mcp.json", ".github/mcp.json", ".codex/config.toml")
    before = {name: (tmp_path / name).read_bytes() for name in names}
    monkeypatch.delenv("APPWRITE_ENDPOINT")
    installer.install(tmp_path)
    assert before == {name: (tmp_path / name).read_bytes() for name in names}
    settings = tomllib.loads(before[".codex/config.toml"].decode())["mcp_servers"][
        "appwrite"
    ]
    assert settings == (
        {"url": "https://mcp.appwrite.io/"}
        if cloud
        else {"command": "./scripts/appwrite-mcp"}
    )


def test_appwrite_reuses_existing_custom_launcher_without_credentials(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    command = executable_launcher(tmp_path, "scripts/custom-appwrite-mcp")
    existing = {"command": command}
    target = tmp_path / ".mcp.json"
    original = json.dumps({"mcpServers": {"appwrite": existing}})
    target.write_text(original)

    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)

    assert target.read_text() == original
    pointer = {"command": command}
    for name in (".mcp.json", ".github/mcp.json"):
        assert json.loads(changes[name])["mcpServers"]["appwrite"] == pointer
    assert (
        tomllib.loads(changes[".codex/config.toml"])["mcp_servers"]["appwrite"]
        == pointer
    )


def test_appwrite_launcher_credentials_require_migration_before_reuse(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    command = executable_launcher(tmp_path, "scripts/custom-appwrite-mcp")
    target = tmp_path / ".mcp.json"
    original = json.dumps(
        {
            "mcpServers": {
                "appwrite": {
                    "command": command,
                    "args": ["--credential", "synthetic"],
                    "env": {"APPWRITE_API_KEY": "synthetic-secret"},
                }
            }
        }
    )
    target.write_text(original)

    changes: dict[str, str] = {}
    with pytest.raises(ValueError, match="secret owner"):
        installer.configure_mcp(tmp_path, changes)

    assert changes == {}
    assert target.read_text() == original


@pytest.mark.parametrize("external_kind", ["parent", "symlink"])
def test_appwrite_does_not_reuse_external_launcher(
    installer: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    external_kind: str,
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    external_name = f"{tmp_path.name}-appwrite-mcp"
    external = tmp_path.parent / external_name
    executable_launcher(tmp_path.parent, external_name)
    if external_kind == "parent":
        pointer = f"./../{external_name}"
    else:
        launcher = tmp_path / "scripts/external-appwrite-mcp"
        launcher.parent.mkdir()
        launcher.symlink_to(external)
        pointer = "./scripts/external-appwrite-mcp"
    target = tmp_path / ".mcp.json"
    original = json.dumps({"mcpServers": {"appwrite": {"command": pointer}}})
    target.write_text(original)

    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)

    assert_preserved_pending_stdio_server(
        target, original, changes, "appwrite", pointer
    )
    assert (
        "MCP setup pending: Appwrite needs the deployed endpoint"
        in capsys.readouterr().out
    )


def test_appwrite_normalizes_existing_cloud_url_for_missing_hosts(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    target = tmp_path / ".mcp.json"
    original = json.dumps(
        {"mcpServers": {"appwrite": {"url": "https://mcp.appwrite.io"}}}
    )
    target.write_text(original)

    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)

    assert target.read_text() == original
    assert json.loads(changes[".mcp.json"])["mcpServers"]["appwrite"] == {
        "url": "https://mcp.appwrite.io"
    }
    assert json.loads(changes[".github/mcp.json"])["mcpServers"]["appwrite"] == {
        "type": "http",
        "url": "https://mcp.appwrite.io/",
    }
    assert tomllib.loads(changes[".codex/config.toml"])["mcp_servers"]["appwrite"] == {
        "url": "https://mcp.appwrite.io/"
    }


def test_appwrite_rejects_mixed_cloud_and_local_existing_targets_before_writes(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    command = executable_launcher(tmp_path, "scripts/custom-appwrite-mcp")
    cloud = tmp_path / ".mcp.json"
    local = tmp_path / ".github/mcp.json"
    local.parent.mkdir()
    cloud.write_text(
        json.dumps({"mcpServers": {"appwrite": {"url": "https://mcp.appwrite.io/"}}})
    )
    local.write_text(json.dumps({"mcpServers": {"appwrite": {"command": command}}}))
    originals = {path: path.read_bytes() for path in (cloud, local)}

    with pytest.raises(ValueError, match="conflicts with Cloud OAuth"):
        installer.install(tmp_path)

    assert {path: path.read_bytes() for path in originals} == originals
    assert not (tmp_path / ".hooks").exists()


def test_sentry_unsupported_stdio_target_stays_pending_for_missing_hosts(
    installer: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository(tmp_path)
    (tmp_path / "app.py").write_text("import sentry_sdk\n")
    monkeypatch.delenv("SENTRY_HOST", raising=False)
    monkeypatch.delenv("SENTRY_MCP_URL", raising=False)
    target = tmp_path / ".mcp.json"
    original = json.dumps({"mcpServers": {"sentry": {"command": "sentry-mcp"}}})
    target.write_text(original)

    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)

    assert_preserved_pending_stdio_server(
        target, original, changes, "sentry", "sentry-mcp"
    )
    assert "MCP setup pending: existing Sentry MCP target" in capsys.readouterr().out

    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "sentry": {
                        "command": "pnpm",
                        "args": ["dlx", "sentry-mcp"],
                        "env": {"SENTRY_AUTH_TOKEN": "synthetic-secret"},
                    }
                }
            }
        )
    )
    from mcp_setup import sentry_server

    assert sentry_server(tmp_path) is None
    assert "MCP setup pending: existing Sentry MCP target" in capsys.readouterr().out


def test_legacy_appwrite_cloud_conflict_is_preserved(
    installer: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    appwrite_project(tmp_path, monkeypatch)
    target = tmp_path / ".mcp.json"
    original = json.dumps(
        {
            "mcpServers": {
                "appwrite": {"command": "uvx", "args": ["mcp-server-appwrite"]}
            }
        }
    )
    target.write_text(original)
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://cloud.appwrite.io/v1")
    with pytest.raises(ValueError, match="conflicts with Cloud OAuth"):
        installer.install(tmp_path)
    assert target.read_text() == original
    assert not (tmp_path / ".hooks").exists()


@pytest.mark.parametrize(
    "source,expected",
    [
        ("", set()),
        ("import 'dart:io';", {"dart"}),
        ("import 'package:flutter/material.dart';", {"dart"}),
        ("import 'package:marionette_flutter/marionette_flutter.dart';", {"dart"}),
        (
            "import 'package:marionette_flutter/marionette_flutter.dart';\nMarionetteBinding.ensureInitialized();",
            {"dart", "marionette"},
        ),
        ("import 'package:appwrite/appwrite.dart';", {"dart", "appwrite"}),
        ("import 'package:sentry_flutter/sentry_flutter.dart';", {"dart", "sentry"}),
        (
            (
                "import 'package:flutter/material.dart';\n"
                "import 'package:appwrite/appwrite.dart';\n"
                "import 'package:sentry_flutter/sentry_flutter.dart';"
            ),
            {"dart", "appwrite", "sentry"},
        ),
    ],
)
def test_installer_registers_only_detected_service_mcps(
    installer: ModuleType,
    tmp_path: Path,
    source: str,
    expected: set[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository(tmp_path)
    (tmp_path / "app.dart").write_text(source)
    monkeypatch.setenv("APPWRITE_ENDPOINT", "https://fra.cloud.appwrite.io/v1")
    monkeypatch.setenv("SENTRY_HOST", "sentry.io")
    monkeypatch.setenv("SENTRY_MCP_URL", "https://mcp.sentry.dev/mcp/example/app")
    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)
    optional = {"sentry", "appwrite", "dart", "marionette"}
    for name in (".mcp.json", ".github/mcp.json"):
        servers = json.loads(changes[name])["mcpServers"]
        assert servers.keys() & optional == expected
        if "dart" in expected:
            assert servers["dart"] == {
                "command": "dart",
                "args": ["mcp-server"],
            }
        if "marionette" in expected:
            assert servers["marionette"] == {
                "command": "dart",
                "args": ["run", "marionette_mcp@"],
            }
    servers = tomllib.loads(changes[".codex/config.toml"])["mcp_servers"]
    assert servers.keys() & optional == expected
    for service in expected & {"dart", "marionette"}:
        assert (
            servers[service] == json.loads(changes[".mcp.json"])["mcpServers"][service]
        )
    if "appwrite" in expected:
        assert servers["appwrite"] == {"url": "https://mcp.appwrite.io/"}


@pytest.mark.parametrize(
    "service", ["sentry", "dart", "marionette", "context-mode", "codebase-memory-mcp"]
)
def test_installer_preserves_existing_service_mcp_configuration(
    installer: ModuleType, tmp_path: Path, service: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository(tmp_path)
    monkeypatch.delenv("SENTRY_HOST", raising=False)
    monkeypatch.setenv("SENTRY_MCP_URL", "https://mcp.sentry.dev/mcp/example/app")
    (tmp_path / "app.py").write_text("import sentry_sdk\n")
    (tmp_path / "app.dart").write_text("import 'package:flutter/material.dart';\n")
    existing = (
        {"url": "https://mcp.sentry.dev/mcp/example/app"}
        if service == "sentry"
        else {"command": service}
    )
    for name in (".mcp.json", ".github/mcp.json"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"mcpServers": {service: existing}}))
    path = tmp_path / ".codex/config.toml"
    path.parent.mkdir()
    path.write_text(
        f"[mcp_servers.{service}]\n"
        + "".join(f"{key} = {json.dumps(value)}\n" for key, value in existing.items())
    )
    changes: dict[str, str] = {}
    installer.configure_mcp(tmp_path, changes)
    for name in (".mcp.json", ".github/mcp.json"):
        assert json.loads(changes[name])["mcpServers"][service] == existing
    assert (
        tomllib.loads(changes[".codex/config.toml"])["mcp_servers"][service] == existing
    )


def test_sentry_reuses_single_custom_launcher_without_copying_secrets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp_setup import sentry_server

    monkeypatch.delenv("SENTRY_HOST", raising=False)
    monkeypatch.delenv("SENTRY_MCP_URL", raising=False)
    config = {"command": executable_launcher(tmp_path, "observability")}
    target = tmp_path / ".mcp.json"
    target.write_text(json.dumps({"mcpServers": {"sentry": config}}))
    assert sentry_server(tmp_path) == config
    target.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "sentry": {
                        **config,
                        "env": {"SENTRY_ACCESS_TOKEN": "synthetic-secret"},
                    }
                }
            }
        )
    )
    with pytest.raises(ValueError, match="secret owner"):
        sentry_server(tmp_path)


def test_sentry_reuses_project_scope_and_rejects_conflicting_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mcp_setup import sentry_server

    monkeypatch.delenv("SENTRY_HOST", raising=False)
    monkeypatch.delenv("SENTRY_MCP_URL", raising=False)
    target = tmp_path / ".mcp.json"
    config = {"url": "https://mcp.sentry.dev/mcp/example/app"}
    original = json.dumps({"mcpServers": {"sentry": config}})
    target.write_text(original)
    assert sentry_server(tmp_path) == config
    monkeypatch.setenv("SENTRY_MCP_URL", "https://mcp.sentry.dev/mcp/different/app")
    with pytest.raises(ValueError, match="Conflicting Sentry"):
        sentry_server(tmp_path)
    assert target.read_text() == original

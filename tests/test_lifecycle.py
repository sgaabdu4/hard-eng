"""Readiness must block edits while leaving diagnosis and honest stops possible."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from hard_eng import agents, common, hooks, integrations, mcp, tools
from hard_eng.common import GateError, Json


@pytest.fixture
def project(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    common.write_json(tmp_path / "hard-eng.gates.json", {"services": {}})
    return tmp_path


def event(name: str, arguments: Json, response: Json | None = None) -> Json:
    return {
        "session_id": "readiness-test",
        "tool_name": name,
        "tool_input": arguments,
        "tool_response": response or {},
    }


def test_failed_start_blocks_edits_but_allows_setup_repair(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(_root: Path) -> str:
        raise GateError("MCP unavailable")

    monkeypatch.setattr(hooks, "session", fail)
    hooks.handle(project, "codex", "SessionStart", {"session_id": "readiness-test"})
    blocked = hooks.handle(
        project, "codex", "PreToolUse", event("Write", {"file_path": str(project / "app.py")})
    )
    assert "deny" in json.dumps(blocked)
    allowed = hooks.handle(
        project, "codex", "PreToolUse", event("Write", {"file_path": str(project / "hard-eng.gates.json")})
    )
    assert allowed == {}
    assert hooks.repair_command(project, "python3 .agents/hard-eng/bin/hard-eng session")
    assert not hooks.repair_command(project, "python3 .agents/hard-eng/bin/hard-eng session; rm app.py")
    blocked = hooks.handle(project, "copilot", "PreToolUse", event("mcp__appwrite__create_document", {}))
    assert blocked["permissionDecision"] == "deny"
    (project / "hard-eng.gates.json").write_text("broken JSON")
    assert hooks.repair_call(project, event("Write", {"file_path": str(project / "hard-eng.gates.json")}))


def test_active_agent_requires_correct_repository_and_index_before_edits(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def ready(_root: Path) -> str:
        return "ready"

    monkeypatch.setattr(hooks, "session", ready)
    hooks.handle(project, "claude", "SessionStart", {"session_id": "readiness-test"})
    probes = [
        event(
            "mcp__context_mode__ctx_execute",
            {"cwd": str(project), "code": "git rev-parse --show-toplevel"},
            {"text": str(project)},
        ),
        event(
            "mcp__codebase_memory__index_repository",
            {"repo_path": str(project)},
            {"structuredContent": {"status": "indexed", "project": "correct-project"}},
        ),
        event(
            "mcp__codebase_memory__get_graph_schema", {"project": "wrong-project"}, {"node_labels": ["File"]}
        ),
    ]
    for probe in probes:
        hooks.handle(project, "claude", "PostToolUse", probe)
    edit = event("Edit", {"file_path": str(project / "app.py")})
    assert "deny" in json.dumps(hooks.handle(project, "claude", "PreToolUse", edit))
    probes[-1]["tool_input"] = {"project": "correct-project"}
    hooks.handle(project, "claude", "PostToolUse", probes[-1])
    assert hooks.handle(project, "claude", "PreToolUse", edit) == {}


def test_gate_failure_blocks_once_and_questions_remain_possible(project: Path) -> None:
    state: Json = {"changed": True, "ready": True}
    message, blocked = hooks.dispatch(project, state, "Stop", {})
    assert blocked and "did not pass" in message
    assert hooks.dispatch(project, state, "Stop", {"stop_hook_active": True}) == ("", False)
    hooks.dispatch(project, state, "UserPromptSubmit", {})
    assert hooks.dispatch(project, state, "Stop", {}) == ("", False)


def test_repaired_startup_requires_fresh_readiness_and_active_probes(
    project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state: Json = {"ready": False, "error": "MCP unavailable"}
    repair = event("exec_command", {"cmd": "python3 .agents/hard-eng/bin/hard-eng session"})

    def unavailable(_root: Path) -> str:
        raise GateError("still unavailable")

    def repaired(_root: Path) -> str:
        return "repaired"

    monkeypatch.setattr(hooks, "session", unavailable)
    hooks.dispatch(project, state, "PostToolUse", repair)
    assert state["ready"] is False
    assert hooks.dispatch(project, state, "PreToolUse", event("Edit", {"path": "app.py"}))[1]
    monkeypatch.setattr(hooks, "session", repaired)
    hooks.dispatch(project, state, "PostToolUse", repair)
    assert state == {"ready": True, "changed": False, "pending": dict.fromkeys(mcp.SERVERS, True)}
    assert hooks.dispatch(project, state, "PreToolUse", event("Edit", {"path": "app.py"}))[1]
    assert not hooks.repair_command(
        project, "python3 .agents/hard-eng/bin/hard-eng session --help", session_only=True
    )


@pytest.mark.parametrize("agent", agents.AGENTS)
def test_agent_configuration_preserves_existing_settings_and_is_repeatable(project: Path, agent: str) -> None:
    common.write_json(project / ".mcp.json", {"mcpServers": {"existing": {"command": "keep"}}})
    common.write_file(
        project / ".codex/config.toml", 'model = "keep-model"\n[features]\nkeep_feature = true\n'
    )
    common.write_json(project / ".claude/settings.json", {"permissions": {"allow": ["Read"]}})
    agents.configure(project, agent)
    agents.configure(project, agent)
    codex = tomllib.loads((project / ".codex/config.toml").read_text())
    assert codex["model"] == "keep-model"
    assert codex["features"]["keep_feature"] is True
    assert "existing" in common.object_value(common.read_json(project / ".mcp.json")["mcpServers"], "servers")
    assert common.read_json(project / ".claude/settings.json")["permissions"] == {"allow": ["Read"]}
    paths = {
        "codex": ".codex/hooks.json",
        "claude": ".claude/settings.json",
        "copilot": ".github/hooks/hard-eng.json",
    }
    data = common.object_value(common.read_json(project / paths[agent])["hooks"], "hooks")
    assert len(data) == 5
    assert all(
        len(common.array(value, "event hooks")) == (2 if agent == "copilot" else 1) for value in data.values()
    )
    if agent == "claude":
        settings = common.read_json(project / paths[agent])
        assert settings["enabledPlugins"] == {"context-mode@context-mode": True}
        assert "context-mode" not in common.object_value(
            common.read_json(project / ".mcp.json")["mcpServers"], "servers"
        )
        assert all(
            len(
                common.array(common.object_value(common.array(value, "entries")[0], "hook")["hooks"], "hooks")
            )
            == 1
            for value in data.values()
        )
    if agent == "copilot":
        servers = common.object_value(common.read_json(project / ".github/mcp.json")["mcpServers"], "servers")
        assert set(mcp.SERVERS) <= servers.keys()


def test_service_detection_uses_dependencies_and_requires_project_identity(project: Path) -> None:
    (project / "README.md").write_text("Sentry and Appwrite are optional examples\n")
    assert integrations.detected(project) == set()
    common.write_json(project / "package.json", {"dependencies": {"@sentry/node": "1", "node-appwrite": "1"}})
    assert integrations.detected(project) == {"sentry", "appwrite"}
    with pytest.raises(GateError, match="project identity"):
        integrations.settings(project)
    common.write_json(
        project / "hard-eng.gates.json",
        {
            "services": {
                "sentry": {
                    "organization": "example",
                    "project": "api",
                    "readiness": {"tool": "find_projects", "arguments": {"organizationSlug": "example"}},
                },
                "appwrite": {
                    "endpoint": "https://appwrite.example.test/v1",
                    "project": "app",
                    "readiness": {"tool": "get_project", "arguments": {"project_id": "app"}},
                },
            }
        },
    )
    with pytest.raises(GateError, match="Self-hosted Appwrite"):
        integrations.servers(project)
    pending: Json = {"sentry": True, "appwrite": True}
    sentry = event(
        "mcp__sentry__find_projects",
        {"organizationSlug": "example"},
        {"structuredContent": {"projects": [{"slug": "api-other"}]}},
    )
    hooks.service_probes(project, pending, sentry)
    assert "sentry" in pending
    sentry["tool_response"] = {"structuredContent": {"projects": [{"slug": "api"}]}}
    hooks.service_probes(project, pending, sentry)
    assert "sentry" not in pending
    appwrite = event(
        "mcp__appwrite__get_project", {"project_id": "app"}, {"structuredContent": {"$id": "app-other"}}
    )
    hooks.service_probes(project, pending, appwrite)
    assert "appwrite" in pending
    appwrite["tool_response"] = {"content": [{"type": "text", "text": '{"$id":"app"}'}]}
    hooks.service_probes(project, pending, appwrite)
    assert pending == {}


def test_mcp_protocol_success_tool_errors_and_crashes_are_distinct(project: Path) -> None:
    script = """
import json, sys
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    if request['method'] == 'crash':
        sys.exit(3)
    result = {'isError': request['method'] == 'tools/call'}
    print(json.dumps({'jsonrpc': '2.0', 'id': request['id'], 'result': result}), flush=True)
"""
    with mcp.Client((sys.executable, "-u", "-c", script), project, timeout=2) as client:
        with pytest.raises(GateError, match="tool error"):
            client.call("get_project", {})
        with pytest.raises(GateError, match="exited"):
            client.request("crash", {})
    assert client.process.poll() == 3


def test_mcp_timeout_does_not_approve_readiness(project: Path) -> None:
    with (
        pytest.raises(GateError, match="timed out"),
        mcp.Client(
            (sys.executable, "-c", "import time; time.sleep(5)"),
            project,
            timeout=0.05,
        ),
    ):
        pytest.fail("An unresponsive server must never initialize successfully")


def test_first_run_download_finishes_before_mcp_protocol(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    npm = project / "npm"
    npm.write_text(
        f"#!{sys.executable}\n"
        "import json, pathlib, sys\n"
        "ready = pathlib.Path('downloaded')\n"
        "if not ready.exists():\n"
        "    print('Downloading native MCP executable...', flush=True)\n"
        "    ready.touch()\n"
        "if '--version' in sys.argv:\n"
        "    sys.exit(0)\n"
        "for line in sys.stdin:\n"
        "    request = json.loads(line)\n"
        "    if 'id' in request:\n"
        "        print(json.dumps({'id': request['id'], 'result': {'ok': True}}), flush=True)\n"
    )
    npm.chmod(0o755)
    monkeypatch.setenv("PATH", str(project) + os.pathsep + os.environ["PATH"])

    def version(_package: str, _ecosystem: str) -> str:
        return "1.0.0"

    monkeypatch.setattr(tools, "package_version", version)
    tool = tools.resolve(project, "codebase-memory-mcp")
    with mcp.Client(tool.command, project, timeout=2) as client:
        assert client.call("probe", {}) == {"ok": True}


@pytest.mark.parametrize("name", ["ToolSearch", "Skill"])
def test_startup_allows_native_tool_and_skill_discovery(project: Path, name: str) -> None:
    assert hooks.dispatch(project, {}, "PreToolUse", event(name, {})) == ("", False)

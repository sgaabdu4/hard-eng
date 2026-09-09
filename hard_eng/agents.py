"""Small native agent configurations that delegate to the shared CLI."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from hard_eng import integrations
from hard_eng.common import GateError, Json, array, object_value, read_json, write_file, write_json
from hard_eng.mcp import SERVERS

AGENTS = ("codex", "claude", "copilot")
ENTRY = 'python3 "$(git rev-parse --show-toplevel)/.hard-eng/bin/hard-eng"'
EVENTS = ("SessionStart", "PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop")


def servers(root: Path) -> Json:
    values: Json = {name: {"command": "sh", "args": ["-c", f"exec {ENTRY} mcp {name}"]} for name in SERVERS}
    values.update(integrations.servers(root))
    return values


def json_servers(root: Path) -> None:
    path = root / ".mcp.json"
    data: Json = read_json(path) if path.exists() else {}
    current = object_value(data.get("mcpServers", {}), "MCP servers")
    for name, definition in servers(root).items():
        definition = object_value(definition, "MCP definition").copy()
        definition.pop("env_vars", None)
        if "url" in definition:
            definition["type"] = "http"
        if name in current and current[name] != definition:
            raise GateError(f"Existing {name} MCP configuration differs; preserve and reconcile it first")
        current[name] = definition
    data["mcpServers"] = current
    write_json(path, data)


def codex_servers(root: Path) -> None:
    path = root / ".codex/config.toml"
    text = path.read_text() if path.exists() else ""
    data = tomllib.loads(text)
    current = object_value(data.get("mcp_servers", {}), "Codex MCP servers")
    features = object_value(data.get("features", {}), "Codex features")
    if features.get("hooks") is False:
        raise GateError("Codex hooks are disabled in project configuration; enable them for enforcement")
    for name, value in servers(root).items():
        definition = object_value(value, "MCP server")
        if name in current:
            if current[name] != definition:
                raise GateError(f"Existing Codex {name} configuration differs; reconcile it first")
            continue
        text += codex_server(name, definition)
    if "hooks" not in features:
        if "features" in data:
            text, count = re.subn(r"(?m)^(\[features\][^\n]*\n)", r"\1hooks = true\n", text, count=1)
            if not count:
                raise GateError("Cannot safely add hooks to this Codex features table; use hooks = true")
        else:
            text += "\n[features]\nhooks = true\n"
    write_file(path, text)


def codex_server(name: str, definition: Json) -> str:
    text = f"\n[mcp_servers.{json.dumps(name)}]\n"
    for key, item in definition.items():
        if key == "env":
            continue
        if not isinstance(item, (str, list)):
            raise GateError(f"Codex {name}: use native environment variable references for credentials")
        text += f"{key} = {json.dumps(item)}\n"
    if "env" in definition:
        text += f"\n[mcp_servers.{json.dumps(name)}.env]\n"
        for key, item in object_value(definition["env"], "MCP environment").items():
            if not isinstance(item, str) or key in {"APPWRITE_API_KEY", "SENTRY_AUTH_TOKEN"}:
                raise GateError(
                    "Keep MCP credentials in the parent environment and forward their names with env_vars"
                )
            text += f"{json.dumps(key)} = {json.dumps(item)}\n"
    return text


def hooks(root: Path, agent: str) -> None:
    paths = {
        "codex": ".codex/hooks.json",
        "claude": ".claude/settings.json",
        "copilot": ".github/hooks/hard-eng.json",
    }
    path = root / paths[agent]
    data: Json = read_json(path) if path.exists() else {}
    if data.get("disableAllHooks") is True:
        raise GateError(f"{agent} hooks are disabled; enable them for enforcement")
    current = object_value(data.get("hooks", {}), "agent hooks")
    for event in EVENTS:
        command = f"{ENTRY} hook {agent} {event}"
        native: Json = {"type": "command", "command": command, "timeout": 3600 if event == "Stop" else 300}
        key = event
        platform = {"codex": "codex", "claude": "claude-code", "copilot": "copilot-cli"}[agent]
        context_command = f"{ENTRY} tool context-mode hook {platform} {event.lower()}"
        if event == "PreToolUse":
            failure = " || { echo 'Hard Eng hook failed' >&2; exit 2; }"
            command += failure
            native["command"] = command
            context_command += failure
        registration: Json = {
            "hooks": [native, {"type": "command", "command": context_command, "timeout": 60}]
        }
        if event in {"PreToolUse", "PostToolUse"}:
            registration["matcher"] = ".*"
        if agent == "copilot":
            key = {
                "SessionStart": "sessionStart",
                "PreToolUse": "preToolUse",
                "PostToolUse": "postToolUse",
                "UserPromptSubmit": "userPromptSubmitted",
                "Stop": "agentStop",
            }[event]
            registration = {"type": "command", "bash": command, "timeoutSec": native["timeout"]}
        entries = array(current.get(key, []), f"{key} hooks")
        if registration not in entries:
            entries.append(registration)
        if agent == "copilot":
            context_hook: Json = {"type": "command", "bash": context_command, "timeoutSec": 60}
            if context_hook not in entries:
                entries.append(context_hook)
        current[key] = entries
    data["hooks"] = current
    if agent == "copilot":
        data["version"] = 1
    write_json(path, data)


def configure(root: Path, agent: str) -> None:
    if agent == "codex":
        codex_servers(root)
    else:
        json_servers(root)
    hooks(root, agent)
    print(
        f"Configured repository-local {agent} MCP servers and hooks; restart/trust this project to load them"
    )
    if agent == "copilot":
        print("LIMITATION: Copilot hook timeouts fail open; Git and CI gates remain required")

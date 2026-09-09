"""Translate native lifecycle events into shared readiness and gate calls."""

from __future__ import annotations

import contextlib
import fcntl
import io
import json
import re
import shlex
from pathlib import Path

from hard_eng import config, integrations, mcp, runner, setup
from hard_eng.common import GateError, Json, array, object_value, parse_json, run, state_dir

READ_ONLY = {
    "read",
    "view",
    "glob",
    "grep",
    "grep_files",
    "list_dir",
    "web_fetch",
    "web_search",
    "ask_user",
    "request_user_input",
    "request_user_input_async",
    "toolsearch",
    "skill",
}
SOURCE_SUFFIXES = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".dart",
    ".sh",
    ".yml",
    ".yaml",
    ".json",
    ".toml",
}


def session(root: Path) -> str:
    if root != Path(__file__).resolve().parents[1]:
        message = setup.update(root)
        result = run(["python3", str(root / ".agents/hard-eng/bin/hard-eng"), "mcp-check"], root, 240)
        if result.returncode:
            raise GateError("MCP readiness failed; run mcp-check to diagnose and repair it")
    else:
        message = "Hard Eng source checkout: updates apply to installed projects"
        mcp.readiness(root)
    integrations.settings(root)
    return message


def tool_input(event: Json) -> Json:
    raw = event.get("tool_input", event.get("toolArgs", {}))
    return parse_json(raw, "tool arguments") if isinstance(raw, str) else object_value(raw, "tool arguments")


def tool_name(event: Json) -> str:
    return str(event.get("tool_name", event.get("toolName", ""))).lower()


def probe_result(event: Json) -> str:
    value = event.get("tool_response", event.get("toolResult", event.get("tool_result", {})))
    text = json.dumps(value)
    if isinstance(value, dict) and (value.get("isError") or value.get("resultType") == "failure"):
        return ""
    return text


def result_data(event: Json) -> Json:
    value = event.get("tool_response", event.get("toolResult", event.get("tool_result", {})))
    if isinstance(value, dict):
        value = value.get("textResultForLlm", value.get("text_result_for_llm", value))
    if isinstance(value, str):
        return parse_json(value, "MCP tool response")
    data = object_value(value, "MCP tool response")
    if "structuredContent" in data:
        return object_value(data["structuredContent"], "MCP structured result")
    for item in array(data.get("content", []), "MCP content"):
        block = object_value(item, "MCP content block")
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            return parse_json(block["text"], "MCP text result")
    return data


def active_probe(root: Path, state: Json, event: Json) -> None:
    name, arguments, response = tool_name(event), tool_input(event), probe_result(event)
    pending = object_value(state.get("pending", {}), "pending MCP probes")
    if not response:
        return
    if "context" in name and name.endswith("ctx_execute"):
        if (
            arguments.get("cwd") == str(root)
            and arguments.get("code") == "git rev-parse --show-toplevel"
            and str(root) in response
        ):
            pending.pop("context-mode", None)
    if "codebase" in name and name.endswith("index_repository") and arguments.get("repo_path") == str(root):
        data = result_data(event)
        if data.get("status") == "indexed" and isinstance(data.get("project"), str):
            state["index_project"] = data["project"]
    if (
        "codebase" in name
        and name.endswith("get_graph_schema")
        and arguments.get("project") == state.get("index_project")
    ):
        if "node_labels" in response and "File" in response:
            pending.pop("codebase-memory-mcp", None)
    service_probes(root, pending, event)
    state["pending"] = pending


def service_probes(root: Path, pending: Json, event: Json) -> None:
    name, arguments = tool_name(event), tool_input(event)
    for service, value in integrations.settings(root).items():
        settings = object_value(value, "service settings")
        probe = object_value(settings["readiness"], "service readiness")
        if service in name and name.endswith(str(probe["tool"])) and arguments == probe["arguments"]:
            data = result_data(event)
            identity = settings["project"]
            if service == "sentry":
                projects = array(data.get("projects", []), "Sentry projects")
                found = arguments.get("organizationSlug") == settings["organization"] and any(
                    object_value(project, "Sentry project").get("slug") == identity for project in projects
                )
            else:
                found = data.get("$id") == identity
            if found:
                pending.pop(service, None)


def repair_call(root: Path, event: Json) -> bool:
    name, arguments = tool_name(event), tool_input(event)
    if name in READ_ONLY or name.endswith(("ctx_search", "ctx_fetch_and_index", "get_graph_schema")):
        return True
    if name.endswith("ctx_execute"):
        return arguments.get("cwd") == str(root) and arguments.get("code") == "git rev-parse --show-toplevel"
    if name.endswith("index_repository"):
        return arguments.get("repo_path") == str(root)
    if name == "apply_patch":
        patch = str(arguments.get("command", arguments.get("patch", "")))
        paths = re.findall(r"(?m)^\*\*\* (?:Add File|Update File|Delete File|Move to): (.+)$", patch)
        return bool(paths) and all(repair_path(root, value) for value in paths)
    path = arguments.get("file_path", arguments.get("path"))
    if name in {"edit", "write", "create"} and isinstance(path, str):
        return repair_path(root, path)
    if repair_command(root, arguments.get("command", arguments.get("cmd", ""))):
        return True
    try:
        for service, value in integrations.settings(root).items():
            probe = object_value(object_value(value, "service settings")["readiness"], "service readiness")
            if service in name and name.endswith(str(probe["tool"])) and arguments == probe["arguments"]:
                return True
    except GateError:
        return False
    return False


def repair_path(root: Path, path: str) -> bool:
    target = (root / path).resolve()
    return target.is_relative_to(root / ".agents/hard-eng") or target in {
        root / "hard-eng.gates.json",
        root / ".mcp.json",
        root / ".github/mcp.json",
        root / ".codex/config.toml",
        root / ".codex/hooks.json",
        root / ".claude/settings.json",
        root / ".github/hooks/hard-eng.json",
    }


def repair_command(root: Path, command: object, *, session_only: bool = False) -> bool:
    if not isinstance(command, str) or any(char in command for char in "\n;&|`<>"):
        return False
    try:
        words = shlex.split(command)
    except ValueError:
        return False
    if not words:
        return False
    if not session_only and words[0] in {"pwd", "which", "rg", "cat", "ls"}:
        return True
    if (
        not session_only
        and words[0] == "git"
        and len(words) > 1
        and words[1] in {"status", "diff", "show", "log", "rev-parse"}
    ):
        return True
    if words[0] in {"python3", "python"} and len(words) >= 3:
        launcher = (root / words[1]).resolve()
        allowed = {root / "bin/hard-eng", root / ".agents/hard-eng/bin/hard-eng"}
        if session_only:
            return launcher in allowed and words[2:] == ["session"]
        return launcher in allowed and words[2] in {
            "session",
            "update",
            "mcp-check",
            "configure",
            "validate",
            "install",
        }
    return False


def has_source_changes(root: Path) -> bool:
    result = run(["git", "status", "--porcelain", "--untracked-files=all"], root)
    if result.returncode:
        raise GateError("Cannot establish changed source scope")
    return any(Path(line[3:].strip('"')).suffix in SOURCE_SUFFIXES for line in result.stdout.splitlines())


def begin(root: Path, state: Json) -> str:
    state.clear()
    state["ready"] = False
    state["changed"] = False
    try:
        message = session(root)
        pending: Json = {name: True for name in (*mcp.SERVERS, *integrations.settings(root))}
        state.update({"ready": True, "pending": pending})
        return (
            message
            + ". Before edits, call Context Mode ctx_execute with language=shell, cwd="
            + str(root)
            + ", code='git rev-parse --show-toplevel'; call Codebase Memory index_repository for this root and get_graph_schema for the returned project. Also run each configured service's read-only readiness call. Use Context Mode for large output."
        )
    except (GateError, OSError, ValueError) as error:
        state["error"] = str(error)
        return f"Hard Eng startup failed: {error}. Diagnose and repair setup; normal project changes are blocked."


def dispatch(root: Path, state: Json, event_name: str, event: Json) -> tuple[str, bool]:
    if event_name == "SessionStart":
        return begin(root, state), False
    if event_name == "UserPromptSubmit":
        state["changed"] = False
        return "", False
    if event_name == "PreToolUse":
        if (not state.get("ready") or state.get("pending")) and not repair_call(root, event):
            return (
                "Hard Eng startup or active-agent MCP probes are incomplete. Diagnose setup or run the required read-only probes before editing.",
                True,
            )
        return "", False
    if event_name == "PostToolUse":
        arguments = tool_input(event)
        if not state.get("ready") and repair_command(
            root, arguments.get("command", arguments.get("cmd", "")), session_only=True
        ):
            return begin(root, state), False
        active_probe(root, state, event)
        if tool_name(event) not in READ_ONLY and has_source_changes(root):
            state["changed"] = True
        return "", False
    if event_name == "Stop" and state.get("changed") and not event.get("stop_hook_active"):
        try:
            runner.check_all(config.load(root))
            state["changed"] = False
            return (
                "Hard Eng gates passed. Review the actual diff against the user's scope before claiming completion.",
                False,
            )
        except (GateError, OSError, ValueError) as error:
            return (
                f"Hard Eng gates did not pass: {error}. Fix the failures or clearly report the unfinished work; do not claim completion.",
                True,
            )
    return "", False


def output(agent: str, event_name: str, message: str, deny: bool) -> Json:
    if event_name == "PreToolUse" and deny:
        if agent == "copilot":
            return {"permissionDecision": "deny", "permissionDecisionReason": message}
        return {
            "hookSpecificOutput": {
                "hookEventName": event_name,
                "permissionDecision": "deny",
                "permissionDecisionReason": message,
            }
        }
    if event_name == "Stop" and deny:
        return {"decision": "block", "reason": message}
    if not message:
        return {}
    if agent == "copilot":
        return {"additionalContext": message}
    if event_name == "Stop":
        return {"systemMessage": message}
    return {"hookSpecificOutput": {"hookEventName": event_name, "additionalContext": message}}


def handle(root: Path, agent: str, event_name: str, event: Json) -> Json:
    identity = event.get("session_id", event.get("sessionId"))
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", identity):
        raise GateError("Native hook session id is missing or invalid")
    path = state_dir(root) / f"{agent}-{identity}.json"
    with path.open("a+") as stream, contextlib.redirect_stdout(io.StringIO()) as diagnostics:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        text = stream.read()
        state = parse_json(text, "session readiness") if text else {}
        if event_name == "SessionStart":
            # A killed startup must leave edits blocked rather than retaining a prior ready state.
            stream.seek(0)
            stream.truncate()
            stream.write('{"ready": false}')
            stream.flush()
        message, deny = dispatch(root, state, event_name, event)
        stream.seek(0)
        stream.truncate()
        json.dump(state, stream)
        stream.flush()
    if diagnostics.getvalue() and deny:
        message += "\n" + diagnostics.getvalue()[-8000:]
    return output(agent, event_name, message, deny)

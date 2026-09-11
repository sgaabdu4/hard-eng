"""Native context/completion responses; Git records scope, never gate results."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gate_config import JsonObject, nonproduction_source, repository_files
from project_setup import dependency_command


def hook_events(agent: str) -> dict[str, str]:
    events = {
        "session": "SessionStart",
        "prompt": "UserPromptSubmit",
        "tool": "PostToolUse",
        "failure": "PostToolUseFailure",
        "stop": "Stop",
    }
    if agent == "codex":
        del events["failure"]
    if agent == "copilot":
        events.update(
            session="sessionStart",
            tool="postToolUse",
            failure="postToolUseFailure",
            stop="agentStop",
        )
        # Config-file prompt hook output is dropped by Copilot.
        del events["prompt"]
    return events


def learning_context(event: str) -> str:
    return (
        f"HE Learn checkpoint ({event}): inspect current evidence for repeated failures or lasting decisions/steering. "
        "Use .agents/skills/he-learn/SKILL.md: deterministic prevention first, skills last; accepted decisions -> docs/adr/. "
        "No qualifying evidence -> continue without new files."
    )


def context_output(agent: str, native: str, message: str) -> JsonObject:
    if agent == "copilot":
        return {"additionalContext": message}
    return {
        "hookSpecificOutput": {
            "hookEventName": native,
            "additionalContext": message,
        }
    }


def session_state(root: Path, payload: JsonObject) -> Path | None:
    identifier = payload.get("session_id", payload.get("sessionId"))
    if not isinstance(identifier, str) or not re.fullmatch(
        r"[A-Za-z0-9_-]{1,200}", identifier
    ):
        return None
    return root / ".hard-eng/sessions" / (identifier + ".json")


def session_context(root: Path, payload: JsonObject) -> str:
    from update import update

    messages = []
    try:
        messages.append(update(root))
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as error:
        messages.append(
            f"Hard Eng update failed: {error}. Continue with the existing scaffold; its gates remain required."
        )
    state = session_state(root, payload)
    if state is not None:
        try:
            revision = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip()
            state.parent.mkdir(parents=True, exist_ok=True)
            if not state.exists():
                state.write_text(json.dumps({"base": revision}))
        except (OSError, subprocess.SubprocessError):
            messages.append("Session revision unavailable; use full checks.")
    messages.append(
        "Use the active Context Mode and Codebase Memory MCP tools for this repository; verify a real call and the repository/index before claiming readiness. If unavailable, warn and continue with available tools."
    )
    for service in integrated_services(root):
        if service == "Dart":
            messages.append(
                "This repository contains Flutter. Use the configured Dart MCP: verify its project roots and perform a read-only analysis or runtime inspection for this repository. The native Dart package launcher downloads the server on demand and requires a compatible Dart SDK. If startup or the call fails, warn and continue; registration alone does not prove readiness."
            )
            continue
        if service == "Marionette":
            messages.append(
                "This repository contains Flutter. Use the configured Marionette MCP: connect to the intended debug app's VM service URI, then call get_interactive_elements or take_screenshots to verify the app/device. If the server, marionette_flutter binding or running app is unavailable, warn and continue; do not claim readiness from installation alone."
            )
            continue
        messages.append(
            f"This repository imports {service}. Use its configured MCP for a read-only call to verify the intended project and endpoint/organization. If configuration or access is missing, warn and continue; do not invent credentials or claim readiness."
        )
    messages.append(learning_context("start/resume"))
    return " ".join(messages)


def integrated_services(root: Path) -> list[str]:
    patterns = {
        "Sentry": r"(?:from\s+['\"]@sentry/|require\(['\"]@sentry/|import\s+sentry_sdk|from\s+sentry_sdk\b|package:sentry(?:_flutter)?/)",
        "Appwrite": r"(?:from\s+['\"](?:node-)?appwrite['\"]|require\(['\"](?:node-)?appwrite['\"]|from\s+appwrite\b|import\s+appwrite\b|package:(?:dart_)?appwrite/)",
        "Marionette": r"\b(?:import|export)\s+['\"]package:flutter/",
    }
    found = set()
    for path in repository_files(root):
        relative = path.relative_to(root)
        if nonproduction_source(relative) or {".agents", ".claude", ".hooks"} & set(
            relative.parts
        ):
            continue
        if (
            path.name == "pubspec.yaml"
            and dependency_command(path.parent, "dart")[0] == "flutter"
        ):
            found.add("Marionette")
        if path.suffix in {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".dart",
            ".mjs",
            ".cjs",
        }:
            source = path.read_text(errors="replace")
            found.update(
                name for name, pattern in patterns.items() if re.search(pattern, source)
            )
    if "Marionette" in found:
        found.add("Dart")
    return sorted(found)


def completion(root: Path, payload: JsonObject) -> JsonObject:
    if payload.get("stop_hook_active"):
        return {
            "systemMessage": "Report remaining verification blockers honestly. Do not claim a pass; no repeated stop-hook loop."
        }
    state = session_state(root, payload)
    base = "HEAD"
    if state is not None and state.exists():
        saved = json.loads(state.read_text())
        if not isinstance(saved, dict):
            raise ValueError("Invalid session state: expected an object")
        base = saved.get("base")
        if not isinstance(base, str) or not base.strip():
            raise ValueError("Invalid session state: expected a nonempty Git base")
    try:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", base, "--"], cwd=root, text=True
        )
        changed += subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
        )
        if not changed.strip() and state is not None and state.exists():
            return {
                "systemMessage": "No repository changes since this session's Git base; no code checks were run."
            }
        with tempfile.TemporaryFile() as log:
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / ".hooks/hard-eng.py"),
                    "check",
                    "--base",
                    base,
                ],
                cwd=root,
                stdout=log,
                stderr=subprocess.STDOUT,
                check=False,
                timeout=3500,
            )
            log.seek(max(0, log.tell() - 16000))
            output = log.read().decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as error:
        return {
            "decision": "block",
            "reason": f"Verification could not run: {error}. Repair it or report the blocker honestly.",
        }
    if result.returncode:
        return {
            "decision": "block",
            "reason": "Repair the failed checks before claiming completion. Questions and honest blocked reports remain possible. "
            + learning_context("failed verification")
            + "\n"
            + output,
        }
    return {}


def handle_event(root: Path, event: str, agent: str) -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise TypeError("Hook input must be a JSON object")
        # Copilot also loads .claude/settings.json and adds its documented
        # timestamp field to that payload. Its own registration handles the
        # event, so do not run updates or checks a second time through Claude.
        if agent == "claude" and "timestamp" in payload:
            print("{}")
            return 0
        native = hook_events(agent).get(event)
        if native is None:
            raise ValueError("Unsupported native hook event")
        if event == "stop":
            output = completion(root, payload)
        else:
            message = (
                session_context(root, payload)
                if event == "session"
                else learning_context(event)
            )
            output = context_output(agent, native, message)
    except (OSError, ValueError, TypeError) as error:
        message = f"Hard Eng hook input/setup failed: {error}. Continue with available tools; do not claim verification passed."
        output = (
            {"systemMessage": message}
            if event != "stop"
            else {"decision": "block", "reason": message}
        )
    print(json.dumps(output))
    return 0

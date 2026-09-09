"""Native session/completion responses; Git records scope, never gate results."""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from gate_config import JsonObject, nonproduction_source, repository_files


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
        messages.append(
            f"This repository imports {service}. Use its configured MCP for a read-only call to verify the intended project and endpoint/organization. If configuration or access is missing, warn and continue; do not invent credentials or claim readiness."
        )
    return " ".join(messages)


def integrated_services(root: Path) -> list[str]:
    patterns = {
        "Sentry": r"(?:from\s+['\"]@sentry/|require\(['\"]@sentry/|import\s+sentry_sdk|from\s+sentry_sdk\b|package:sentry(?:_flutter)?/)",
        "Appwrite": r"(?:from\s+['\"](?:node-)?appwrite['\"]|require\(['\"](?:node-)?appwrite['\"]|from\s+appwrite\b|import\s+appwrite\b|package:(?:dart_)?appwrite/)",
    }
    found = set()
    for path in repository_files(root):
        if nonproduction_source(path.relative_to(root)):
            continue
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
    return sorted(found)


def completion(root: Path, payload: JsonObject) -> JsonObject:
    if payload.get("stop_hook_active"):
        return {
            "systemMessage": "Report remaining verification blockers honestly. Do not claim a pass; no repeated stop-hook loop."
        }
    state = session_state(root, payload)
    base = "HEAD"
    if state is not None and state.exists():
        base = json.loads(state.read_text()).get("base", "HEAD")
    try:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", base, "--"], cwd=root, text=True
        )
        changed += subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], cwd=root, text=True
        )
        if not changed.strip():
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
            "reason": "Repair the failed checks before claiming completion. Questions and honest blocked reports remain possible.\n"
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
        if event == "session":
            message = session_context(root, payload)
            output = (
                {"additionalContext": message}
                if agent == "copilot"
                else {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": message,
                    }
                }
            )
        else:
            output = completion(root, payload)
    except (OSError, ValueError, TypeError) as error:
        message = f"Hard Eng hook input/setup failed: {error}. Continue with available tools; do not claim verification passed."
        output = (
            {"systemMessage": message}
            if event == "session"
            else {"decision": "block", "reason": message}
        )
    print(json.dumps(output))
    return 0

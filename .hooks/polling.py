"""Claude Code PreToolUse hook: refuse a merge that skips ship, and deny foreground polling (HE-NO-FOREGROUND-POLL)."""

import json
import re
import sys
from collections.abc import Callable

REASON = (
    "HE-NO-FOREGROUND-POLL: this command waits in the foreground with sleep. "
    "Start the long job once with run_in_background: true; "
    "the harness tells you when it exits. Read its output file after that notice."
)


def deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def decision(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if payload.get("tool_name") != "Bash" or not isinstance(command, str):
        return None
    if "erge" in command and re.search(r"\bgh\b", command):
        from pathlib import Path

        from merge_guard import holds_merge, merge_problem

        if holds_merge(command) and (
            problem := merge_problem(command, Path(str(payload.get("cwd") or ".")))
        ):
            return deny(f"Merge refused: {problem}")
    if payload.get("agent_id") or (
        isinstance(tool_input, dict) and tool_input.get("run_in_background") is True
    ):
        return None
    if "sleep" not in command and "select(" not in command:
        return None
    from wait_text import polls

    return deny(REASON) if polls(command) else None


def respond(decide: Callable[[object], dict[str, object] | None]) -> int:
    try:
        output = decide(json.load(sys.stdin))
    except ValueError:
        return 0
    if output is not None:
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(respond(decision))

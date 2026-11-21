"""PreToolUse hook (Claude Code and Antigravity): deny foreground polling (HE-NO-FOREGROUND-POLL)."""

import json
import sys
from collections.abc import Callable

REASON = (
    "HE-NO-FOREGROUND-POLL: this command waits in the foreground with sleep. "
    "Start the long job once with run_in_background: true; "
    "the harness tells you when it exits. Read its output file after that notice."
)


def decision(payload: object) -> dict[str, object] | None:
    if not isinstance(payload, dict):
        return None
    tool_call = payload.get("toolCall")
    if isinstance(tool_call, dict):
        args = tool_call.get("args")
        if (
            payload.get("parentConversationId")
            or tool_call.get("name") != "run_command"
            or not isinstance(args, dict)
            or args.get("IsDaemon") is True
            or not isinstance(command := args.get("CommandLine"), str)
        ):
            return None
        agy = True
    else:
        tool_input = payload.get("tool_input")
        if (
            payload.get("agent_id")
            or payload.get("tool_name") != "Bash"
            or not isinstance(tool_input, dict)
            or tool_input.get("run_in_background") is True
            or not isinstance(command := tool_input.get("command"), str)
        ):
            return None
        agy = False
    if "sleep" not in command and "select(" not in command:
        return None
    from wait_text import polls

    if not polls(command):
        return None
    if agy:
        return {"decision": "deny", "reason": REASON}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON,
        }
    }


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

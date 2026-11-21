#!/usr/bin/env python3
"""Refuse an old Python, answer a hook event early, else run the commands."""

import json
import sys

PYTHON_FLOOR = (3, 12)
if sys.version_info < PYTHON_FLOOR:
    refusal = (
        f"Hard Eng needs Python {PYTHON_FLOOR[0]}.{PYTHON_FLOOR[1]} or later, but python3 "
        f"here is {sys.version_info[0]}.{sys.version_info[1]}. No check or hook ran. "
        "Put a newer python3 first on PATH."
    )
    event, agy = sys.argv[1:2], sys.argv[2:3] == ["agy"]
    if event == ["stop"]:
        d = json.load(sys.stdin)
        skip = d.get("stop_hook_active") is True or d.get("continuationActive") is True
        if agy and (d.get("parentConversationId") or d.get("fullyIdle") is False):
            skip = True
        skip = skip or (agy and d.get("terminationReason") == "USER_CANCELED")
        out: dict[str, str] = {} if agy else {"systemMessage": refusal}
        if not skip:
            out = {"decision": "continue" if agy else "block", "reason": refusal}
        print(json.dumps(out))
    elif event == ["session"]:
        msg = {"systemMessage": refusal}
        print(json.dumps({"injectSteps": [{"systemMessage": msg}]} if agy else msg))
    else:
        sys.exit(refusal)
    sys.exit(0)

if __name__ == "__main__":
    args, agents = sys.argv[1:], ("claude", "codex", "agy")
    if len(args) == 2 and args[0] in ("session", "stop") and args[1] in agents:
        from pathlib import Path

        from agent_hooks import handle_event

        root = Path(__file__).resolve().parents[1]
        raise SystemExit(handle_event(root, args[0], args[1]))
    from gate_runner import run

    run()

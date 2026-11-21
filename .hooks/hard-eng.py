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
        data = json.load(sys.stdin)
        active = True in (data.get("stop_hook_active"), data.get("continuationActive"))
        block = {"decision": "continue" if agy else "block", "reason": refusal}
        done: dict[str, str] = {} if agy else {"systemMessage": refusal}
        print(json.dumps(done if active else block))
    elif event == ["session"]:
        step = {"systemMessage": {"systemMessage": refusal}}
        print(
            json.dumps({"injectSteps": [step]} if agy else {"systemMessage": refusal})
        )
    else:
        sys.exit(refusal)
    sys.exit(0)

if (
    __name__ == "__main__"
    and sys.argv[1:2] in (["session"], ["stop"])
    and sys.argv[2:] in (["claude"], ["codex"], ["agy"])
):
    from pathlib import Path

    from agent_hooks import handle_event

    raise SystemExit(handle_event(Path(__file__).resolve().parents[1], *sys.argv[1:3]))

if __name__ == "__main__":
    from gate_runner import run

    run()

#!/usr/bin/env python3
"""Converge or check the shared hard-eng guard hooks for Codex and Copilot.

usage: agent-hooks.py <codex|copilot> <install|check>

Codex hooks.json is shared with other owners, so only entries whose command
names the guard script are pruned and rewritten. The Copilot personal hook
file is ours alone and is written whole.

Exit codes: 0 converged/matching, 5 drift (check mode), >0 failure.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path

MARKERS = ("agent-hook.sh", "agent_hook.py")
COMMAND_KEYS = ("command", "bash", "powershell")
TIMEOUT_SECONDS = 10

RUNTIMES = {
    "codex": {
        "path_env": "CODEX_HOOKS",
        "events": (("PreToolUse", "pretooluse"), ("PostToolUse", "posttooluse")),
        "nested": True,
        "command_key": "command",
        "timeout_key": "timeout",
    },
    # Copilot names the shell command after the shell that runs it, and states
    # its timeout in seconds; a "command" key is silently ignored.
    "copilot": {
        "path_env": "COPILOT_HOOKS",
        "events": (("preToolUse", "pretooluse"), ("postToolUse", "posttooluse")),
        "nested": False,
        "command_key": "bash",
        "timeout_key": "timeoutSec",
    },
}


def fail(message: str) -> None:
    raise SystemExit(f"agent-hooks: FAIL: {message}")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
        raise SystemExit(1)
    return value


def owned(hook: object) -> bool:
    # Every dialect's command key is checked so entries written under a
    # superseded key are pruned rather than left behind.
    if not isinstance(hook, dict):
        return False
    return any(
        isinstance(value, str) and marker in value
        for key in COMMAND_KEYS
        for value in (hook.get(key),)
        for marker in MARKERS
    )


def prune(entries: object, nested: bool, event: str) -> list:
    if entries is None:
        return []
    if not isinstance(entries, list):
        fail(f"hooks.{event} key has a non-array owner")
        raise SystemExit(1)
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"hooks.{event} contains a non-object entry")
            raise SystemExit(1)
        if not nested:
            if not owned(entry):
                kept.append(entry)
            continue
        inner = entry.get("hooks")
        if not isinstance(inner, list):
            fail(f"hooks.{event} entry has a non-array hooks value")
            raise SystemExit(1)
        remaining = [hook for hook in inner if not owned(hook)]
        if not remaining:
            continue
        entry["hooks"] = remaining
        kept.append(entry)
    return kept


def desired(current: dict, runtime: str, command: str) -> dict:
    spec = RUNTIMES[runtime]
    target = copy.deepcopy(current)
    if runtime == "copilot":
        target["version"] = 1
    hooks = target.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        fail("hooks key has a non-object owner")
        raise SystemExit(1)
    for event, argument in spec["events"]:
        entries = prune(hooks.get(event), spec["nested"], event)
        hook = {
            "type": "command",
            spec["command_key"]: f"{command} {runtime} {argument}",
            spec["timeout_key"]: TIMEOUT_SECONDS,
        }
        entries.append({"hooks": [hook]} if spec["nested"] else hook)
        hooks[event] = entries
    return target


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in RUNTIMES:
        fail("usage: agent-hooks.py <codex|copilot> <install|check>")
    runtime, mode = sys.argv[1], sys.argv[2]
    if mode not in ("install", "check"):
        fail("usage: agent-hooks.py <codex|copilot> <install|check>")
    path = Path(required_env(RUNTIMES[runtime]["path_env"]))
    if path.exists():
        try:
            current = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            fail(f"hooks file is not valid JSON: {path}: {error}")
            return 1
        if not isinstance(current, dict):
            fail(f"hooks file is not a JSON object: {path}")
            return 1
    else:
        current = {}
    target = desired(current, runtime, required_env("HARD_ENG_HOOK_COMMAND"))
    if current == target:
        return 0
    if mode == "check":
        return 5
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".hard-eng.tmp")
    temporary.write_text(json.dumps(target, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

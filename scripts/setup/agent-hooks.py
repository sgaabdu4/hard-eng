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
import shlex
import sys
from pathlib import Path
from typing import NoReturn

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup.safe_file import SafeFileError, create_path, read_snapshot, replace_path_if_unchanged
from scripts.setup.cli_errors import run_cli

MARKERS = ("agent-hook.sh", "enforcement_policy.pl")
COMMAND_KEYS = ("command", "bash", "powershell")
TIMEOUT_SECONDS = 2

RUNTIMES = {
    "codex": {
        "path_env": "CODEX_HOOKS",
        "events": (
            ("PreToolUse", "pretooluse"),
        ),
        "nested": True,
        "command_key": "command",
        "timeout_key": "timeout",
    },
    # Copilot names the shell command after the shell that runs it, states its
    # timeout in seconds, and calls the end of a turn agentStop; a "command" key
    # and a "Stop" event name are both silently ignored.
    "copilot": {
        "path_env": "COPILOT_HOOKS",
        "events": (
            ("preToolUse", "pretooluse"),
        ),
        "nested": False,
        "command_key": "bash",
        "timeout_key": "timeoutSec",
    },
}
RETIRED_EVENTS = {
    "codex": ("PostToolUse", "Stop"),
    "copilot": ("postToolUse", "agentStop"),
}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"agent-hooks: FAIL: {message}")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
    return value


def owned(hook: object) -> bool:
    if not isinstance(hook, dict):
        return False
    interpreters = {"bash", "sh", "zsh", "fish", "perl", "python", "python3"}
    for key in COMMAND_KEYS:
        value = hook.get(key)
        if not isinstance(value, str):
            continue
        try:
            tokens = shlex.split(value, posix=True)
        except ValueError:
            continue
        for index, token in enumerate(tokens):
            if Path(token).name not in MARKERS:
                continue
            if index == 0 or Path(tokens[index - 1]).name in interpreters:
                return True
    return False


def prune(entries: object, nested: bool, event: str) -> list:
    if entries is None:
        return []
    if not isinstance(entries, list):
        fail(f"hooks.{event} key has a non-array owner")
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"hooks.{event} contains a non-object entry")
        if not nested:
            if not owned(entry):
                kept.append(entry)
            continue
        inner = entry.get("hooks")
        if not isinstance(inner, list):
            fail(f"hooks.{event} entry has a non-array hooks value")
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
    for event in RETIRED_EVENTS[runtime]:
        hooks[event] = prune(hooks.get(event), spec["nested"], event)
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
    original: bytes | None
    original_mode: int | None
    try:
        original, original_mode = read_snapshot(path.parent, Path(path.name))
    except FileNotFoundError:
        original, original_mode = None, None
    except OSError as error:
        fail(f"hooks path is unsafe: {path}: {error}")
    if original is not None:
        try:
            current = json.loads(original.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
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
    replacement = (json.dumps(target, indent=2) + "\n").encode("utf-8")
    try:
        if original is None or original_mode is None:
            create_path(path, replacement, 0o600)
        else:
            replace_path_if_unchanged(path, original, original_mode, replacement)
    except (FileNotFoundError, SafeFileError, OSError) as error:
        fail(f"hooks write was not applied safely: {path}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli("agent-hooks", main))

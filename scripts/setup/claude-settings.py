#!/usr/bin/env python3
"""Converge or check hard-eng-owned keys in Claude Code settings.json.

Owned keys: attribution (commit/pr empty), includeCoAuthoredBy false,
the shared hard-eng guard hooks, the pinned context-mode marketplace entry,
its enabled plugin flag, and the canonical output style.
All other settings content is preserved untouched.

Exit codes: 0 converged/matching, 5 drift (check mode), >0 failure.
"""

from __future__ import annotations

import copy
import json
import os
import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"claude-settings: FAIL: {message}")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
    return value


GUARD_EVENTS = (
    ("PreToolUse", "Bash|Edit|Write|MultiEdit|NotebookEdit", "pretooluse"),
    ("PostToolUse", "Bash|mcp__codebase-memory-mcp__.*", "posttooluse"),
)
# Commands hard-eng owns and therefore may prune; the last two are superseded names.
OWNED_HOOK_MARKERS = ("agent-hook.sh", "agent_hook.py", "rg-guard.py")
# Must match the name: frontmatter in output-styles/plain-english.md.
OUTPUT_STYLE = "Plain English"


def owned_hook(hook: object) -> bool:
    if not isinstance(hook, dict) or hook.get("type") != "command":
        return False
    command = hook.get("command")
    return isinstance(command, str) and any(
        marker in command for marker in OWNED_HOOK_MARKERS
    )


def prune_owned(hooks: dict, event: str) -> list:
    entries = hooks.setdefault(event, [])
    if not isinstance(entries, list):
        fail(f"hooks.{event} key has a non-array owner")
    kept = []
    for entry in entries:
        if not isinstance(entry, dict):
            fail(f"hooks.{event} contains a non-object entry")
        entry_hooks = entry.get("hooks")
        if not isinstance(entry_hooks, list):
            fail(f"hooks.{event} entry has a non-array hooks value")
        remaining = [hook for hook in entry_hooks if not owned_hook(hook)]
        if not remaining:
            continue
        entry["hooks"] = remaining
        kept.append(entry)
    hooks[event] = kept
    return kept


def add_guard_hooks(target: dict, command: str) -> None:
    hooks = target.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        fail("hooks key has a non-object owner")
    for event, matcher, argument in GUARD_EVENTS:
        entries = prune_owned(hooks, event)
        entries.append(
            {
                "matcher": matcher,
                "hooks": [{"type": "command", "command": f"{command} claude {argument}"}],
            }
        )


def desired(current: dict) -> dict:
    target = copy.deepcopy(current)
    attribution = target.setdefault("attribution", {})
    if not isinstance(attribution, dict):
        fail("attribution key has a non-object owner")
    attribution["commit"] = ""
    attribution["pr"] = ""
    target["includeCoAuthoredBy"] = False
    target["outputStyle"] = OUTPUT_STYLE
    add_guard_hooks(target, required_env("HARD_ENG_HOOK_COMMAND"))
    marketplaces = target.setdefault("extraKnownMarketplaces", {})
    if not isinstance(marketplaces, dict):
        fail("extraKnownMarketplaces key has a non-object owner")
    marketplaces[required_env("CONTEXT_MARKETPLACE_NAME")] = {
        "source": {
            "source": "github",
            "repo": required_env("CONTEXT_MARKETPLACE_REPO"),
            "ref": required_env("CONTEXT_MARKETPLACE_REF"),
        }
    }
    plugins = target.setdefault("enabledPlugins", {})
    if not isinstance(plugins, dict):
        fail("enabledPlugins key has a non-object owner")
    plugins[required_env("CONTEXT_PLUGIN_ID")] = True
    return target


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("install", "check"):
        fail("usage: claude-settings.py install|check")
    settings_path = Path(required_env("CLAUDE_SETTINGS"))
    if settings_path.exists():
        try:
            current = json.loads(settings_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            fail(f"settings file is not valid JSON: {settings_path}: {error}")
        if not isinstance(current, dict):
            fail(f"settings file is not a JSON object: {settings_path}")
    else:
        current = {}
    target = desired(current)
    if current == target:
        return 0
    if sys.argv[1] == "check":
        return 5
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = settings_path.with_name(settings_path.name + ".hard-eng.tmp")
    temporary.write_text(
        json.dumps(target, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temporary, settings_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Converge or check hard-eng-owned keys in Claude Code settings.json.

Owned keys: attribution (commit/pr empty), includeCoAuthoredBy false,
the Claude rg guard, the pinned context-mode marketplace entry, and its
enabled plugin flag.
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


def add_claude_rg_guard(target: dict, command: str) -> None:
    hooks = target.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        fail("hooks key has a non-object owner")
    pre_tool_use = hooks.setdefault("PreToolUse", [])
    if not isinstance(pre_tool_use, list):
        fail("hooks.PreToolUse key has a non-array owner")
    for entry in pre_tool_use:
        if not isinstance(entry, dict):
            fail("hooks.PreToolUse contains a non-object entry")
        if entry.get("matcher") != "Bash":
            continue
        entry_hooks = entry.get("hooks")
        if not isinstance(entry_hooks, list):
            fail("hooks.PreToolUse Bash entry has a non-array hooks value")
        if any(
            isinstance(hook, dict)
            and hook.get("type") == "command"
            and hook.get("command") == command
            for hook in entry_hooks
        ):
            return
    pre_tool_use.append(
        {
            "matcher": "Bash",
            "hooks": [{"type": "command", "command": command}],
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
    add_claude_rg_guard(target, required_env("CLAUDE_RG_GUARD_COMMAND"))
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

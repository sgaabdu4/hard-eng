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
import base64
import json
import os
import sys
from pathlib import Path
from typing import NoReturn

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup.safe_file import (
    SafeFileError,
    consume_if_unchanged,
    create_path,
    read_snapshot,
    replace_path_if_unchanged,
)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"claude-settings: FAIL: {message}")


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
    return value


GUARD_EVENTS = (
    (
        "PreToolUse",
        "Bash|Edit|Write|MultiEdit|NotebookEdit|Agent|mcp__.*",
        "pretooluse",
    ),
)
# Commands hard-eng owns and therefore may prune; the last two are superseded names.
OWNED_HOOK_MARKERS = ("agent-hook.sh", "enforcement_policy.pl", "rg-guard.py")
# Must match the name: frontmatter in output-styles/plain-english.md.
OUTPUT_STYLE = "Plain English"


def owned_hook(hook: object) -> bool:
    if not isinstance(hook, dict) or hook.get("type") != "command":
        return False
    command = hook.get("command")
    if not isinstance(command, str):
        return False
    try:
        import shlex

        tokens = shlex.split(command, posix=True)
    except ValueError:
        return False
    interpreters = {"bash", "sh", "zsh", "fish", "perl", "python", "python3"}
    for index, token in enumerate(tokens):
        if Path(token).name not in OWNED_HOOK_MARKERS:
            continue
        if index == 0 or Path(tokens[index - 1]).name in interpreters:
            return True
    return False


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
    for event in ("PostToolUse", "Stop"):
        prune_owned(hooks, event)
    for event, matcher, argument in GUARD_EVENTS:
        entries = prune_owned(hooks, event)
        entry = {"hooks": [{"type": "command", "command": f"{command} claude {argument}"}]}
        if matcher is not None:
            entry = {"matcher": matcher, **entry}
        entries.append(entry)


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


def journal_path() -> Path | None:
    value = os.environ.get("CLAUDE_SETTINGS_JOURNAL")
    return Path(value) if value else None


def write_journal(
    path: Path,
    original: bytes | None,
    original_mode: int | None,
    replacement: bytes,
    replacement_mode: int,
) -> None:
    journal = journal_path()
    if journal is None:
        return
    payload = {
        "path": str(path),
        "before": None if original is None else base64.b64encode(original).decode("ascii"),
        "before_mode": original_mode,
        "after": base64.b64encode(replacement).decode("ascii"),
        "after_mode": replacement_mode,
    }
    create_path(
        journal,
        (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        0o600,
    )


def rollback() -> int:
    journal = journal_path()
    if journal is None:
        fail("CLAUDE_SETTINGS_JOURNAL is required for rollback")
    try:
        payload_bytes, journal_mode = read_snapshot(journal.parent, Path(journal.name))
        if journal_mode != 0o600:
            fail("settings rollback journal is not private")
        payload = json.loads(payload_bytes.decode("utf-8"))
        path = Path(payload["path"])
        if path != Path(required_env("CLAUDE_SETTINGS")):
            fail("settings rollback journal names another target")
        before_value = payload["before"]
        before = None if before_value is None else base64.b64decode(before_value, validate=True)
        before_mode = payload["before_mode"]
        after = base64.b64decode(payload["after"], validate=True)
        after_mode = int(payload["after_mode"])
        if before is None:
            consume_if_unchanged(path.parent, Path(path.name), after, after_mode)
        else:
            if not isinstance(before_mode, int):
                fail("settings rollback journal has no original mode")
            replace_path_if_unchanged(path, after, after_mode, before)
    except (KeyError, TypeError, ValueError, UnicodeError, json.JSONDecodeError, OSError) as error:
        fail(f"settings rollback was not applied safely: {error}")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("install", "check", "rollback"):
        fail("usage: claude-settings.py install|check|rollback")
    if sys.argv[1] == "rollback":
        return rollback()
    settings_path = Path(required_env("CLAUDE_SETTINGS"))
    original: bytes | None
    original_mode: int | None
    try:
        original, original_mode = read_snapshot(settings_path.parent, Path(settings_path.name))
    except FileNotFoundError:
        original, original_mode = None, None
    except OSError as error:
        fail(f"settings path is unsafe: {settings_path}: {error}")
    if original is not None:
        try:
            current = json.loads(original.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
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
    replacement = (json.dumps(target, indent=2) + "\n").encode("utf-8")
    replacement_mode = 0o600 if original_mode is None else original_mode
    try:
        write_journal(
            settings_path,
            original,
            original_mode,
            replacement,
            replacement_mode,
        )
        if original is None or original_mode is None:
            create_path(settings_path, replacement, replacement_mode)
        else:
            replace_path_if_unchanged(
                settings_path,
                original,
                original_mode,
                replacement,
            )
    except (FileNotFoundError, SafeFileError, OSError) as error:
        fail(f"settings write was not applied safely: {settings_path}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

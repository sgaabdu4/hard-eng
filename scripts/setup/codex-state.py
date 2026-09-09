#!/usr/bin/env python3
"""Read-only validation of the managed Codex plugin state."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

import tomllib

ROOT = Path(__file__).resolve().parents[2]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from bounded_run import run_captured
from git_env import git_env

from scripts.setup.cli_errors import run_cli

MANIFEST = json.loads((ROOT / "scripts/setup/manifest.json").read_text())
CONTEXT = MANIFEST["codex"]["context_mode"]

MATCH = 0
MISSING = 3
CONFLICT = 4
DRIFT = 5
MEMORY_NAME = "codebase-memory"


def fail(message: str, code: int) -> NoReturn:
    print(f"setup:codex: {message}", file=sys.stderr)
    raise SystemExit(code)


def codex_json(*arguments: str) -> dict:
    try:
        captured = run_captured(["codex", *arguments, "--json"], 60)
    except OSError as error:
        fail(f"Codex command did not complete: {error}", 2)
    result = subprocess.CompletedProcess(
        ["codex", *arguments, "--json"],
        captured.returncode,
        captured.stdout.decode("utf-8", "replace"),
        captured.stderr.decode("utf-8", "replace"),
    )
    if result.returncode:
        fail(result.stderr.strip() or f"codex {' '.join(arguments)} failed", 2)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"invalid Codex JSON: {error}", 2)
    if not isinstance(value, dict):
        fail("Codex JSON root must be an object", 2)
    return value


def marketplace_entry() -> dict | None:
    value = codex_json("plugin", "marketplace", "list")
    entries = value.get("marketplaces")
    if not isinstance(entries, list):
        fail("marketplace list missing", 2)
    matches = [item for item in entries if isinstance(item, dict) and item.get("name") == CONTEXT["marketplace_name"]]
    if not matches:
        return None
    if len(matches) != 1:
        fail("duplicate managed marketplace", CONFLICT)
    item = matches[0]
    source = item.get("marketplaceSource", {})
    if (
        not isinstance(source, dict)
        or source.get("sourceType") != "git"
        or source.get("source") != CONTEXT["marketplace_source"]
    ):
        fail("managed marketplace name belongs to another source", CONFLICT)
    return item


def marketplace_commit(item: dict) -> str:
    root = item.get("root")
    if not isinstance(root, str) or not root:
        fail("managed marketplace root missing", DRIFT)
    try:
        captured = run_captured(["git", "-C", root, "rev-parse", "HEAD"], 20, env=git_env())
    except OSError as error:
        fail(f"managed marketplace commit check failed: {error}", DRIFT)
    result = subprocess.CompletedProcess(
        ["git", "-C", root, "rev-parse", "HEAD"],
        captured.returncode,
        captured.stdout.decode("utf-8", "replace"),
        captured.stderr.decode("utf-8", "replace"),
    )
    commit = result.stdout.strip()
    if result.returncode or not commit:
        fail("managed marketplace commit unavailable", DRIFT)
    return commit


def marketplace_status() -> int:
    item = marketplace_entry()
    if item is None:
        return MISSING
    if marketplace_commit(item) != CONTEXT["marketplace_commit"]:
        return DRIFT
    return MATCH


def plugin_status() -> int:
    value = codex_json("plugin", "list")
    entries = value.get("installed")
    if not isinstance(entries, list):
        fail("plugin list missing", 2)
    matches = [item for item in entries if isinstance(item, dict) and item.get("pluginId") == CONTEXT["plugin_id"]]
    if not matches:
        return MISSING
    if len(matches) != 1:
        fail("duplicate managed plugin", CONFLICT)
    item = matches[0]
    source = item.get("marketplaceSource", {})
    if (
        item.get("marketplaceName") != CONTEXT["marketplace_name"]
        or not isinstance(source, dict)
        or source.get("sourceType") != "git"
        or source.get("source") != CONTEXT["marketplace_source"]
    ):
        fail("managed plugin ID belongs to another source", CONFLICT)
    if (
        item.get("version") != CONTEXT["version"]
        or item.get("installed") is not True
        or item.get("enabled") is not True
    ):
        return DRIFT
    return MATCH


def mcp_status() -> int:
    config_path = Path(os.environ["CODEX_HOME"]) / "config.toml"
    if not config_path.is_file():
        return MISSING
    try:
        value = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        fail(f"invalid Codex config: {error}", 2)
    servers = value.get("mcp_servers")
    entry = servers.get(MEMORY_NAME) if isinstance(servers, dict) else None
    if entry is None:
        return MISSING
    expected = os.environ.get("MEMORY_MCP_COMMAND", "")
    if not expected:
        fail("MEMORY_MCP_COMMAND is required for the mcp verb", 2)
    if not isinstance(entry, dict) or entry.get("command") != expected:
        fail("managed MCP server name belongs to another owner", CONFLICT)
    return MATCH


def main() -> int:
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    if command == "marketplace":
        return marketplace_status()
    if command == "marketplace-head":
        item = marketplace_entry()
        if item is None:
            return MISSING
        print(marketplace_commit(item))
        return MATCH
    if command == "plugin":
        return plugin_status()
    if command == "mcp":
        return mcp_status()
    if command == "check":
        marketplace = marketplace_status()
        plugin = plugin_status()
        if marketplace != MATCH or plugin != MATCH:
            return DRIFT
        print("setup:codex: PASS")
        return MATCH
    fail("usage: codex-state.py [marketplace|plugin|mcp|check]", 2)
    return 2


if __name__ == "__main__":
    raise SystemExit(run_cli("setup:codex", main))

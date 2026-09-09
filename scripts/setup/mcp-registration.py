#!/usr/bin/env python3
"""Read-only status of one managed MCP server registration in a JSON config."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup.cli_errors import run_cli

MATCH = 0
MISSING = 3
CONFLICT = 4


def main() -> int:
    config_path = Path(os.environ["MEMORY_MCP_CONFIG"])
    name = os.environ["MEMORY_MCP_NAME"]
    expected = os.environ["MEMORY_MCP_COMMAND"]
    if not config_path.is_file():
        return MISSING
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        print(f"setup:mcp-registration: unreadable MCP config {config_path}: {error}", file=sys.stderr)
        return 2
    servers = value.get("mcpServers") if isinstance(value, dict) else None
    entry = servers.get(name) if isinstance(servers, dict) else None
    if entry is None:
        return MISSING
    if isinstance(entry, dict) and entry.get("command") == expected:
        return MATCH
    print(f"setup:mcp-registration: MCP server {name} has another owner: {config_path}", file=sys.stderr)
    return CONFLICT


if __name__ == "__main__":
    raise SystemExit(run_cli("setup:mcp-registration", main))

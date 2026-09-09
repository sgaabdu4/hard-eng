#!/usr/bin/env python3
"""Static contracts for the Claude Code setup surface."""

from __future__ import annotations

from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-claude-contract: FAIL: {message}")


def check_claude_memory_mcp() -> None:
    common = (ROOT / "scripts/setup/common.sh").read_text(encoding="utf-8")
    required_common = (
        "MEMORY_MCP_NAME=codebase-memory\n",
        "MEMORY_MCP_COMMAND=$BIN_DIR/codebase-memory-mcp\n",
        "MCP_REGISTRATION_TOOL=$SETUP_DIR/mcp-registration.py\n",
    )
    if any(anchor not in common for anchor in required_common):
        fail("setup does not own one shared codebase-memory MCP contract")
    owner = (ROOT / "scripts/setup/claude.sh").read_text(encoding="utf-8")
    required = (
        "command -v claude >/dev/null 2>&1 || return 0\n",
        'bounded_setup_run 60 claude mcp add --scope user "$MEMORY_MCP_NAME" -- "$MEMORY_MCP_COMMAND"',
        'bounded_setup_run 60 claude mcp remove --scope user "$MEMORY_MCP_NAME"',
    )
    if any(anchor not in owner for anchor in required):
        fail("Claude MCP registration is not converged through the bounded official CLI")
    check_body = owner.partition("check_claude_integration() {")[2].partition("\n}\n")[0]
    if "claude_mcp_status" not in check_body:
        fail("Claude integration check does not prove the MCP registration")


def main() -> int:
    check_claude_memory_mcp()
    print("setup-claude-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

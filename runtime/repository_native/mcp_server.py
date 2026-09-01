#!/usr/bin/env python3
"""Tiny stdio MCP server exposing the active Hard Eng identity."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from runtime.repository_native.repository import inspect_repository


def _identity(repository: Path) -> dict[str, object]:
    state = inspect_repository(repository)
    local = state.root / ".agents/hard-eng"
    current = local / "current"
    release: dict[str, object] = {}
    identity = current / ".hard-eng-release.json"
    if identity.is_file() and not identity.is_symlink():
        try:
            value = json.loads(identity.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        if isinstance(value, dict):
            release = value
    return {
        "channel": state.policy.channel if state.policy else None,
        "marked": state.marked,
        "mode": os.environ.get("HARD_ENG_MODE") or "unprotected",
        "repository": str(state.root),
        "source_commit": release.get("source_commit"),
        "version": os.environ.get("HARD_ENG_VERSION") or release.get("version"),
    }


def _result(identifier: object, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "result": result}


def _error(identifier: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": identifier, "error": {"code": code, "message": message}}


def _handle(message: dict[str, Any], repository: Path) -> dict[str, object] | None:
    method = message.get("method")
    identifier = message.get("id")
    if identifier is None:
        return None
    if method == "initialize":
        params = message.get("params")
        protocol = params.get("protocolVersion") if isinstance(params, dict) else None
        return _result(
            identifier,
            {
                "capabilities": {"tools": {}},
                "protocolVersion": protocol or "2025-06-18",
                "serverInfo": {"name": "hard-eng", "version": "1"},
            },
        )
    if method == "ping":
        return _result(identifier, {})
    if method == "tools/list":
        return _result(
            identifier,
            {
                "tools": [
                    {
                        "annotations": {
                            "destructiveHint": False,
                            "idempotentHint": True,
                            "openWorldHint": False,
                            "readOnlyHint": True,
                        },
                        "description": "Report the repository's active Hard Eng mode and release identity.",
                        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                        "name": "hard_eng_status",
                    }
                ]
            },
        )
    if method == "tools/call":
        params = message.get("params")
        if not isinstance(params, dict) or params.get("name") != "hard_eng_status":
            return _error(identifier, -32602, "unknown Hard Eng tool")
        value = _identity(repository)
        return _result(
            identifier,
            {"content": [{"type": "text", "text": json.dumps(value, sort_keys=True)}], "structuredContent": value},
        )
    return _error(identifier, -32601, f"method not found: {method}")


def serve(repository: Path) -> int:
    for raw in sys.stdin:
        try:
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise TypeError("message is not an object")
            response = _handle(value, repository)
        except (TypeError, json.JSONDecodeError) as error:
            response = _error(None, -32700, str(error))
        if response is not None:
            sys.stdout.write(json.dumps(response, separators=(",", ":")) + "\n")
            sys.stdout.flush()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    arguments = parser.parse_args()
    return serve(Path(arguments.repo).resolve())


if __name__ == "__main__":
    raise SystemExit(main())

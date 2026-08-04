#!/usr/bin/env python3
"""Block grep-style recursive flags bundled with ripgrep."""

from __future__ import annotations

import json
import os
import re
import shlex
import sys


BOUNDARIES = {";", "&&", "||", "|", "&", "(", ")"}
COMMAND_WRAPPERS = {"command", "env", "nice", "nohup", "rtk", "sudo", "time"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
SHORT_FLAG_CLUSTER = re.compile(r"^-[A-Za-z]+$")
GLUED_REPLACE = re.compile(r"r[A-Za-z]+")


def shell_tokens(command: str) -> list[str]:
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|&;()")
    lexer.whitespace_split = True
    return list(lexer)


def command_positions(tokens: list[str]) -> list[int]:
    positions: list[int] = []
    command_position = True
    for index, token in enumerate(tokens):
        if token in BOUNDARIES:
            command_position = True
            continue
        if command_position:
            if token in COMMAND_WRAPPERS or ASSIGNMENT.fullmatch(token):
                continue
            positions.append(index)
            command_position = False
    return positions


def bad_flag_after(tokens: list[str], command_index: int) -> str | None:
    for token in tokens[command_index + 1 :]:
        if token in BOUNDARIES or token == "--":
            return None
        if SHORT_FLAG_CLUSTER.fullmatch(token) and GLUED_REPLACE.search(token[1:]):
            return token
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError) as error:
        print(f"rg-guard: invalid hook input: {error}", file=sys.stderr)
        return 2

    if not isinstance(payload, dict) or payload.get("tool_name") != "Bash":
        return 0

    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        print("rg-guard: Bash hook input has no command", file=sys.stderr)
        return 2

    try:
        tokens = shell_tokens(command)
    except ValueError:
        return 0

    for command_index in command_positions(tokens):
        if os.path.basename(tokens[command_index]) != "rg":
            continue
        flag = bad_flag_after(tokens, command_index)
        if flag is not None:
            print(
                f"Blocked {flag}: ripgrep uses -r for --replace, not recursion. "
                "Use rg -n or rg -ln; rg recurses by default.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

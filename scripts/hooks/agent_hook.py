#!/usr/bin/env python3
"""Runtime-agnostic agent guard hooks.

usage: agent_hook.py <claude|codex|copilot> <pretooluse|posttooluse>

Reads one hook payload on stdin, applies every guard that matches the tool,
and answers in the caller runtime's own deny dialect. Silence means allow.

Guards:
  rg          ripgrep recursion flags that actually mean --replace
  impact      edits to a repository file no codebase-map query has covered

Exit codes: 0 always for a decided call; 0 with no output means allow.
Any guard that cannot decide stays silent, because a guard that fails closed
on its own bugs would brick every edit in every runtime at once.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
import time
from pathlib import Path

STATE_ROOT = Path(
    os.environ.get("HARD_ENG_HOOK_STATE")
    or Path.home() / ".cache" / "hard-eng" / "agent-hooks"
)
CLEARED_TTL_SECONDS = 90 * 60

BOUNDARIES = {";", "&&", "||", "|", "&", "(", ")"}
COMMAND_WRAPPERS = {"command", "env", "nice", "nohup", "rtk", "sudo", "time"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")
SHORT_FLAG_CLUSTER = re.compile(r"^-[A-Za-z]+$")
GLUED_REPLACE = re.compile(r"r[A-Za-z]+")

SHELL_TOOLS = {"bash", "shell", "run_command", "terminal"}
EDIT_TOOLS = {
    "apply_patch",
    "create",
    "create_file",
    "edit",
    "edit_file",
    "multiedit",
    "notebookedit",
    "str_replace",
    "str_replace_editor",
    "write",
    "write_file",
}
PATH_KEYS = ("file_path", "filePath", "path", "file", "notebook_path", "notebookPath")
PATCH_PATH = re.compile(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", re.MULTILINE)

# A denied edit tool is not a protected file: agents rewrite the same file from
# the shell instead. These name the ways a shell command writes one.
REDIRECT = re.compile(r"(?:^|[\s;|&])>>?\s*([^\s;|&<>]+)")
DD_TARGET = re.compile(r"\bof=([^\s;|&]+)")
INLINE_OPEN = re.compile(r"""open\(\s*['"]([^'"]+)['"]\s*,\s*['"][^'"]*[wa+]""")
INLINE_WRITE_FILE = re.compile(r"""write(?:File|_text|Text)\w*\(\s*['"]([^'"]+)['"]""")
INPLACE_FLAG = re.compile(r"^--in-place|^-[A-Za-z0-9.]*i")
INPLACE_TOOLS = {"awk", "gsed", "perl", "ruby", "sed"}
APPEND_TOOLS = {"tee"}
DESTINATION_TOOLS = {"cp", "install", "mv", "rsync"}

# Prose and data carry no call graph, so a map query proves nothing about them.
EXEMPT_SUFFIXES = {
    ".csv",
    ".json",
    ".lock",
    ".md",
    ".mdx",
    ".rst",
    ".sql",
    ".svg",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}

MAP_CLI = "codebase-memory-mcp"
REFRESH_CALLS = ("index_repository", "detect_changes", "index_status")
RESPONSE_PATH = re.compile(r'\\?"file_path\\?"\s*:\s*\\?"([^"\\]+)')


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


class Call:
    """One tool invocation, normalised across runtimes."""

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        raw_name = payload.get("tool_name") or payload.get("toolName") or ""
        self.tool = str(raw_name).strip()
        self.key = self.tool.lower().rsplit("__", 1)[-1]
        args = (
            payload.get("tool_input")
            or payload.get("toolArgs")
            or payload.get("tool_args")
            or payload.get("arguments")
        )
        # Copilot sends arguments as a string: encoded JSON for most tools,
        # and the raw patch body for apply_patch.
        self.text = ""
        if isinstance(args, str):
            self.text = args
            try:
                args = json.loads(args)
            except ValueError:
                args = None
        self.args = args if isinstance(args, dict) else {}
        self.session = str(
            payload.get("session_id") or payload.get("sessionId") or "shared"
        )
        self.cwd = str(payload.get("cwd") or payload.get("workingDirectory") or os.getcwd())

    @property
    def command(self) -> str | None:
        value = self.args.get("command")
        return value if isinstance(value, str) else None

    def response_text(self) -> str:
        for key in ("tool_response", "toolResponse", "tool_output", "output", "result"):
            value = self.payload.get(key)
            if value is None:
                continue
            return value if isinstance(value, str) else json.dumps(value)
        return ""

    def resolve(self, targets: list[str], bases: list[Path] | None = None) -> list[Path]:
        roots = bases or [Path(self.cwd)]
        resolved = []
        for raw in targets:
            path = Path(raw.strip().strip("\"'"))
            if not path.name:
                continue
            if path.is_absolute():
                resolved.append(path)
                continue
            resolved.extend(root / path for root in roots)
        return resolved

    def shell_bases(self, tokens: list[str]) -> list[Path]:
        """`cd elsewhere && write` moves the target, so every cd is a candidate root."""
        roots = [Path(self.cwd)]
        for index in command_positions(tokens):
            if os.path.basename(tokens[index]) != "cd" or index + 1 >= len(tokens):
                continue
            argument = tokens[index + 1]
            if argument in BOUNDARIES or argument.startswith("-"):
                continue
            candidate = Path(argument.strip("\"'"))
            roots.append(candidate if candidate.is_absolute() else roots[0] / candidate)
        return roots

    def edit_targets(self) -> list[Path]:
        targets: list[str] = []
        for key in PATH_KEYS:
            value = self.args.get(key)
            if isinstance(value, str) and value:
                targets.append(value)
        bodies = [self.args.get(key) for key in ("command", "patch", "input", "content")]
        for value in (*bodies, self.text):
            if isinstance(value, str):
                targets.extend(PATCH_PATH.findall(value))
        return self.resolve(targets)

    def shell_write_targets(self) -> list[Path]:
        command = self.command
        if not command:
            return []
        targets: list[str] = [
            *REDIRECT.findall(command),
            *DD_TARGET.findall(command),
            *INLINE_OPEN.findall(command),
            *INLINE_WRITE_FILE.findall(command),
            *PATCH_PATH.findall(command),
        ]
        try:
            tokens = shell_tokens(command)
        except ValueError:
            return self.resolve(targets)
        bases = self.shell_bases(tokens)
        for index in command_positions(tokens):
            name = os.path.basename(tokens[index])
            if name not in INPLACE_TOOLS | APPEND_TOOLS | DESTINATION_TOOLS:
                continue
            inplace = False
            arguments: list[str] = []
            for token in tokens[index + 1 :]:
                if token in BOUNDARIES:
                    break
                if token.startswith("-") and token != "-":
                    inplace = inplace or bool(INPLACE_FLAG.match(token))
                    continue
                arguments.append(token)
            if name in APPEND_TOOLS:
                targets.extend(arguments)
            elif name in DESTINATION_TOOLS and len(arguments) >= 2:
                targets.append(arguments[-1])
            elif inplace:
                # A script expression is not a path, so it drops out on the exists() test.
                targets.extend(arguments)
        return self.resolve(targets, bases)


def repo_root(path: Path) -> Path | None:
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def state_path(session: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", session)[:120] or "shared"
    return STATE_ROOT / f"{safe}.json"


def read_state(session: str) -> dict:
    try:
        return json.loads(state_path(session).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def write_state(session: str, state: dict) -> None:
    path = state_path(session)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_text(json.dumps(state), encoding="utf-8")
        os.replace(temporary, path)
    except OSError:
        pass


def cleared_paths(state: dict) -> dict:
    cleared = state.get("cleared")
    return cleared if isinstance(cleared, dict) else {}


def is_cleared(state: dict, target: Path) -> bool:
    """A map result clears a file wherever it lives; queries cross repositories."""
    absolute = str(target.resolve())
    now = time.time()
    for known, stamp in cleared_paths(state).items():
        if not isinstance(stamp, (int, float)) or now - stamp >= CLEARED_TTL_SECONDS:
            continue
        if absolute == known or absolute.endswith("/" + known.lstrip("/")):
            return True
    return False


def guard_rg(call: Call) -> str | None:
    if call.key not in SHELL_TOOLS or not call.command:
        return None
    try:
        tokens = shell_tokens(call.command)
    except ValueError:
        return None
    for index in command_positions(tokens):
        if os.path.basename(tokens[index]) != "rg":
            continue
        flag = bad_flag_after(tokens, index)
        if flag is not None:
            return (
                f"Blocked {flag}: ripgrep uses -r for --replace, not recursion. "
                "Use rg -n or rg -ln; rg recurses by default."
            )
    return None


def impact_message(root: Path, unseen: list[str], refreshed: bool) -> str:
    files = ", ".join(unseen[:3]) + (" …" if len(unseen) > 3 else "")
    steps = [
        f"{MAP_CLI} cli index_repository '{{\"repo_path\":\"{root}\"}}'  # only if stale",
        f"{MAP_CLI} cli search_graph "
        '\'{"project":"<project>","query":"<what this change does>","limit":10}\'',
    ]
    if refreshed:
        steps = steps[1:]
    joined = "\n  ".join(steps)
    return (
        f"Blocked edit to {files}: no codebase-map query has covered it this session, "
        "so the other places that do the same thing are still unknown. "
        f"Ask the map first, then repeat this edit:\n  {joined}\n"
        "Every file the query names is unblocked for 90 minutes."
    )


def guard_impact(call: Call) -> str | None:
    if call.key in EDIT_TOOLS:
        targets = call.edit_targets()
    elif call.key in SHELL_TOOLS:
        targets = call.shell_write_targets()
    else:
        return None
    if not targets:
        return None
    state = read_state(call.session)
    refreshed = bool(state.get("refreshed_at"))
    unseen: list[str] = []
    root: Path | None = None
    for target in targets:
        # A file that does not exist yet has no callers to miss.
        if target.suffix.lower() in EXEMPT_SUFFIXES or not target.exists():
            continue
        found = repo_root(target)
        if found is None or is_cleared(state, target):
            continue
        root = found
        try:
            unseen.append(str(target.resolve().relative_to(found.resolve())))
        except ValueError:
            unseen.append(str(target))
    if root is None or not unseen:
        return None
    return impact_message(root, unseen, refreshed)


def record_map_call(call: Call) -> None:
    """Remember what the codebase map has already shown this session."""
    text = f"{call.tool} {call.command or ''}"
    if MAP_CLI not in text and "codebase_memory" not in call.key:
        return
    state = read_state(call.session)
    if any(name in text for name in REFRESH_CALLS):
        state["refreshed_at"] = time.time()
    cleared = state.setdefault("cleared", {})
    if not isinstance(cleared, dict):
        cleared = {}
        state["cleared"] = cleared
    now = time.time()
    for raw in RESPONSE_PATH.findall(call.response_text()):
        cleared[raw] = now
    write_state(call.session, state)


def deny(runtime: str, reason: str) -> int:
    if runtime == "copilot":
        body = {"permissionDecision": "deny", "permissionDecisionReason": reason}
    else:
        body = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    print(json.dumps(body))
    return 0


def main() -> int:
    if len(sys.argv) != 3:
        print("agent_hook: usage: agent_hook.py <runtime> <event>", file=sys.stderr)
        return 0
    runtime, event = sys.argv[1], sys.argv[2].lower()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    call = Call(payload)
    if event == "posttooluse":
        record_map_call(call)
        return 0
    for guard in (guard_rg, guard_impact):
        try:
            reason = guard(call)
        except Exception:  # a broken guard must not brick every edit
            continue
        if reason:
            return deny(runtime, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

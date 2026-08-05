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
import subprocess
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
GLOB_CHARACTERS = "*?["
# `2>&1` splits into an ampersand and a digit, and the digit then reads as the
# next command in the pipeline, which would make every such read look unknown.
FD_DUP = re.compile(r"\d*>&\d*")

# Naming the ways a command writes can never be complete, so a command that
# names a source file must instead prove it only reads. Anything absent from
# this list — interpreters, unknown tools, indirection — counts as a writer.
READ_ONLY_TOOLS = {
    "awk", "basename", "cat", "cd", "cksum", "cmp", "column", "comm", "cut",
    "diff", "dirname", "du", "echo", "file", "find", "git", "grep", "head",
    "jq", "ls", "md5", "md5sum", "nl", "od", "printf", "pwd", "readlink",
    "realpath", "rg", "sed", "sha1sum", "sha256sum", "shasum", "sort", "stat",
    "strings", "tail", "tr", "true", "uniq", "wc", "which", "xxd",
}
# Running a file is normally reading it, and the PostToolUse net undoes whatever
# these do change, so blocking them before the fact only costs false refusals.
EXECUTOR_TOOLS = {
    "bash", "bun", "cargo", "dash", "deno", "dotnet", "flutter", "go", "gradle",
    "jest", "make", "mvn", "node", "npm", "npx", "php", "pnpm", "pytest",
    "python", "python3", "rustc", "sh", "swift", "tsx", "uv", "uvx", "vitest",
    "yarn", "zsh",
}
# `timeout 900 python3 x.py` runs python, not a program called timeout, and
# reading the wrapper as the command misreads the whole line.
WRAPPER_TOOLS = {"command", "env", "nice", "nohup", "stdbuf", "time", "timeout"}
WRAPPER_ARGUMENT = re.compile(r"^(-|\d+(\.\d+)?[smhd]?$|[A-Za-z_][A-Za-z0-9_]*=)")
GIT_READ_SUBCOMMANDS = {
    "blame", "cat-file", "describe", "diff", "grep", "log", "ls-files",
    "ls-tree", "rev-list", "rev-parse", "shortlog", "show", "status",
}
FIND_WRITE_ACTIONS = {"-delete", "-exec", "-execdir", "-fprint", "-fprintf", "-ok", "-okdir"}
# Indirection hides the real command from every check below it.
INDIRECTION = ("$(", "`", "${", "eval ", " -c ", "xargs", "|&")

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


def segment(tokens: list[str], command_index: int) -> list[str]:
    """Tokens belonging to one command, stopping at the next shell boundary."""
    taken: list[str] = []
    for token in tokens[command_index + 1 :]:
        if token in BOUNDARIES:
            break
        taken.append(token)
    return taken


def reads_only(command: str, tokens: list[str]) -> bool:
    # Redirection is not disqualifying: its target is captured as a write
    # already, and reading a source file into a scratch copy is still a read.
    if any(marker in command for marker in INDIRECTION):
        return False
    positions = command_positions(tokens)
    if not positions:
        return False
    for index in positions:
        while index < len(tokens) and os.path.basename(tokens[index]) in WRAPPER_TOOLS:
            index += 1
            while index < len(tokens) and WRAPPER_ARGUMENT.match(tokens[index]):
                index += 1
        if index >= len(tokens):
            continue
        name = os.path.basename(tokens[index])
        if name in EXECUTOR_TOOLS:
            continue
        if name not in READ_ONLY_TOOLS:
            return False
        arguments = segment(tokens, index)
        flags = [token for token in arguments if token.startswith("-") and token != "-"]
        if name in INPLACE_TOOLS and any(INPLACE_FLAG.match(flag) for flag in flags):
            return False
        if name == "find" and any(token in FIND_WRITE_ACTIONS for token in arguments):
            return False
        if name == "git":
            words = [token for token in arguments if not token.startswith("-")]
            if not words or words[0] not in GIT_READ_SUBCOMMANDS:
                return False
    return True


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

    def shell_named_targets(self, tokens: list[str], bases: list[Path]) -> list[Path]:
        """Every path a non-read-only command names, globs included."""
        named: list[str] = []
        # `eval "sed -i '' f"` arrives as one token, so a quoted script is read as
        # the several words it will become.
        widened: list[str] = []
        for token in tokens:
            widened.append(token)
            if any(character.isspace() for character in token):
                try:
                    widened.extend(shell_tokens(token))
                except ValueError:
                    widened.extend(token.split())
        for token in widened:
            if token in BOUNDARIES or token.startswith("-"):
                continue
            cleaned = token.strip().strip("\"'")
            if not cleaned:
                continue
            if any(character in cleaned for character in GLOB_CHARACTERS):
                for base in bases:
                    try:
                        named.extend(str(match) for match in base.glob(cleaned))
                    except (OSError, ValueError, IndexError, NotImplementedError):
                        continue
                continue
            named.append(cleaned)
        return self.resolve(named, bases)

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
            tokens = shell_tokens(FD_DUP.sub(" ", command))
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
        resolved = self.resolve(targets, bases)
        if not reads_only(command, tokens):
            resolved.extend(self.shell_named_targets(tokens, bases))
        return resolved


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
        # A file that does not exist yet has no callers to miss, and a directory
        # is not a call site.
        if target.suffix.lower() in EXEMPT_SUFFIXES or not target.is_file():
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


RESOLVING = (
    "MERGE_HEAD", "REBASE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD",
    "BISECT_LOG", "rebase-merge", "rebase-apply",
)

GIT_ENV_HOME = Path(__file__).resolve().parents[2] / "skills" / "deterministic-checks" / "scripts"
GIT_SAFE = False


def scrub_git_environment() -> bool:
    """Drop the per-invocation Git variables this process may have inherited.

    Git exports GIT_DIR and friends to hooks, and a child that inherits them
    resolves `-C`, discovery and the index against the hook's own checkout rather
    than the one the agent is working in. False means the canonical sanitizer was
    unreachable, and no git call below may run.
    """
    sys.path.insert(0, str(GIT_ENV_HOME))
    try:
        from git_env import scrub_environ  # type: ignore[import-not-found]
    except Exception:
        return False
    finally:
        if sys.path[:1] == [str(GIT_ENV_HOME)]:
            del sys.path[0]
    scrub_environ()
    return True


def mid_operation(root: Path) -> bool:
    """A merge, rebase, cherry-pick or bisect in flight: restoring a file then is
    not an undo, it is throwing away a resolution nobody can reproduce."""
    if not GIT_SAFE:
        return True
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if result.returncode != 0:
        return True
    git_dir = Path(result.stdout.strip() or ".git")
    if not git_dir.is_absolute():
        git_dir = root / git_dir
    return any((git_dir / marker).exists() for marker in RESOLVING)


def git_dirty(root: Path) -> set[str]:
    """Tracked files git currently sees as changed, whoever changed them.

    Unmerged paths are left out: they are a conflict being resolved, and the net
    must never be the thing that discards a half-finished resolution.
    """
    if not GIT_SAFE:
        return set()
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1", "-uno", "-z"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if result.returncode != 0:
        return set()
    changed = set()
    for entry in result.stdout.split("\0"):
        if len(entry) <= 3:
            continue
        state = entry[:2]
        if "U" in state or state in {"DD", "AA"}:
            continue
        # Only the worktree column. A command's own write always leaves the file
        # differing from the index; a staged-clean file is somebody else staging
        # work, and restoring it from that same index would be a no-op at best.
        if state[1] not in {"M", "D", "T"}:
            continue
        changed.add(entry[3:])
    return changed


COMPANY_TTL_SECONDS = 30 * 60


def repo_register(root: Path, session: str) -> list[str]:
    """Sessions other than this one that ran a command in this repository lately.

    Git can say a file changed; it cannot say who changed it. When a second agent
    is working in the same checkout, an undo here would land on their edit, so the
    net has to know it has company.
    """
    directory = STATE_ROOT / "repos"
    record = directory / (str(root).strip("/").replace("/", "-")[-120:] + ".json")
    now = time.time()
    try:
        loaded = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        loaded = None
    seen: dict = loaded if isinstance(loaded, dict) else {}
    others = [
        name
        for name, stamp in seen.items()
        if name != session and isinstance(stamp, (int, float)) and now - stamp < COMPANY_TTL_SECONDS
    ]
    seen = {
        name: stamp
        for name, stamp in seen.items()
        if isinstance(stamp, (int, float)) and now - stamp < COMPANY_TTL_SECONDS
    }
    seen[session] = now
    try:
        directory.mkdir(parents=True, exist_ok=True)
        record.write_text(json.dumps(seen), encoding="utf-8")
    except OSError:
        pass
    return others


def snapshot_repository(call: Call) -> None:
    """A command can write through a script this hook never sees, so record the before."""
    if call.key not in SHELL_TOOLS:
        return
    root = repo_root(Path(call.cwd))
    if root is None:
        return
    repo_register(root, call.session)
    state = read_state(call.session)
    snapshots = state.setdefault("snapshots", {})
    if not isinstance(snapshots, dict):
        snapshots = {}
        state["snapshots"] = snapshots
    snapshots[str(root)] = sorted(git_dirty(root))
    write_state(call.session, state)


def revert_unmapped_writes(call: Call) -> str | None:
    """Restore any source file this command changed without a map query behind it."""
    if call.key not in SHELL_TOOLS:
        return None
    root = repo_root(Path(call.cwd))
    if root is None or mid_operation(root):
        return None
    state = read_state(call.session)
    snapshots = state.get("snapshots")
    before = snapshots.get(str(root)) if isinstance(snapshots, dict) else None
    if not isinstance(before, list):
        return None
    changed = [
        relative
        for relative in sorted(git_dirty(root) - set(before))
        if (root / relative).suffix.lower() not in EXEMPT_SUFFIXES
        and not is_cleared(state, root / relative)
    ]
    if not changed:
        return None
    company = repo_register(root, call.session)
    if company:
        return (
            f"{', '.join(changed)} changed during this command and no codebase-map query "
            "has covered them. Another agent session is working in this checkout, so this "
            "was left alone rather than undone on top of their edit. Ask the map about "
            "these files before changing them:\n"
            f"  {MAP_CLI} cli search_graph "
            '\'{"project":"<project>","query":"<what this change does>","limit":10}\''
        )
    reverted: list[str] = []
    rescue = STATE_ROOT / "rescued" / f"{call.session}-{int(time.time())}"
    for relative in changed:
        target = root / relative
        # Undoing someone's work irrecoverably would be worse than the write this
        # is undoing, so the discarded bytes are kept before git touches the file.
        try:
            copy = rescue / relative
            copy.parent.mkdir(parents=True, exist_ok=True)
            copy.write_bytes(target.read_bytes())
        except OSError:
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(root), "checkout", "--", relative],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            reverted.append(relative)
    if not reverted:
        return None
    return (
        f"Reverted {', '.join(reverted)}: that command changed a source file no "
        "codebase-map query has covered this session, so the change was undone rather "
        "than left half-known. Ask the map about the file, then make the change again:\n"
        f"  {MAP_CLI} cli search_graph "
        '\'{"project":"<project>","query":"<what this change does>","limit":10}\'\n'
        f"The undone bytes are kept at {rescue} if the change was wanted after all."
    )


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


def report(runtime: str, message: str) -> int:
    """PostToolUse cannot deny; it can only make sure nobody misses what it did."""
    print(message, file=sys.stderr)
    if runtime != "copilot":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": message,
                    }
                }
            )
        )
    return 0


def main() -> int:
    if len(sys.argv) != 3:
        print("agent_hook: usage: agent_hook.py <runtime> <event>", file=sys.stderr)
        return 0
    runtime, event = sys.argv[1], sys.argv[2].lower()
    global GIT_SAFE
    GIT_SAFE = scrub_git_environment()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        return 0
    if not isinstance(payload, dict):
        return 0
    call = Call(payload)
    try:
        # Every call, not only the shell ones: a session editing through its edit
        # tool is still company that another session's net must not overwrite.
        here = repo_root(Path(call.cwd))
        if here is not None and event != "posttooluse":
            repo_register(here, call.session)
    except Exception:
        pass
    if event == "posttooluse":
        record_map_call(call)
        try:
            undone = revert_unmapped_writes(call)
        except Exception:  # a broken net must not break the tool that already ran
            undone = None
        if undone:
            return report(runtime, undone)
        return 0
    for guard in (guard_rg, guard_impact):
        try:
            reason = guard(call)
        except Exception:  # a broken guard must not brick every edit
            continue
        if reason:
            return deny(runtime, reason)
    try:
        snapshot_repository(call)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

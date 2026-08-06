#!/usr/bin/env python3
"""Runtime-agnostic agent guard hooks.

usage: agent_hook.py <claude|codex|copilot> <pretooluse|posttooluse>

Reads one hook payload on stdin, applies every guard that matches the tool,
and answers in the caller runtime's own dialect. Silence means allow.

Guards:
  rg          ripgrep recursion flags that actually mean --replace
  discard     git commands that would throw uncommitted work away
  impact      hands the caller the map's view of a file it is about to edit

The impact guard injects and never denies. A deny can only prove a query ran,
not that anything was learned from it, and its unblock condition is a ranked
search that frequently omits the very file being edited — so it refused
informed edits and admitted ignorant ones. Injection runs the query itself, on
every edit, and cannot stall. Shell writes stay covered by the PostToolUse net,
which asks git what actually changed instead of parsing the command.

The discard guard denies, because it covers the one case the net cannot: a
discard leaves the file matching HEAD, so afterwards nothing can tell that
anything was ever there. The net itself only undoes recognised source files
this command's own writes touched, and only a few at a time — everything else
it reports, because an undo it gets wrong is unrecoverable too.

Exit codes: 0 always for a decided call; 0 with no output means allow.
Any guard that cannot decide stays silent, because a guard that fails closed
on its own bugs would brick every edit in every runtime at once.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

# shlex and shutil are imported where they are used. Both cost real milliseconds
# to import and every tool call in every runtime pays for a module-level import,
# while the paths that need them are a minority of calls.

STATE_ROOT = Path(
    os.environ.get("HARD_ENG_HOOK_STATE")
    or Path.home() / ".cache" / "hard-eng" / "agent-hooks"
)
CLEARED_TTL_SECONDS = 90 * 60
# Coarse filesystems round mtime, so a write can look a shade older than the command.
MTIME_TOLERANCE_SECONDS = 1.0
REVERT_FILE_LIMIT = 3
RESCUE_TTL_SECONDS = 14 * 24 * 60 * 60
SESSION_TTL_SECONDS = 7 * 24 * 60 * 60

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

# Code the map can hold a call graph for. This is an allowlist rather than a list of
# prose exclusions because the revert net acts on it: anything unrecognised — a binary,
# a captured screenshot, a generated asset — has to be structurally out of reach.
SOURCE_SUFFIXES = {
    ".bash",
    ".c",
    ".cc",
    ".cjs",
    ".cpp",
    ".cs",
    ".css",
    ".dart",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".kts",
    ".m",
    ".mjs",
    ".mm",
    ".php",
    ".py",
    ".rb",
    ".rs",
    ".scala",
    ".scss",
    ".sh",
    ".svelte",
    ".swift",
    ".ts",
    ".tsx",
    ".vue",
    ".zsh",
}


def map_indexable(relative: str) -> bool:
    """The extractor walks visible directories only, so nothing under a dotted
    one can ever appear in a result."""
    return not any(part.startswith(".") for part in Path(relative).parts)


MAP_CLI = "codebase-memory-mcp"
MAP_TIMEOUT_SECONDS = 5
REFRESH_CALLS = ("index_repository", "detect_changes", "index_status")
# search_code reaches files whose symbols the extractor never emits (Dart extension
# bodies, for one) but names them under "file", so both keys have to clear.
RESPONSE_PATH = re.compile(r'\\?"(?:file_path|file)\\?"\s*:\s*\\?"([^"\\]+)')
CONTEXT_FILE_LIMIT = 3
CONTEXT_LINE_LIMIT = 12


def shell_tokens(command: str) -> list[str]:
    import shlex

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
        # Copilot's key is toolResult. Missing it cost a live session three
        # reverts: the agent ran the map query it was told to run, nothing was
        # recorded as covered, and its next write was undone all over again.
        for key in (
            "tool_response",
            "toolResponse",
            "toolResult",
            "tool_result",
            "tool_output",
            "output",
            "result",
        ):
            value = self.payload.get(key)
            if value is None:
                continue
            return value if isinstance(value, str) else json.dumps(value)
        return ""

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
        base = Path(self.cwd)
        resolved: list[Path] = []
        for raw in targets:
            path = Path(raw.strip().strip("\"'"))
            if not path.name:
                continue
            resolved.append(path if path.is_absolute() else base / path)
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
    """A map result covers a file wherever it lives; queries cross repositories."""
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


DISCARD_WHOLE_TREE = {".", "./", "*", ":/"}
# Options git accepts before the subcommand, and which swallow the next token.
# Skipping them is what keeps `git -C <path> checkout` from reading <path> as the
# subcommand: the repository's own rules ask for exactly that form.
GIT_VALUE_OPTIONS = {
    "-C",
    "-c",
    "--exec-path",
    "--git-dir",
    "--namespace",
    "--super-prefix",
    "--work-tree",
}


def git_prefix(rest: list[str]) -> tuple[list[str], str | None]:
    """The tokens from the subcommand onward, and any -C directory in front of it."""
    directory = None
    index = 0
    while index < len(rest):
        token = rest[index]
        if token in GIT_VALUE_OPTIONS:
            if token == "-C" and index + 1 < len(rest):
                directory = rest[index + 1]
            index += 2
            continue
        if token.startswith("-"):
            if token.startswith("--git-dir=") or token.startswith("--work-tree="):
                directory = token.split("=", 1)[1]
            index += 1
            continue
        break
    return rest[index:], directory


def discard_targets(tokens: list[str], index: int) -> tuple[str, list[str], str | None] | None:
    """The git subcommand at `index`, the paths it would overwrite, and its -C root.

    An empty path list means the whole worktree. None means this git call does not
    throw work away: `git checkout <branch>` refuses to clobber a dirty file, and
    `git reset` without --hard only moves the index.
    """
    raw: list[str] = []
    for token in tokens[index + 1 :]:
        if token in BOUNDARIES:
            break
        raw.append(token)
    rest, directory = git_prefix(raw)
    words = [token for token in rest if not token.startswith("-")]
    if not words:
        return None
    verb = words[0]
    flags = {token for token in rest if token.startswith("-")}
    if verb == "reset":
        return ("reset --hard", [], directory) if "--hard" in flags else None
    if verb == "clean":
        return ("clean", [], directory) if any("f" in flag for flag in flags) else None
    # `pop` and `apply` restore work rather than throw it away.
    if verb == "stash" and len(words) > 1 and words[1] in {"drop", "clear"}:
        return (f"stash {words[1]}", [], directory)
    if verb not in {"checkout", "restore"}:
        return None
    paths = words[1:]
    if "--" in rest:
        paths = rest[rest.index("--") + 1 :]
    if not paths:
        # `git checkout` with no path is a branch switch, which git already
        # refuses when it would overwrite local changes.
        return None
    if any(path in DISCARD_WHOLE_TREE for path in paths):
        return (verb, [], directory)
    return (verb, paths, directory)


def guard_discard(call: Call) -> str | None:
    """Refuse a git command that would silently destroy uncommitted work.

    This asks git what is actually dirty rather than reading intent out of the
    command text, so it fires only when real content would be lost. The revert net
    cannot cover this: a discard leaves the file matching HEAD, so nothing
    downstream can tell that anything was there.
    """
    if call.key not in SHELL_TOOLS or not call.command:
        return None
    try:
        tokens = shell_tokens(call.command)
    except ValueError:
        return None
    working = Path(call.cwd)
    for index in command_positions(tokens):
        name = os.path.basename(tokens[index])
        if name == "cd":
            # `cd elsewhere && git restore x` discards elsewhere's x, not this
            # checkout's, so the line's own directory has to be followed.
            argument = next(
                (
                    token
                    for token in tokens[index + 1 :]
                    if token not in BOUNDARIES and not token.startswith("-")
                ),
                None,
            )
            working = working / argument if argument else Path.home()
            continue
        if name != "git":
            continue
        found = discard_targets(tokens, index)
        if found is None:
            continue
        verb, paths, directory = found
        # `git -C <dir>` runs against that checkout, not the caller's.
        base = working if directory is None else working / directory
        root = repo_root(base)
        if root is None:
            continue
        dirty = git_dirty(root)
        if verb.startswith("stash") or verb == "clean":
            # Neither shows up in `git status` as a dirty tracked file, so there is
            # nothing to measure; both are destructive by definition.
            at_risk = []
        elif not paths:
            at_risk = sorted(dirty)
        else:
            targets = [(base / path).resolve() for path in paths]
            at_risk = sorted(
                relative
                for relative in dirty
                for target in targets
                if (root / relative).resolve() == target
                or target in (root / relative).resolve().parents
            )
            if not at_risk:
                continue
        listed = ", ".join(at_risk[:CONTEXT_FILE_LIMIT]) if at_risk else "this worktree"
        return (
            f"Blocked git {verb}: it would discard uncommitted work in {listed}, "
            "and nothing can restore it afterwards. Keep the work first:\n"
            f"  git -C {root} stash push -m <why> -- {' '.join(at_risk) or '.'}\n"
            "Then say what you are discarding and ask before running it again."
        )
    return None


def file_query(project: str, relative: str) -> dict:
    """The map's own arguments for one file.

    `pattern` greps content, so a file's own name matches only where some other
    file happens to mention it — asking about src/billing.py by name answers
    nothing. Anchoring `path_filter` on the path and matching any character is
    what actually asks about this file. The key is snake_case; the hyphenated
    spelling the CLI takes on the command line is ignored without complaint here.

    The dot in the path stays unescaped on purpose. This query is printed for an
    agent to paste, and fish eats the backslash inside single quotes, so an
    escaped path arrives as invalid JSON and the CLI answers `pattern is
    required`. Unescaped it is a regex any-character, which costs nothing here.
    """
    return {
        "project": project,
        "pattern": ".",
        "regex": True,
        "path_filter": relative + "$",
        "limit": 10,
    }


def map_query_hint(root: Path, relatives: list[str]) -> str:
    """The exact queries to run, already carrying this checkout's project and files."""
    return "\n".join(
        f"  echo '{json.dumps(file_query(str(root), relative))}' | {MAP_CLI} cli search_code"
        for relative in relatives[:CONTEXT_FILE_LIMIT]
    )


def map_call(tool: str, arguments: dict) -> dict | None:
    """One bounded map query. Any failure is silence, never a stalled edit.

    Arguments go in on stdin: the CLI deprecated its raw-JSON argument in 0.9.0,
    and stdin needs no per-tool knowledge of flag names.
    """
    import shutil

    if shutil.which(MAP_CLI) is None:
        return None
    try:
        result = subprocess.run(
            [MAP_CLI, "cli", tool],
            input=json.dumps(arguments),
            capture_output=True,
            text=True,
            timeout=MAP_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    # The binary prints an unstructured startup line before the JSON body.
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            return json.loads(line)
        except ValueError:
            continue
    return None


def summarise(response: dict | None, seen: set[str]) -> list[str]:
    lines: list[str] = []
    if not isinstance(response, dict):
        return lines
    for entry in response.get("results") or []:
        if not isinstance(entry, dict):
            continue
        where = str(entry.get("file_path") or entry.get("file") or "")
        name = str(entry.get("name") or entry.get("node") or entry.get("qualified_name") or "")
        if not where or not name:
            continue
        label = str(entry.get("label") or "").strip()
        start = entry.get("start_line")
        place = f"{where}:{start}" if isinstance(start, int) else where
        line = f"  {name}{f' ({label})' if label else ''} — {place}"
        if line in seen:
            continue
        seen.add(line)
        lines.append(line)
    return lines


def impact_context(call: Call) -> str | None:
    """What the map knows about the files this call is about to write."""
    if call.key not in EDIT_TOOLS:
        return None
    targets = call.edit_targets()
    if not targets:
        return None
    state = read_state(call.session)
    root: Path | None = None
    wanted: list[str] = []
    for target in targets:
        # A file that does not exist yet has no callers to miss, and a directory
        # is not a call site.
        if target.suffix.lower() not in SOURCE_SUFFIXES or not target.is_file():
            continue
        found = repo_root(target)
        if found is None:
            continue
        try:
            relative = str(target.resolve().relative_to(found.resolve()))
        except ValueError:
            relative = str(target)
        if not map_indexable(relative) or relative in wanted:
            continue
        root = found
        wanted.append(relative)
    if root is None or not wanted:
        return None

    # The map resolves a project by its root path, so nothing has to be looked up
    # first; a root it has never indexed simply answers with an error and no results.
    project = str(root)

    cleared = state.setdefault("cleared", {})
    if not isinstance(cleared, dict):
        cleared = {}
        state["cleared"] = cleared
    now = time.time()
    sections: list[str] = []
    seen: set[str] = set()
    chosen = wanted[:CONTEXT_FILE_LIMIT]
    queries = [
        query
        for relative in chosen
        for query in (
            ("search_code", file_query(project, relative)),
            ("search_graph", {"project": project, "query": Path(relative).stem, "limit": 10}),
        )
    ]
    # Each query is its own map process and none reads another's answer, so they
    # run together; `seen` dedupes across sections and is order-dependent, which
    # is why the answers are consumed in the order they were asked. The import is
    # deferred because every hook invocation pays for a module-level one and only
    # this path uses it. Four workers, not one per query: each is a full map
    # process, and the widest real case is one patch touching three files.
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as pool:
        answers = list(pool.map(lambda query: map_call(*query), queries))
    for index, relative in enumerate(chosen):
        here, near = answers[2 * index], answers[2 * index + 1]
        for response in (here, near):
            for raw in RESPONSE_PATH.findall(json.dumps(response or {})):
                cleared[raw] = now
        lines = (summarise(here, seen) + summarise(near, seen))[:CONTEXT_LINE_LIMIT]
        if lines:
            sections.append(f"{relative} — related symbols the map knows:\n" + "\n".join(lines))
    write_state(call.session, state)
    if not sections:
        return None
    return (
        "Codebase map, before you write:\n"
        + "\n\n".join(sections)
        + "\nCheck these before changing shared behaviour. Nothing is blocked."
    )


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
    state = read_state(call.session)
    snapshots = state.setdefault("snapshots", {})
    if not isinstance(snapshots, dict):
        snapshots = {}
        state["snapshots"] = snapshots
    snapshots[str(root)] = {"files": sorted(git_dirty(root)), "at": time.time()}
    write_state(call.session, state)


def prune_state(now: float) -> None:
    """Session records and rescued bytes are a short-lived undo, not an archive."""
    marker = STATE_ROOT / "pruned.stamp"
    try:
        if now - marker.stat().st_mtime < SESSION_TTL_SECONDS / 7:
            return
    except OSError:
        pass
    try:
        STATE_ROOT.mkdir(parents=True, exist_ok=True)
        marker.write_text("", encoding="utf-8")
    except OSError:
        return
    aged = [(path, SESSION_TTL_SECONDS) for path in STATE_ROOT.glob("*.json")]
    aged += [(path, SESSION_TTL_SECONDS) for path in (STATE_ROOT / "repos").glob("*.json")]
    aged += [(path, RESCUE_TTL_SECONDS) for path in (STATE_ROOT / "rescued").glob("*")]
    for path, ttl in aged:
        try:
            if now - path.stat().st_mtime < ttl:
                continue
            if path.is_dir():
                import shutil

                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink()
        except OSError:
            continue


def written_since(target: Path, instant: float) -> bool:
    """Whether this file was really written after the command started.

    Being dirty is not proof of authorship: an editor autosave or a parallel session
    can dirty a file between the two hook calls, and reverting that would destroy work
    this command never touched.
    """
    try:
        return target.stat().st_mtime >= instant - MTIME_TOLERANCE_SECONDS
    except OSError:
        return False


def revert_unmapped_writes(call: Call) -> str | None:
    """Restore any source file this command changed without a map query behind it."""
    if call.key not in SHELL_TOOLS:
        return None
    root = repo_root(Path(call.cwd))
    if root is None:
        return None
    # The snapshot lookup is a file read and mid_operation spawns git, so ask the
    # cheap question first: with no snapshot there is nothing to compare against
    # and no decision to make. mid_operation still guards every path that reverts.
    state = read_state(call.session)
    snapshots = state.get("snapshots")
    snapshot = snapshots.get(str(root)) if isinstance(snapshots, dict) else None
    if not isinstance(snapshot, dict):
        return None
    before = snapshot.get("files")
    started = snapshot.get("at")
    if not isinstance(before, list) or not isinstance(started, (int, float)):
        return None
    if mid_operation(root):
        return None
    changed = [
        relative
        for relative in sorted(git_dirty(root) - set(before))
        if (root / relative).suffix.lower() in SOURCE_SUFFIXES
        and written_since(root / relative, started)
        and not is_cleared(state, root / relative)
    ]
    if not changed:
        return None
    named = ", ".join(changed[:CONTEXT_FILE_LIMIT])
    if len(changed) > CONTEXT_FILE_LIMIT:
        named += f" and {len(changed) - CONTEXT_FILE_LIMIT} more"
    held = None
    if repo_register(root, call.session):
        held = "another agent session is working in this checkout, so an undo here would land on their edit"
    elif len(changed) > REVERT_FILE_LIMIT:
        # A batch this size is a generator, a formatter or a sync, and putting one of
        # those back halfway leaves the tree in a state nobody wrote.
        held = f"{len(changed)} files at once is a generated or bulk change, not a stray edit"
    if held:
        return (
            f"{named} changed during this command and no codebase-map query has covered "
            f"them. Left in place: {held}. Ask the map about them before going further:\n"
            + map_query_hint(root, changed)
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
        + map_query_hint(root, reverted)
        + f"\nThe undone bytes are kept at {rescue} if the change was wanted after all."
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


def inject(runtime: str, event: str, message: str) -> int:
    """Add to what the caller knows without touching whether the call proceeds."""
    name = "PostToolUse" if event == "posttooluse" else "PreToolUse"
    if runtime == "copilot":
        body: dict = {"additionalContext": message}
    else:
        body = {
            "hookSpecificOutput": {
                "hookEventName": name,
                "additionalContext": message,
            }
        }
    print(json.dumps(body))
    return 0


def report(runtime: str, message: str) -> int:
    """PostToolUse cannot deny; it can only make sure nobody misses what it did."""
    print(message, file=sys.stderr)
    return inject(runtime, "posttooluse", message)


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
        prune_state(time.time())
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
    reason = None
    try:
        reason = guard_rg(call) or guard_discard(call)
    except Exception:  # a broken guard must not brick every edit
        reason = None
    if reason:
        return deny(runtime, reason)
    try:
        context = impact_context(call)
    except Exception:
        context = None
    try:
        snapshot_repository(call)
    except Exception:
        pass
    if context:
        return inject(runtime, event, context)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

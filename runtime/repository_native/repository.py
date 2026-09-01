"""Repository marker, rule-owner, and global-install discovery."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from . import DEFAULT_RELEASE_REPOSITORY, LAUNCHER_SCHEMA
from .errors import ConfigurationError
from .models import GlobalState, MarkerPolicy, RepositoryState

MAX_MARKER_BYTES = 1024 * 1024
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _git_env() -> dict[str, str]:
    return {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}


def git(root: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *arguments],
            check=check,
            capture_output=True,
            text=True,
            env=_git_env(),
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise ConfigurationError(f"Git could not inspect {root}: {error}") from error


def find_repository(start: Path) -> Path:
    candidate = start.resolve()
    result = git(candidate, "rev-parse", "--show-toplevel", check=False)
    if result.returncode != 0:
        raise ConfigurationError(f"not inside a Git repository: {candidate}")
    root = Path(result.stdout.strip()).resolve()
    if root == Path(root.anchor):
        raise ConfigurationError("the filesystem root cannot be a repository target")
    return root


def _tracked(root: Path, relative: str) -> bool:
    return git(root, "ls-files", "--error-unmatch", "--", relative, check=False).returncode == 0


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"{label} must be a regular file: {path}")


def _marker_policy(value: object) -> MarkerPolicy:
    if not isinstance(value, dict):
        raise ConfigurationError("hard_eng in hard-eng.gates.json must be an object")
    allowed = {"channel", "minimum_version", "release_repository", "schema_version"}
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"hard_eng has unsupported keys: {', '.join(unknown)}")
    if value.get("schema_version", 1) != 1:
        raise ConfigurationError("hard_eng.schema_version must be 1")
    channel = value.get("channel")
    if channel is not None and channel not in {"stable", "prerelease"}:
        raise ConfigurationError("hard_eng.channel must be stable or prerelease")
    minimum = value.get("minimum_version")
    if minimum is not None and (not isinstance(minimum, str) or not minimum.startswith("v")):
        raise ConfigurationError("hard_eng.minimum_version must be a release tag")
    release_repository = value.get("release_repository", DEFAULT_RELEASE_REPOSITORY)
    if release_repository != DEFAULT_RELEASE_REPOSITORY:
        raise ConfigurationError(f"hard_eng.release_repository must be {DEFAULT_RELEASE_REPOSITORY}")
    return MarkerPolicy(channel, minimum, release_repository)


def inspect_repository(start: Path) -> RepositoryState:
    root = find_repository(start)
    marker = root / "hard-eng.gates.json"
    if not marker.exists() and not marker.is_symlink():
        return RepositoryState(root, False, None, None)
    _regular_file(marker, "Hard Eng marker")
    if not _tracked(root, "hard-eng.gates.json"):
        raise ConfigurationError("hard-eng.gates.json exists but is not tracked by Git")
    raw = marker.read_bytes()
    if len(raw) > MAX_MARKER_BYTES:
        raise ConfigurationError("hard-eng.gates.json is too large")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ConfigurationError(f"hard-eng.gates.json is invalid JSON: {error}") from error
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ConfigurationError("hard-eng.gates.json must be a schema_version 1 object")
    agents = root / "AGENTS.md"
    _regular_file(agents, "repository AGENTS.md")
    if not _tracked(root, "AGENTS.md"):
        raise ConfigurationError("repository AGENTS.md must be tracked by Git")
    policy = _marker_policy(value["hard_eng"]) if "hard_eng" in value else None
    return RepositoryState(root, True, "sha256:" + hashlib.sha256(raw).hexdigest(), policy)


def require_claude_owner(repository: Path) -> None:
    claude = repository / "CLAUDE.md"
    _regular_file(claude, "repository CLAUDE.md")
    if not _tracked(repository, "CLAUDE.md"):
        raise ConfigurationError("repository CLAUDE.md must be tracked by Git")
    if claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
        raise ConfigurationError("repository CLAUDE.md must contain only @AGENTS.md")


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return False


def _contains(path: Path, text: str) -> bool:
    try:
        return (
            path.is_file()
            and not path.is_symlink()
            and path.stat().st_size <= MAX_MARKER_BYTES
            and text in path.read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError):
        return False


def _json_setting_matches(path: Path, key: str, expected: object) -> bool:
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MARKER_BYTES:
            return False
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get(key) == expected


def _hook_points_to(path: Path, expected: Path) -> bool:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MARKER_BYTES:
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, dict):
            pending.extend(current.values())
        elif isinstance(current, list):
            pending.extend(current)
        elif isinstance(current, str):
            try:
                tokens = shlex.split(current)
            except ValueError:
                continue
            for token in tokens:
                if Path(token).name == "agent-hook.sh" and _same_file(Path(token), expected):
                    return True
    return False


def _copilot_rules_wired(home: Path, root: Path) -> bool:
    configured = os.environ.get("COPILOT_CUSTOM_INSTRUCTIONS_DIRS", "")
    for value in configured.split(os.pathsep):
        if value and _same_file(Path(value) / "AGENTS.md", root / "AGENTS.md"):
            return True
    marker = "# >>> hard-eng managed Copilot instructions >>>"
    assignment = 'COPILOT_CUSTOM_INSTRUCTIONS_DIRS="$HOME/.agents"'
    fish_assignment = 'COPILOT_CUSTOM_INSTRUCTIONS_DIRS "$HOME/.agents"'
    profiles = (
        home / ".bash_profile",
        home / ".bashrc",
        home / ".zshenv",
        home / ".zprofile",
        home / ".zshrc",
        home / ".config/fish/config.fish",
    )
    return any(
        _contains(path, marker) and (_contains(path, assignment) or _contains(path, fish_assignment))
        for path in profiles
    )


def _global_identity(root: Path) -> str:
    manifest = root / ".hard-eng-release.json"
    if manifest.is_file() and not manifest.is_symlink():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            value = {}
        version = value.get("version")
        if isinstance(version, str) and version:
            return version
    if (root / ".git").exists():
        head = git(root, "rev-parse", "HEAD", check=False).stdout.strip()
        if COMMIT.fullmatch(head):
            dirty = git(root, "status", "--porcelain", check=False).stdout != ""
            return f"development@{head}{'-dirty' if dirty else ''}"
    return "development@unknown"


def inspect_global(home: Path, agent: str) -> GlobalState:
    root = home / ".agents"
    launcher = home / ".local/bin/hard-eng"
    hard_eng_paths = (
        root / ".hard-eng-release.json",
        root / "bin/hard-eng",
        root / "scripts/hooks/agent-hook.sh",
        launcher,
    )
    footprint = any(path.exists() or path.is_symlink() for path in hard_eng_paths)
    if not footprint:
        return GlobalState("absent", root, None, ())
    problems: list[str] = []
    if root.is_symlink() or not root.is_dir():
        problems.append(f"{root} is not a regular directory")
    required = (
        root / "AGENTS.md",
        root / "agents/he-learn/claude.md",
        root / "agents/he-learn/codex.toml",
        root / "agents/he-learn/copilot.agent.md",
        root / "output-styles/plain-english.md",
        root / "skills/plain-english/SKILL.md",
        root / "scripts/hooks/agent-hook.sh",
        root / "bin/hard-eng",
        root / "runtime/repository_native/__init__.py",
        root / "runtime/repository_native/cli.py",
        root / "runtime/repository_native/errors.py",
        root / "runtime/repository_native/mcp_server.py",
        root / "runtime/repository_native/models.py",
        root / "runtime/repository_native/release.py",
        root / "runtime/repository_native/repository.py",
        root / "runtime/repository_native/wiring.py",
    )
    for path in required:
        if not path.is_file():
            problems.append(f"missing {path}")
    if (root / "runtime/repository_native/__init__.py").is_file():
        try:
            source = (root / "runtime/repository_native/__init__.py").read_text(encoding="utf-8")
            module = ast.parse(source)
        except (OSError, UnicodeError, SyntaxError):
            problems.append("global launcher compatibility cannot be read")
        else:
            schemas = [
                node.value.value
                for node in module.body
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "LAUNCHER_SCHEMA" for target in node.targets)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, int)
            ]
            if schemas != [LAUNCHER_SCHEMA]:
                problems.append("global launcher compatibility does not match this launcher")
    if not _same_file(launcher, root / "bin/hard-eng"):
        problems.append(f"{launcher} does not point to the global Hard Eng launcher")
    if agent == "codex":
        if not _same_file(home / ".codex/AGENTS.md", root / "AGENTS.md"):
            problems.append("Codex global AGENTS.md is not wired to Hard Eng")
        if not _same_file(home / ".codex/agents/he-learn.toml", root / "agents/he-learn/codex.toml"):
            problems.append("Codex global agent configuration is missing")
        if not _hook_points_to(home / ".codex/hooks.json", root / "scripts/hooks/agent-hook.sh"):
            problems.append("Codex global guard hook is missing")
        if not _contains(home / ".codex/config.toml", "codebase-memory"):
            problems.append("Codex global MCP wiring is missing")
    elif agent == "claude":
        if not _contains(home / ".claude/CLAUDE.md", str(root / "AGENTS.md")) and not _contains(
            home / ".claude/CLAUDE.md", "@~/.agents/AGENTS.md"
        ):
            problems.append("Claude global rules are not wired to Hard Eng")
        if not _same_file(home / ".claude/skills", root / "skills"):
            problems.append("Claude global skills are not wired to Hard Eng")
        if not _same_file(home / ".claude/agents/he-learn.md", root / "agents/he-learn/claude.md"):
            problems.append("Claude global agent configuration is missing")
        if not _same_file(home / ".claude/output-styles", root / "output-styles"):
            problems.append("Claude global output styles are not wired to Hard Eng")
        if not _hook_points_to(home / ".claude/settings.json", root / "scripts/hooks/agent-hook.sh"):
            problems.append("Claude global guard hook is missing")
        if not _json_setting_matches(home / ".claude/settings.json", "outputStyle", "Plain English"):
            problems.append("Claude global plain-English output style is missing")
        if not _contains(home / ".claude.json", "codebase-memory"):
            problems.append("Claude global MCP wiring is missing")
    elif agent == "copilot":
        if not _copilot_rules_wired(home, root):
            problems.append("Copilot global rules are not wired to Hard Eng")
        if not _same_file(home / ".copilot/agents/he-learn.agent.md", root / "agents/he-learn/copilot.agent.md"):
            problems.append("Copilot global agent configuration is missing")
        if not _hook_points_to(home / ".copilot/hooks/hard-eng.json", root / "scripts/hooks/agent-hook.sh"):
            problems.append("Copilot global guard hook is missing")
        if not _contains(home / ".copilot/mcp-config.json", "codebase-memory"):
            problems.append("Copilot global MCP wiring is missing")
        if not _contains(home / ".copilot/settings.json", "includeCoAuthoredBy"):
            problems.append("Copilot global settings are missing")
    if problems:
        return GlobalState("broken", root, None, tuple(problems))
    return GlobalState("global", root, _global_identity(root), ())

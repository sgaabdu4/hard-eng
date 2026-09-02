"""Repository marker, rule-owner, and global-install discovery."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from . import DEFAULT_RELEASE_REPOSITORY, LAUNCHER_SCHEMA
from .errors import ConfigurationError
from .models import GlobalState, MarkerPolicy, ReleasePin, RepositoryState

MAX_MARKER_BYTES = 1024 * 1024
COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
RELEASE_TAG = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:-alpha\.g[0-9a-f]{40})?$")
OWNER_START = "# >>> hard-eng repository owners >>>"
OWNER_END = "# <<< hard-eng repository owners <<<"
AGENT_HOME_VARIABLES = {"codex": "CODEX_HOME", "claude": "CLAUDE_CONFIG_DIR", "copilot": "COPILOT_HOME"}
AGENT_LABELS = {"codex": "Codex", "claude": "Claude Code", "copilot": "Copilot CLI"}
RUNTIME_FILES = (
    "__init__.py",
    "adapters.py",
    "cli.py",
    "errors.py",
    "installer.py",
    "locking.py",
    "models.py",
    "prepare.py",
    "release.py",
    "repository.py",
    "shared.py",
    "wiring.py",
)


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


def git_path(root: Path, name: str) -> Path:
    result = git(root, "rev-parse", "--path-format=absolute", "--git-path", name, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        raise ConfigurationError(f"Git path could not be resolved: {name}")
    return Path(result.stdout.strip())


def _tracked(root: Path, relative: str) -> bool:
    return git(root, "ls-files", "--error-unmatch", "--", relative, check=False).returncode == 0


def _privately_owned(root: Path, relative: str) -> bool:
    result = git(root, "rev-parse", "--path-format=absolute", "--git-path", "info/exclude", check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return False
    exclude = Path(result.stdout.strip())
    if exclude.is_symlink() or not exclude.is_file() or exclude.stat().st_size > MAX_MARKER_BYTES:
        return False
    try:
        lines = exclude.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        return False
    starts = [index for index, line in enumerate(lines) if line == OWNER_START]
    ends = [index for index, line in enumerate(lines) if line == OWNER_END]
    if not starts and not ends:
        return False
    if len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]:
        raise ConfigurationError("Git private owner block has malformed Hard Eng markers")
    return f"/{relative}" in lines[starts[0] + 1 : ends[0]]


def _admitted(root: Path, relative: str) -> bool:
    return _tracked(root, relative) or _privately_owned(root, relative)


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"{label} must be a regular file: {path}")


def _release_pin(value: object) -> ReleasePin:
    if not isinstance(value, dict) or set(value) != {"tag", "archive_sha256", "manifest_sha256"}:
        raise ConfigurationError("hard_eng.pin must contain exactly tag, archive_sha256, and manifest_sha256")
    tag = value["tag"]
    if not isinstance(tag, str) or not RELEASE_TAG.fullmatch(tag):
        raise ConfigurationError("hard_eng.pin.tag must be a Hard Eng release tag")
    for name in ("archive_sha256", "manifest_sha256"):
        if not isinstance(value[name], str) or not SHA256.fullmatch(value[name]):
            raise ConfigurationError(f"hard_eng.pin.{name} must be a lowercase hex SHA-256")
    return ReleasePin(tag, value["archive_sha256"], value["manifest_sha256"])


def _marker_policy(value: object) -> MarkerPolicy:
    if not isinstance(value, dict):
        raise ConfigurationError("hard_eng in hard-eng.gates.json must be an object")
    allowed = {"channel", "minimum_version", "pin", "release_repository", "schema_version", "wiring"}
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
    wiring = value.get("wiring")
    if wiring is not None and wiring != "shared":
        raise ConfigurationError("hard_eng.wiring must be shared when present")
    if (wiring == "shared") != ("pin" in value):
        raise ConfigurationError("hard_eng.wiring = shared and hard_eng.pin must be set together")
    pin = _release_pin(value["pin"]) if "pin" in value else None
    return MarkerPolicy(channel, minimum, release_repository, wiring == "shared", pin)


def inspect_repository(start: Path) -> RepositoryState:
    root = find_repository(start)
    marker = root / "hard-eng.gates.json"
    if not marker.exists() and not marker.is_symlink():
        return RepositoryState(root, False, None, None)
    _regular_file(marker, "Hard Eng marker")
    if not _admitted(root, "hard-eng.gates.json"):
        raise ConfigurationError("hard-eng.gates.json must be tracked or privately ignored by Git")
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
    if not _admitted(root, "AGENTS.md"):
        raise ConfigurationError("repository AGENTS.md must be tracked or privately ignored by Git")
    policy = _marker_policy(value["hard_eng"]) if "hard_eng" in value else None
    return RepositoryState(root, True, "sha256:" + hashlib.sha256(raw).hexdigest(), policy)


def require_claude_owner(repository: Path) -> None:
    claude = repository / "CLAUDE.md"
    _regular_file(claude, "repository CLAUDE.md")
    if not _admitted(repository, "CLAUDE.md"):
        raise ConfigurationError("repository CLAUDE.md must be tracked or privately ignored by Git")
    if claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
        raise ConfigurationError("repository CLAUDE.md must contain only @AGENTS.md")


def agent_home(home: Path, agent: str) -> Path:
    configured = os.environ.get(AGENT_HOME_VARIABLES[agent])
    return Path(configured).expanduser() if configured else home / f".{agent}"


def claude_user_config(home: Path) -> Path:
    configured = os.environ.get("CLAUDE_CONFIG_DIR")
    return Path(configured).expanduser() / ".claude.json" if configured else home / ".claude.json"


def agent_installed(agent: str) -> bool:
    return shutil.which(agent) is not None


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


def _shared_problems(root: Path, launcher: Path) -> list[str]:
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
        *(root / "runtime/repository_native" / name for name in RUNTIME_FILES),
    )
    for path in required:
        if not path.is_file():
            problems.append(f"missing {path}")
    package = root / "runtime/repository_native/__init__.py"
    if package.is_file():
        try:
            module = ast.parse(package.read_text(encoding="utf-8"))
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
    return problems


def _agent_problems(home: Path, root: Path, agent: str) -> list[str]:
    hook = root / "scripts/hooks/agent-hook.sh"
    settings = agent_home(home, agent)
    problems: list[str] = []
    if agent == "codex":
        if not _same_file(settings / "AGENTS.md", root / "AGENTS.md"):
            problems.append("Codex global AGENTS.md is not wired to Hard Eng")
        if not _same_file(settings / "agents/he-learn.toml", root / "agents/he-learn/codex.toml"):
            problems.append("Codex global agent configuration is missing")
        if not _hook_points_to(settings / "hooks.json", hook):
            problems.append("Codex global guard hook is missing")
        if not _contains(settings / "config.toml", "codebase-memory"):
            problems.append("Codex global MCP wiring is missing")
    elif agent == "claude":
        memory = settings / "CLAUDE.md"
        if not _contains(memory, str(root / "AGENTS.md")) and not _contains(memory, "@~/.agents/AGENTS.md"):
            problems.append("Claude global rules are not wired to Hard Eng")
        if not _same_file(settings / "skills", root / "skills"):
            problems.append("Claude global skills are not wired to Hard Eng")
        if not _same_file(settings / "agents/he-learn.md", root / "agents/he-learn/claude.md"):
            problems.append("Claude global agent configuration is missing")
        if not _same_file(settings / "output-styles", root / "output-styles"):
            problems.append("Claude global output styles are not wired to Hard Eng")
        if not _hook_points_to(settings / "settings.json", hook):
            problems.append("Claude global guard hook is missing")
        if not _json_setting_matches(settings / "settings.json", "outputStyle", "Plain English"):
            problems.append("Claude global plain-English output style is missing")
        if not _contains(claude_user_config(home), "codebase-memory"):
            problems.append("Claude global MCP wiring is missing")
    elif agent == "copilot":
        if not _same_file(settings / "copilot-instructions.md", root / "AGENTS.md"):
            problems.append("Copilot global rules are not wired to Hard Eng")
        if not _same_file(settings / "agents/he-learn.agent.md", root / "agents/he-learn/copilot.agent.md"):
            problems.append("Copilot global agent configuration is missing")
        if not _hook_points_to(settings / "hooks/hard-eng.json", hook):
            problems.append("Copilot global guard hook is missing")
        if not _contains(settings / "mcp-config.json", "codebase-memory"):
            problems.append("Copilot global MCP wiring is missing")
        if not _contains(settings / "settings.json", "includeCoAuthoredBy"):
            problems.append("Copilot global settings are missing")
    return problems


def inspect_global(home: Path, agent: str) -> GlobalState:
    """Global health for one agent; agents whose command is absent only need the shared install."""
    root = home / ".agents"
    launcher = home / ".local/bin/hard-eng"
    hard_eng_paths = (
        root / ".hard-eng-release.json",
        root / "bin/hard-eng",
        root / "scripts/hooks/agent-hook.sh",
        launcher,
    )
    if not any(path.exists() or path.is_symlink() for path in hard_eng_paths):
        return GlobalState("absent", root, None, ())
    problems = _shared_problems(root, launcher)
    if agent_installed(agent):
        problems.extend(_agent_problems(home, root, agent))
    if problems:
        return GlobalState("broken", root, None, tuple(problems))
    return GlobalState("global", root, _global_identity(root), ())

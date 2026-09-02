"""One-command Hard Eng installation: global releases and repository setup."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from . import DEFAULT_RELEASE_REPOSITORY, SUPPORTED_AGENTS
from .errors import ConfigurationError, ReleaseUnavailable
from .locking import exclusive_lock
from .models import MarkerPolicy, PreparedState
from .prepare import prepare, remove_fallback
from .release import select_release, stage_release
from .repository import (
    AGENT_LABELS,
    OWNER_END,
    OWNER_START,
    agent_installed,
    find_repository,
    git,
    git_path,
    inspect_global,
)

INSTALL_LOCK_SECONDS = 600
OWNER_FILES = ("AGENTS.md", "CLAUDE.md", "hard-eng.gates.json")
MAX_OWNER_BYTES = 1024 * 1024
DEFAULT_AGENTS = b"""# Repository Rules

- Follow the repository's existing documentation and conventions.
- Use its existing build, test, lint, and formatting commands.
- Preserve its product behavior, security requirements, and data.
"""
DEFAULT_POLICY = {"schema_version": 1, "channel": "prerelease", "release_repository": DEFAULT_RELEASE_REPOSITORY}


def _write_all(descriptor: int, raw: bytes) -> None:
    remaining = memoryview(raw)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError("could not write the complete file")
        remaining = remaining[written:]


def _write_new(path: Path, raw: bytes, mode: int = 0o644) -> None:
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, mode)
    try:
        _write_all(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _replace(path: Path, raw: bytes, mode: int) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    _write_new(temporary, raw, mode)
    os.replace(temporary, path)


def _regular_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise ConfigurationError(f"{label} must be a regular file: {path}")
    if path.stat().st_size > MAX_OWNER_BYTES:
        raise ConfigurationError(f"{label} must be smaller than 1 MiB: {path}")


def _owner_block_lines(current: str) -> tuple[list[str], str]:
    lines = current.splitlines(keepends=True)
    starts = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == OWNER_START]
    ends = [index for index, line in enumerate(lines) if line.rstrip("\r\n") == OWNER_END]
    if (starts or ends) and (len(starts) != 1 or len(ends) != 1 or starts[0] >= ends[0]):
        raise ConfigurationError("Git private exclude has malformed Hard Eng owner markers")
    if starts:
        return lines, "".join(lines[: starts[0]]) + "".join(lines[ends[0] + 1 :])
    return lines, current


def _owner_exclude(current: str, private: bool) -> str:
    _, without_block = _owner_block_lines(current)
    if not private:
        return without_block
    prefix = without_block
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += "\n"
    if prefix and not prefix.endswith("\n\n"):
        prefix += "\n"
    block = "\n".join((OWNER_START, *(f"/{name}" for name in OWNER_FILES), OWNER_END)) + "\n"
    return prefix + block


class OwnerJournal:
    """Creates the repository-owned files and can put every change back."""

    def __init__(self, root: Path, *, private: bool) -> None:
        self.root = root
        self.private = private
        self.created: list[Path] = []
        self.replaced: dict[Path, tuple[bytes, int]] = {}
        self.exclude = git_path(root, "info/exclude")
        self.exclude_before: tuple[bytes, int] | None = None
        self.exclude_changed = False
        self.staged: list[str] = []
        self.hard_eng_existed = (root / ".agents/hard-eng").exists()
        self.agents_existed = (root / ".agents").exists()

    def _create(self, path: Path, raw: bytes) -> None:
        _write_new(path, raw)
        self.created.append(path)

    def apply(self) -> None:
        agents = self.root / "AGENTS.md"
        if agents.exists() or agents.is_symlink():
            _regular_file(agents, "AGENTS.md")
        else:
            self._create(agents, DEFAULT_AGENTS)
        claude = self.root / "CLAUDE.md"
        if claude.exists() or claude.is_symlink():
            _regular_file(claude, "CLAUDE.md")
            if claude.read_text(encoding="utf-8").strip() != "@AGENTS.md":
                raise ConfigurationError("CLAUDE.md must contain only @AGENTS.md")
        else:
            self._create(claude, b"@AGENTS.md\n")
        marker = self.root / "hard-eng.gates.json"
        if marker.exists() or marker.is_symlink():
            _regular_file(marker, "hard-eng.gates.json")
            raw = marker.read_bytes()
            try:
                value = json.loads(raw)
            except (UnicodeError, json.JSONDecodeError) as error:
                raise ConfigurationError(f"hard-eng.gates.json is invalid: {error}") from error
            if not isinstance(value, dict) or value.get("schema_version") != 1:
                raise ConfigurationError("hard-eng.gates.json must be a schema_version 1 object")
            if "hard_eng" not in value:
                mode = stat.S_IMODE(marker.stat().st_mode)
                self.replaced[marker] = (raw, mode)
                value["hard_eng"] = DEFAULT_POLICY
                _replace(marker, (json.dumps(value, indent=2) + "\n").encode(), mode)
            elif not isinstance(value["hard_eng"], dict):
                raise ConfigurationError("hard-eng.gates.json hard_eng must be an object")
        else:
            value = {"schema_version": 1, "hard_eng": DEFAULT_POLICY}
            self._create(marker, (json.dumps(value, indent=2) + "\n").encode())
        if self.exclude.exists() or self.exclude.is_symlink():
            _regular_file(self.exclude, "Git private exclude")
            current = self.exclude.read_bytes()
            mode = stat.S_IMODE(self.exclude.stat().st_mode)
            self.exclude_before = (current, mode)
        else:
            current = b""
            mode = 0o600
        updated = _owner_exclude(current.decode("utf-8"), self.private).encode()
        if updated != current:
            self.exclude.parent.mkdir(parents=True, exist_ok=True)
            _replace(self.exclude, updated, mode)
            self.exclude_changed = True

    def stage(self) -> None:
        for name in OWNER_FILES:
            tracked = git(self.root, "ls-files", "--error-unmatch", "--", name, check=False).returncode == 0
            if tracked:
                continue
            added = git(self.root, "add", "--", name, check=False)
            if added.returncode != 0:
                raise ConfigurationError(f"could not stage {name}; use --repo --ignore to keep it local")
            self.staged.append(name)

    def rollback(self) -> None:
        for name in self.staged:
            git(self.root, "rm", "--cached", "--quiet", "--", name, check=False)
        for path in reversed(self.created):
            if path.is_file() and not path.is_symlink():
                path.unlink()
        for path, (raw, mode) in self.replaced.items():
            _replace(path, raw, mode)
        if self.exclude_changed:
            if self.exclude_before is None:
                if self.exclude.is_file():
                    self.exclude.unlink()
            else:
                _replace(self.exclude, *self.exclude_before)
        if not self.hard_eng_existed:
            remove_fallback(self.root)
            shutil.rmtree(self.root / ".agents/hard-eng", ignore_errors=True)
        if not self.agents_existed:
            try:
                (self.root / ".agents").rmdir()
            except OSError:
                pass

    def summary(self) -> str:
        names = ", ".join(OWNER_FILES)
        if self.private:
            return f"Kept {names} private to this checkout."
        if self.staged:
            return f"Staged {', '.join(self.staged)}; commit them to share this setup."
        return f"{names} were already tracked."


def agent_lines(home: Path, prepared: dict[str, PreparedState] | None = None) -> list[str]:
    lines: list[str] = []
    for agent in SUPPORTED_AGENTS:
        label = AGENT_LABELS[agent]
        if not agent_installed(agent):
            lines.append(f"{label}: skipped (the {agent} command is not installed)")
            continue
        if prepared is not None:
            lines.append(f"{label}: ready ({prepared[agent].mode})")
            continue
        state = inspect_global(home, agent)
        if state.mode != "global":
            details = "\n  - ".join(state.problems) or state.mode
            raise ConfigurationError(f"{label} global wiring is incomplete:\n  - {details}")
        lines.append(f"{label}: ready")
    return lines


def _release_version(target: Path) -> str | None:
    identity = target / ".hard-eng-release.json"
    if identity.is_symlink() or not identity.is_file():
        return None
    try:
        value = json.loads(identity.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    version = value.get("version") if isinstance(value, dict) else None
    return version if isinstance(version, str) and version else None


def _global_kind(target: Path) -> str:
    if not target.exists() and not target.is_symlink():
        return "absent"
    if target.is_symlink() or not target.is_dir():
        raise ConfigurationError(f"{target} exists but is not a directory; move it aside, then rerun")
    if _release_version(target):
        return "release"
    if (target / ".git").exists() and (target / "setup.sh").is_file():
        return "checkout"
    raise ConfigurationError(f"{target} exists but is not a Hard Eng install; move it aside, then rerun")


def _run_setup(target: Path) -> None:
    setup = target / "setup.sh"
    if setup.is_symlink() or not setup.is_file() or not os.access(setup, os.X_OK):
        raise ConfigurationError(f"{setup} is missing or not executable")
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    print(f"hard-eng: running {setup} install", flush=True)
    result = subprocess.run([str(setup), "install"], check=False, env=environment)
    if result.returncode != 0:
        raise ConfigurationError(f"{setup} install failed with exit code {result.returncode}")


def _replace_global(stage: Path, target: Path) -> None:
    previous = target.with_name(f".agents.previous-{os.getpid()}")
    had_previous = target.exists()
    if had_previous:
        os.rename(target, previous)
    try:
        os.rename(stage, target)
    except OSError:
        if had_previous:
            os.rename(previous, target)
        raise
    try:
        _run_setup(target)
    except BaseException:
        shutil.rmtree(target, ignore_errors=True)
        if had_previous:
            os.rename(previous, target)
        raise
    if had_previous:
        shutil.rmtree(previous, ignore_errors=True)


def install_global(home: Path) -> int:
    if home.is_symlink() or not home.is_dir():
        raise ConfigurationError(f"HOME must be an existing directory: {home}")
    target = home / ".agents"
    asset_dir = home / ".local/share/hard-eng"
    asset_dir.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(asset_dir / "install.lock", timeout=INSTALL_LOCK_SECONDS, holder="another Hard Eng install"):
        kind = _global_kind(target)
        if kind == "checkout":
            _run_setup(target)
            action = "repaired the development checkout"
        else:
            policy = MarkerPolicy("prerelease", None, DEFAULT_RELEASE_REPOSITORY)
            installed = _release_version(target) if kind == "release" else None
            try:
                candidate = select_release(policy)
            except ReleaseUnavailable as error:
                if installed is None:
                    raise ConfigurationError(f"could not read the Hard Eng releases on GitHub: {error}") from error
                print(f"hard-eng: WARNING: update check failed ({error}); repairing {installed}", flush=True)
                candidate = None
            if candidate is None or candidate.tag == installed:
                _run_setup(target)
                action = f"repaired {installed}"
            else:
                stage = stage_release(candidate, policy.release_repository, home, agents=SUPPORTED_AGENTS)
                _replace_global(stage, target)
                action = (
                    f"installed {candidate.tag}" if installed is None else f"updated {installed} to {candidate.tag}"
                )
        lines = agent_lines(home)
    print(f"Hard Eng global setup: {action} at {target}")
    for line in lines:
        print(f"  {line}")
    return 0


def install_repository(start: Path, home: Path, *, private: bool) -> int:
    root = find_repository(start)
    if Path.cwd().resolve() != root:
        raise ConfigurationError(f"run this from the repository root: {root}")
    lock = git_path(root, "hard-eng-install.lock")
    with exclusive_lock(lock, timeout=INSTALL_LOCK_SECONDS, holder="another Hard Eng repository setup"):
        journal = OwnerJournal(root, private=private)
        journal.apply()
        try:
            if not private:
                journal.stage()
            agents = [agent for agent in SUPPORTED_AGENTS if agent_installed(agent)] or ["codex"]
            prepared = {agent: prepare(root, home, agent) for agent in agents}
            modes = {state.mode for state in prepared.values()}
            if len(modes) != 1 or not modes <= {"global", "fallback"}:
                raise ConfigurationError("Hard Eng did not prepare this repository the same way for every agent")
        except BaseException:
            journal.rollback()
            raise
    state = next(iter(prepared.values()))
    identity = state.version or state.hard_eng_root
    print(f"Hard Eng repository setup: {state.mode} ({identity}) in {root}")
    for line in agent_lines(home, {agent: state for agent in SUPPORTED_AGENTS}):
        print(f"  {line}")
    print(journal.summary())
    return 0

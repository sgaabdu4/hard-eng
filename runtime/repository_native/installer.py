"""One-command Hard Eng installation: a global clone of main and repository setup."""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

from . import SUPPORTED_AGENTS
from .adapters import shared_files
from .errors import ConfigurationError
from .jsonstyle import render, style_for
from .locking import exclusive_lock
from .models import PreparedState
from .prepare import remove_copy, share
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
from .source import COMMIT_ID, SOURCE_BRANCH, source_url

INSTALL_LOCK_SECONDS = 600
GIT_TIMEOUT_SECONDS = 600
OWNER_FILES = ("AGENTS.md", "CLAUDE.md", "hard-eng.gates.json")
MAX_OWNER_BYTES = 1024 * 1024
DEFAULT_AGENTS = b"""# Repository Rules

- Follow the repository's existing documentation and conventions.
- Use its existing build, test, lint, and formatting commands.
- Preserve its product behavior, security requirements, and data.
"""
SHARED_POLICY = {"schema_version": 1, "wiring": "shared"}


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


def _owner_exclude(current: str) -> str:
    _, without_block = _owner_block_lines(current)
    return without_block


class OwnerJournal:
    """Creates the repository-owned files and can put every change back."""

    def __init__(self, root: Path) -> None:
        self.root = root
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
            if value.get("hard_eng") != SHARED_POLICY:
                mode = stat.S_IMODE(marker.stat().st_mode)
                self.replaced[marker] = (raw, mode)
                value["hard_eng"] = dict(SHARED_POLICY)
                _replace(marker, render(value, style_for(marker)).encode(), mode)
        else:
            value = {"schema_version": 1, "hard_eng": dict(SHARED_POLICY)}
            self._create(marker, render(value, style_for(marker)).encode())
        if self.exclude.exists() or self.exclude.is_symlink():
            _regular_file(self.exclude, "Git private exclude")
            current = self.exclude.read_bytes()
            mode = stat.S_IMODE(self.exclude.stat().st_mode)
            self.exclude_before = (current, mode)
        else:
            current = b""
            mode = 0o600
        updated = _owner_exclude(current.decode("utf-8")).encode()
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
                raise ConfigurationError(f"could not stage {name}: {added.stderr.strip()}")
            self.staged.append(name)

    def stage_shared(self) -> list[str]:
        names = ["hard-eng.gates.json"] + [
            path.relative_to(self.root).as_posix() for path in shared_files(self.root) if path.is_file()
        ]
        added = git(self.root, "add", "--force", "--", *names, check=False)
        if added.returncode != 0:
            raise ConfigurationError(f"could not stage the shared Hard Eng files: {added.stderr.strip()}")
        return names

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
            remove_copy(self.root)
            shutil.rmtree(self.root / ".agents/hard-eng", ignore_errors=True)
        if not self.agents_existed:
            try:
                (self.root / ".agents").rmdir()
            except OSError:
                pass

    def summary(self) -> str:
        names = ", ".join(OWNER_FILES)
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


def _global_kind(target: Path) -> str:
    if not target.exists() and not target.is_symlink():
        return "absent"
    if target.is_symlink() or not target.is_dir():
        raise ConfigurationError(f"{target} exists but is not a directory; move it aside, then rerun")
    if (target / ".git").exists() and (target / "setup.sh").is_file():
        return "checkout"
    if (target / ".hard-eng-release.json").is_file():
        return "release"
    raise ConfigurationError(f"{target} exists but is not a Hard Eng install; move it aside, then rerun")


def _git(cwd: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
        stdin=subprocess.DEVNULL,
        timeout=GIT_TIMEOUT_SECONDS,
    )


def _failure(result: subprocess.CompletedProcess[str], fallback: str) -> str:
    lines = result.stderr.strip().splitlines()
    return lines[-1] if lines else fallback


def _head(target: Path) -> str:
    head = _git(target, "rev-parse", "HEAD").stdout.strip()
    return head[:12] if COMMIT_ID.fullmatch(head) else "unknown"


def _run_setup(target: Path) -> None:
    setup = target / "setup.sh"
    if setup.is_symlink() or not setup.is_file() or not os.access(setup, os.X_OK):
        raise ConfigurationError(f"{setup} is missing or not executable")
    environment = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    print(f"hard-eng: running {setup} install", flush=True)
    result = subprocess.run([str(setup), "install"], check=False, env=environment)
    if result.returncode != 0:
        raise ConfigurationError(f"{setup} install failed with exit code {result.returncode}")


def _clone_global(home: Path) -> Path:
    stage = home / f".hard-eng-install-{os.getpid()}"
    shutil.rmtree(stage, ignore_errors=True)
    url = source_url()
    result = _git(
        home, "clone", "--quiet", "--depth", "1", "--branch", SOURCE_BRANCH, "--single-branch", url, str(stage)
    )
    if result.returncode != 0:
        shutil.rmtree(stage, ignore_errors=True)
        raise ConfigurationError(f"could not clone {url}: {_failure(result, 'git clone failed')}")
    return stage


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


def _update_checkout(target: Path) -> str:
    before = _head(target)
    branch = _git(target, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch != SOURCE_BRANCH or _git(target, "status", "--porcelain", "--untracked-files=no").stdout != "":
        _run_setup(target)
        return "repaired the development checkout"
    pulled = _git(target, "pull", "--ff-only", "--quiet", source_url(), SOURCE_BRANCH)
    if pulled.returncode != 0:
        print(
            f"hard-eng: WARNING: update failed ({_failure(pulled, 'git pull failed')}); repairing {before}", flush=True
        )
        _run_setup(target)
        return f"repaired {before}"
    after = _head(target)
    _run_setup(target)
    return f"repaired {before}" if after == before else f"updated {before} to {after}"


def install_global(home: Path) -> int:
    if home.is_symlink() or not home.is_dir():
        raise ConfigurationError(f"HOME must be an existing directory: {home}")
    target = home / ".agents"
    asset_dir = home / ".local/share/hard-eng"
    asset_dir.mkdir(parents=True, exist_ok=True)
    with exclusive_lock(asset_dir / "install.lock", timeout=INSTALL_LOCK_SECONDS, holder="another Hard Eng install"):
        kind = _global_kind(target)
        if kind == "checkout":
            action = _update_checkout(target)
        else:
            stage = _clone_global(home)
            try:
                _replace_global(stage, target)
            finally:
                shutil.rmtree(stage, ignore_errors=True)
            commit = _head(target)
            action = f"installed {commit}" if kind == "absent" else f"replaced the old release install with {commit}"
        lines = agent_lines(home)
    print(f"Hard Eng global setup: {action} at {target}")
    for line in lines:
        print(f"  {line}")
    return 0


def install_repository(start: Path, home: Path) -> int:
    root = find_repository(start)
    if Path.cwd().resolve() != root:
        raise ConfigurationError(f"run this from the repository root: {root}")
    lock = git_path(root, "hard-eng-install.lock")
    with exclusive_lock(lock, timeout=INSTALL_LOCK_SECONDS, holder="another Hard Eng repository setup"):
        journal = OwnerJournal(root)
        journal.apply()
        try:
            journal.stage()
            agents = [agent for agent in SUPPORTED_AGENTS if agent_installed(agent)] or ["codex"]
            prepared = {agent: share(root, home, agent) for agent in agents}
            if {state.mode for state in prepared.values()} != {"shared"}:
                raise ConfigurationError("Hard Eng did not prepare this repository the same way for every agent")
        except BaseException:
            journal.rollback()
            raise
        staged = journal.stage_shared()
    state = next(iter(prepared.values()))
    print(f"Hard Eng repository setup: {state.mode} ({state.identity}) in {root}")
    for line in agent_lines(home, {agent: state for agent in SUPPORTED_AGENTS}):
        print(f"  {line}")
    print(f"Staged {', '.join(staged)}; commit them so every clone fetches the newest Hard Eng.")
    return 0

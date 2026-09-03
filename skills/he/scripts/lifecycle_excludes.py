#!/usr/bin/env python3
"""Keep terminal Hard Eng lifecycle state out of repository status noise."""

from __future__ import annotations

import fcntl
import os
import re
import stat
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GIT_ENV_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from bounded_run import run_captured
from git_env import git_env

REPOSITORY_ROOT = SCRIPT_DIR.parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file


class LifecycleExcludeError(OSError):
    """Terminal lifecycle state could not be registered safely."""


TERMINAL_STATUSES = {"shipped", "cancelled"}
LEGACY_MARKER = b"# Hard Eng terminal lifecycle state (shared by linked worktrees)"
BEGIN = b"# >>> Hard Eng terminal lifecycle state >>>"
END = b"# <<< Hard Eng terminal lifecycle state <<<"
OWNED_PATTERN = re.compile(rb"/features/[a-z0-9]+(?:-[a-z0-9]+)*/(?:PLAN\.md|BUILD\.md|receipts/|tickets/)")


def _git_path(repo: Path, *arguments: str) -> Path:
    try:
        result = run_captured(["git", "-C", str(repo), "rev-parse", *arguments], timeout=10, grace=1, env=git_env())
    except OSError as error:
        raise LifecycleExcludeError(f"cannot resolve {' '.join(arguments)}") from error
    stdout = result.stdout.decode("utf-8", "replace").strip()
    stderr = result.stderr.decode("utf-8", "replace").strip()
    if result.returncode != 0 or not stdout:
        raise LifecycleExcludeError(f"cannot resolve {' '.join(arguments)}: {stderr[:500]}")
    path = Path(stdout)
    return (path if path.is_absolute() else repo / path).absolute()


def _split_owned(existing: bytes) -> tuple[list[bytes], set[bytes]]:
    rows = existing.splitlines()
    if rows.count(BEGIN) != rows.count(END) or rows.count(BEGIN) > 1:
        raise LifecycleExcludeError("Git exclude has a malformed Hard Eng owned block")
    if BEGIN in rows:
        start = rows.index(BEGIN)
        finish = rows.index(END)
        if finish <= start:
            raise LifecycleExcludeError("Git exclude has a malformed Hard Eng owned block")
        owned = rows[start + 1 : finish]
        if any(not OWNED_PATTERN.fullmatch(row) for row in owned):
            raise LifecycleExcludeError("Git exclude Hard Eng block contains an invalid row")
        return rows[:start] + rows[finish + 1 :], set(owned)
    if LEGACY_MARKER in rows:
        base = [row for row in rows if row != LEGACY_MARKER and not OWNED_PATTERN.fullmatch(row)]
        owned = {row for row in rows if OWNED_PATTERN.fullmatch(row)}
        return base, owned
    return rows, set()


def _render_owned(base: list[bytes], owned: set[bytes]) -> bytes:
    while base and base[-1] == b"":
        base.pop()
    rows = list(base)
    if owned:
        if rows:
            rows.append(b"")
        rows.extend((BEGIN, *sorted(owned), END))
    return b"\n".join(rows) + (b"\n" if rows else b"")


def _update_owned(exclude: Path, patterns: tuple[bytes, ...], *, add: bool) -> None:
    lock = exclude.with_name("hard-eng-lifecycle-excludes.lock")
    try:
        with safe_file.parent_fd(lock.parent, Path(lock.name), create=True) as (directory, name):
            descriptor = os.open(
                name,
                os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory,
            )
            os.fsync(directory)
    except OSError as error:
        raise LifecycleExcludeError(f"unsafe Git exclude lock: {lock}: {error}") from error
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        metadata = os.fstat(descriptor)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) & 0o077
        ):
            raise LifecycleExcludeError("Git exclude lock is not a private current-user file")
        try:
            existing, mode = safe_file.read_snapshot(exclude.parent, Path(exclude.name))
            existed = True
        except FileNotFoundError:
            existing, mode, existed = b"", 0o644, False
        if len(existing) > 1024 * 1024:
            raise LifecycleExcludeError("Git exclude exceeds the 1 MiB safety bound")
        base, owned = _split_owned(existing)
        owned.update(patterns) if add else owned.difference_update(patterns)
        replacement = _render_owned(base, owned)
        if replacement != existing:
            if existed:
                safe_file.replace_path_if_unchanged(exclude, existing, mode, replacement)
            else:
                safe_file.create_path(exclude, replacement, mode)
    except LifecycleExcludeError:
        raise
    except OSError as error:
        raise LifecycleExcludeError(f"Git exclude owned-block update failed safely: {error}") from error
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(descriptor)


def _exclude_target(repo: Path, plan: Path) -> tuple[Path, str]:
    repo = repo.resolve()
    plan = plan.resolve()
    if _git_path(repo, "--show-toplevel") != repo:
        raise LifecycleExcludeError("repository path must be the Git worktree root")
    try:
        relative = plan.relative_to(repo)
    except ValueError as error:
        raise LifecycleExcludeError("PLAN must be inside the repository") from error
    if len(relative.parts) != 3 or relative.parts[0] != "features" or relative.parts[2] != "PLAN.md":
        raise LifecycleExcludeError("PLAN path must be features/<feature-slug>/PLAN.md")
    slug = relative.parts[1]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise LifecycleExcludeError("feature slug must be lowercase kebab-case")
    common_dir = _git_path(repo, "--git-common-dir")
    exclude = _git_path(repo, "--git-path", "info/exclude")
    if exclude != (common_dir / "info" / "exclude").absolute():
        raise LifecycleExcludeError("Git exclude is not owned by the common directory")
    return exclude, slug


def _owned_patterns(slug: str) -> tuple[bytes, ...]:
    return tuple(f"/features/{slug}/{name}".encode() for name in ("PLAN.md", "BUILD.md", "receipts/", "tickets/"))


def exclude_terminal_artifacts(repo: Path, plan: Path, lifecycle_status: str) -> Path:
    """Register exact terminal PLAN/receipt paths in the shared local exclude."""
    if lifecycle_status not in TERMINAL_STATUSES:
        raise LifecycleExcludeError("only terminal lifecycle state can be excluded")
    exclude, slug = _exclude_target(repo, plan)
    patterns = _owned_patterns(slug)
    _update_owned(exclude, patterns, add=True)
    return exclude


def activate_lifecycle_artifacts(repo: Path, plan: Path) -> Path:
    exclude, slug = _exclude_target(repo, plan)
    patterns = _owned_patterns(slug)
    _update_owned(exclude, patterns, add=False)
    return exclude

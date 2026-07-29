#!/usr/bin/env python3
"""Keep terminal Hard Eng lifecycle state out of repository status noise."""

from __future__ import annotations

import fcntl
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
GIT_ENV_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env


class LifecycleExcludeError(OSError):
    """Terminal lifecycle state could not be registered safely."""


TERMINAL_STATUSES = {"shipped", "cancelled"}
MARKER = "# Hard Eng terminal lifecycle state (shared by linked worktrees)"


def _git_path(repo: Path, *arguments: str) -> Path:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            env=git_env(),
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise LifecycleExcludeError(
            f"cannot resolve {' '.join(arguments)}"
        ) from error
    if result.returncode != 0 or not result.stdout.strip():
        raise LifecycleExcludeError(
            f"cannot resolve {' '.join(arguments)}: {result.stderr.strip()[:500]}"
        )
    path = Path(result.stdout.strip())
    return (path if path.is_absolute() else repo / path).resolve()


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise LifecycleExcludeError("zero-byte Git exclude write")
        view = view[written:]


def _read_all(descriptor: int, size: int) -> bytes:
    chunks = []
    remaining = size
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            raise LifecycleExcludeError("short Git exclude read")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def exclude_terminal_artifacts(
    repo: Path, plan: Path, lifecycle_status: str
) -> Path:
    """Register exact terminal PLAN/receipt paths in the shared local exclude."""
    if lifecycle_status not in TERMINAL_STATUSES:
        raise LifecycleExcludeError("only terminal lifecycle state can be excluded")
    repo = repo.resolve()
    plan = plan.resolve()
    if _git_path(repo, "--show-toplevel") != repo:
        raise LifecycleExcludeError("repository path must be the Git worktree root")
    try:
        relative = plan.relative_to(repo)
    except ValueError as error:
        raise LifecycleExcludeError("PLAN must be inside the repository") from error
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "features"
        or relative.parts[2] != "PLAN.md"
    ):
        raise LifecycleExcludeError(
            "PLAN path must be features/<feature-slug>/PLAN.md"
        )
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", relative.parts[1]):
        raise LifecycleExcludeError("feature slug must be lowercase kebab-case")

    common_dir = _git_path(repo, "--git-common-dir")
    exclude = _git_path(repo, "--git-path", "info/exclude")
    if exclude != (common_dir / "info" / "exclude").resolve():
        raise LifecycleExcludeError("Git exclude is not owned by the common directory")
    exclude.parent.mkdir(parents=True, exist_ok=True)

    slug = relative.parts[1]
    patterns = (
        f"/features/{slug}/PLAN.md".encode(),
        f"/features/{slug}/receipts/".encode(),
    )
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(exclude, flags, 0o644)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode):
            raise LifecycleExcludeError("Git exclude must be a regular file")
        if metadata.st_size > 1024 * 1024:
            raise LifecycleExcludeError("Git exclude exceeds the 1 MiB safety bound")
        existing = _read_all(descriptor, metadata.st_size)
        rows = set(existing.splitlines())
        missing = [pattern for pattern in patterns if pattern not in rows]
        if missing:
            addition = []
            marker = MARKER.encode()
            if marker not in rows:
                addition.append(marker)
            addition.extend(missing)
            prefix = b"" if not existing or existing.endswith(b"\n") else b"\n"
            payload = prefix + b"\n".join(addition) + b"\n"
            os.lseek(descriptor, 0, os.SEEK_END)
            _write_all(descriptor, payload)
            os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return exclude

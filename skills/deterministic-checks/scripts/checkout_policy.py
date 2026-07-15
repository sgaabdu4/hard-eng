#!/usr/bin/env python3
"""Read the canonical repository checkout policy without following override symlinks."""

from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=False, capture_output=True, text=True
    )


def git_path(root: Path, name: str) -> Path:
    result = git(root, "rev-parse", name)
    if result.returncode:
        raise OSError(f"cannot resolve {name}")
    value = Path(result.stdout.strip())
    return (value if value.is_absolute() else root / value).resolve()


def primary_checkout(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"],
        check=False,
        capture_output=True,
    )
    if result.returncode:
        raise OSError("cannot resolve primary checkout")
    for record in result.stdout.split(b"\0"):
        if record.startswith(b"worktree "):
            return Path(record.removeprefix(b"worktree ").decode("utf-8", "strict")).resolve()
    raise OSError("primary checkout is missing")


def checkout_policy(root: Path) -> str:
    owner = primary_checkout(root)
    path = owner / "AGENTS.override.md"
    if git(owner, "ls-files", "--error-unmatch", "--", path.name).returncode:
        return "selectable"
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(descriptor, encoding="utf-8") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError("tracked AGENTS.override.md must be a regular no-follow file")
        text = handle.read(65537)
    if len(text) > 65536:
        raise OSError("tracked AGENTS.override.md exceeds 65536 bytes")
    policies = []
    for line in text.splitlines():
        directive = line.strip()
        if not directive or directive.startswith("#") or "checkout_policy" not in directive:
            continue
        match = re.fullmatch(r"- checkout_policy = (primary-only|selectable)", directive)
        if match is None:
            raise OSError("malformed checkout_policy directive")
        policies.append(match.group(1))
    if len(policies) > 1:
        raise OSError("duplicate checkout_policy directive")
    return policies[0] if policies else "selectable"


def linked_checkout(root: Path) -> bool:
    return git_path(root, "--git-dir") != git_path(root, "--git-common-dir")

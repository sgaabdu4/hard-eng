#!/usr/bin/env python3
"""Canonical owner of Git subprocess environment sanitation.

git-env-hygiene: exempt - this module reads the live variable list before a
sanitized environment exists.

Git exports its per-invocation repository variables to hooks. A hook-launched
subprocess that inherits them resolves `-C`, discovery, pathspecs, and the index
against the hook's repository instead of the requested checkout, so cross-repo
and worktree work silently targets the wrong tree.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from bounded_run import run_captured

from scripts.setup import safe_file

# Baseline mirror of `git rev-parse --local-env-vars` plus the hook-only
# variables Git omits from that list. The live list is unioned in at runtime.
LOCAL_ENV_VARS = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_CONFIG",
    "GIT_CONFIG_COUNT",
    "GIT_CONFIG_PARAMETERS",
    "GIT_DIR",
    "GIT_GRAFT_FILE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_INDEX_VERSION",
    "GIT_NAMESPACE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_OBJECT_DIRECTORY",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_REPLACE_REF_BASE",
    "GIT_SHALLOW_FILE",
    "GIT_WORK_TREE",
)

_STRIPPED: frozenset[str] | None = None

# The in-process memo below only helps a long-lived process. The agent guard is a
# fresh interpreter on every tool call in every runtime, so it paid for this fork
# every time. The list is a property of the git binary, so it is cached on disk
# against that binary's identity and re-read for free; a different or upgraded git
# misses the cache and forks again, which is what keeps the list honest across
# version drift. The static list stays the floor, so a cache miss is never a hole.
_CACHE = Path(
    os.environ.get("HARD_ENG_GIT_ENV_CACHE") or Path.home() / ".cache" / "hard-eng" / "git-env" / "local-env-vars.json"
)


def _git_fingerprint() -> str | None:
    """Which git this PATH resolves, and which build of it."""
    for directory in os.environ.get("PATH", "").split(os.pathsep):
        if not directory:
            continue
        candidate = os.path.join(directory, "git")
        if not (os.path.isfile(candidate) and os.access(candidate, os.X_OK)):
            continue
        try:
            stat = os.stat(candidate)
        except OSError:
            return None
        return f"{candidate}:{stat.st_mtime_ns}:{stat.st_size}"
    return None


def _cached(fingerprint: str | None) -> frozenset[str] | None:
    if fingerprint is None:
        return None
    try:
        content, mode = safe_file.read_snapshot(_CACHE)
        if mode != 0o600:
            return None
        record = json.loads(content)
    except (OSError, ValueError):
        return None
    if not isinstance(record, dict) or record.get("fingerprint") != fingerprint:
        return None
    names = record.get("variables")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        return None
    return frozenset(names)


def _remember(fingerprint: str | None, names: list[str]) -> None:
    if fingerprint is None or not names:
        return
    content = (json.dumps({"fingerprint": fingerprint, "variables": sorted(names)}) + "\n").encode()
    try:
        before, mode = safe_file.read_snapshot(_CACHE)
    except FileNotFoundError:
        try:
            safe_file.create_path(_CACHE, content, 0o600)
        except OSError:
            return
    except OSError:
        return
    else:
        try:
            safe_file.replace_path_if_unchanged(_CACHE, before, mode, content)
        except OSError:
            return


def stripped_variables() -> frozenset[str]:
    """Variable names removed from every sanitized environment."""
    global _STRIPPED
    if _STRIPPED is not None:
        return _STRIPPED
    fingerprint = _git_fingerprint()
    remembered = _cached(fingerprint)
    if remembered is not None:
        _STRIPPED = frozenset(LOCAL_ENV_VARS) | remembered
        return _STRIPPED
    reported: list[str] = []
    try:
        captured = run_captured(["git", "rev-parse", "--local-env-vars"], timeout=10, grace=1)
    except OSError:
        captured = None
    if captured is not None and captured.returncode == 0:
        reported = captured.stdout.decode("utf-8", "replace").split()
        # Only a clean answer is worth remembering: caching a failed or empty run
        # would blind every later process until the git binary changed.
        _remember(fingerprint, reported)
    _STRIPPED = frozenset(LOCAL_ENV_VARS) | frozenset(reported)
    return _STRIPPED


def git_env(base: dict[str, str] | None = None, *, ceiling: str | os.PathLike[str] | None = None) -> dict[str, str]:
    """Environment with Git's inherited per-invocation variables removed.

    `ceiling` sets GIT_CEILING_DIRECTORIES so fixture repositories cannot
    discover an enclosing checkout.
    """
    stripped = stripped_variables()
    source = os.environ if base is None else base
    env = {key: value for key, value in source.items() if key not in stripped}
    if ceiling is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(Path(ceiling))
    return env


def scrub_environ(*, ceiling: str | os.PathLike[str] | None = None) -> None:
    """Sanitize this process's own environment, covering every child it spawns.

    Entry points and fixture harnesses only: importable production modules must
    pass `git_env()` per call instead of mutating a caller's environment.
    """
    for name in stripped_variables():
        os.environ.pop(name, None)
    if ceiling is not None:
        os.environ["GIT_CEILING_DIRECTORIES"] = str(Path(ceiling))

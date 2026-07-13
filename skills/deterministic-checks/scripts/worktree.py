#!/usr/bin/env python3
"""Validate Git checkout readiness, branch state, and copied local inputs."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


INTENTS = ("read", "write", "publish")
BROAD_INCLUDE_PATTERNS = {"*", "**", "/*", "/**", "**/*", "/**/*"}
GLOB_MARKERS = frozenset("*?[")


def emit(key: str, value: object) -> None:
    print(f"{key}={str(value).replace(chr(10), ' ').replace(chr(13), ' ')}")


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=check,
        capture_output=True,
        text=True,
    )


def git_root(repo: str) -> Path:
    candidate = Path(repo).expanduser().resolve()
    return Path(git(candidate, "rev-parse", "--show-toplevel").stdout.strip()).resolve()


def git_path(root: Path, name: str) -> Path:
    value = Path(git(root, "rev-parse", name).stdout.strip())
    return (value if value.is_absolute() else root / value).resolve()


def branch(root: Path) -> str:
    result = git(root, "symbolic-ref", "--quiet", "--short", "HEAD", check=False)
    return result.stdout.strip() if result.returncode == 0 else "DETACHED"


def include_entries(root: Path) -> tuple[str, ...]:
    path = root / ".worktreeinclude"
    if not path.is_file():
        return ()
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def literal_entry(entry: str) -> bool:
    return not entry.startswith("!") and not any(marker in entry for marker in GLOB_MARKERS)


def inspect(repo: str, intent: str) -> int:
    try:
        root = git_root(repo)
        git_dir = git_path(root, "--git-dir")
        common_dir = git_path(root, "--git-common-dir")
        current_branch = branch(root)
        head = git(root, "rev-parse", "HEAD").stdout.strip()
        dirty = tuple(line for line in git(root, "status", "--short").stdout.splitlines() if line)
        entries = include_entries(root)
    except (FileNotFoundError, OSError, UnicodeError, subprocess.CalledProcessError) as exc:
        emit("result", "invalid")
        emit("error_1", f"repository preflight failed: {exc}")
        return 4

    isolated = git_dir != common_dir
    errors: list[str] = []
    broad = tuple(entry for entry in entries if entry in BROAD_INCLUDE_PATTERNS)
    if broad:
        errors.append("broad .worktreeinclude pattern forbidden: " + ",".join(broad))
    include_path = root / ".worktreeinclude"
    if include_path.exists() and git(
        root, "ls-files", "--error-unmatch", "--", ".worktreeinclude", check=False
    ).returncode != 0:
        errors.append(".worktreeinclude must be tracked in the selected starting state")

    missing = tuple(
        entry
        for entry in entries
        if literal_entry(entry) and not (root / entry.lstrip("/")).exists()
    )
    tracked = tuple(
        entry
        for entry in entries
        if literal_entry(entry)
        and git(root, "ls-files", "--error-unmatch", "--", entry.lstrip("/"), check=False).returncode == 0
    )
    if intent == "write" and not isolated and dirty:
        errors.append("dirty primary checkout requires an isolated Git worktree")
    if missing:
        errors.append("required .worktreeinclude paths missing: " + ",".join(missing))
    if tracked:
        errors.append("tracked paths forbidden in .worktreeinclude: " + ",".join(tracked))
    if intent == "publish" and current_branch == "DETACHED":
        errors.append("commit/push requires a dedicated named branch")

    emit("result", "invalid" if errors else "valid")
    emit("repository_root", root)
    emit("worktree", "isolated" if isolated else "primary")
    emit("branch", current_branch)
    emit("head_sha", head)
    emit("dirty_count", len(dirty))
    emit("starting_state", "dirty" if dirty else "clean")
    emit("worktreeinclude", "present" if entries else "absent")
    emit("included_path_count", len(entries))
    emit("codex_session", "yes" if os.environ.get("CODEX_THREAD_ID") else "no")
    for index, error in enumerate(errors, start=1):
        emit(f"error_{index}", error)
    return 4 if errors else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--intent", choices=INTENTS, default="read")
    args = parser.parse_args()
    return inspect(args.repo, args.intent)


if __name__ == "__main__":
    sys.exit(main())

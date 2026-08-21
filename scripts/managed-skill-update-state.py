#!/usr/bin/env python3
"""Protect existing Feature Brief files while managed skills are updated."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
DETERMINISTIC_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

from bounded_run import TIMEOUT_EXIT, run_captured
from git_env import git_env


class UpdateStateError(RuntimeError):
    pass


SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
RECEIPT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\.json\Z")
TICKET = re.compile(r"T-(?:[1-9][0-9]*|int)\.md\Z")


def fail(message: str) -> NoReturn:
    raise UpdateStateError(message)


def git_bytes(repo: Path, args: list[str]) -> bytes:
    result = run_captured(["git", "-C", str(repo), *args], timeout=20, grace=1, env=git_env(ceiling=repo.parent))
    if result.returncode == TIMEOUT_EXIT:
        fail("Git inspection timed out")
    if result.returncode:
        fail("Git inspection failed")
    return result.stdout


def split_paths(payload: bytes) -> list[str]:
    paths = [os.fsdecode(item) for item in payload.split(b"\0") if item]
    if len(paths) != len(set(paths)):
        fail("Git returned a duplicate path")
    return paths


def changed_paths(repo: Path, *, cached: bool) -> list[str]:
    args = ["diff", "--name-only", "-z"]
    if cached:
        args.insert(1, "--cached")
    return split_paths(git_bytes(repo, args))


def untracked_paths(repo: Path) -> list[str]:
    return split_paths(git_bytes(repo, ["ls-files", "-z", "--others", "--exclude-standard"]))


def ignored_feature_paths(repo: Path) -> list[str]:
    return split_paths(
        git_bytes(repo, ["ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--", "features"])
    )


def lifecycle_parts(relative: str) -> tuple[str, ...] | None:
    parts = PurePosixPath(relative).parts
    if len(parts) == 3 and parts[0] == "features" and SLUG.fullmatch(parts[1]) and parts[2] == "PLAN.md":
        return parts
    if (
        len(parts) == 4
        and parts[0] == "features"
        and SLUG.fullmatch(parts[1])
        and parts[2] == "receipts"
        and RECEIPT.fullmatch(parts[3])
    ):
        return parts
    if (
        len(parts) == 4
        and parts[0] == "features"
        and SLUG.fullmatch(parts[1])
        and parts[2] == "tickets"
        and TICKET.fullmatch(parts[3])
    ):
        return parts
    return None


def lock_keys(repo: Path) -> frozenset[str]:
    flags = os.O_RDONLY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(repo / ".skill-lock.json", flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
                fail("managed-skill lock owner or type is unsafe")
            if metadata.st_size > 1024 * 1024:
                fail("managed-skill lock is too large")
            payload = bytearray()
            while len(payload) <= 1024 * 1024:
                chunk = os.read(descriptor, 64 * 1024)
                if not chunk:
                    break
                payload.extend(chunk)
            if len(payload) > 1024 * 1024:
                fail("managed-skill lock is too large")
        finally:
            os.close(descriptor)
        value = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError) as error:
        raise UpdateStateError("cannot read the managed-skill lock") from error
    skills = value.get("skills") if isinstance(value, dict) else None
    if not isinstance(skills, dict):
        fail("managed-skill lock has an invalid shape")
    keys = frozenset(skills)
    if not keys or any(not SLUG.fullmatch(key) for key in keys):
        fail("managed-skill lock has an invalid key")
    return keys


def managed_path(relative: str, keys: frozenset[str]) -> bool:
    parts = PurePosixPath(relative).parts
    return relative == ".skill-lock.json" or (len(parts) >= 2 and parts[0] == "skills" and parts[1] in keys)


def descriptor_metadata(descriptor: int) -> tuple[int, int, int, int]:
    metadata = os.fstat(descriptor)
    return (metadata.st_mode, metadata.st_uid, metadata.st_gid, metadata.st_size)


def open_directory(parent: int, name: str) -> int:
    flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(name, flags, dir_fd=parent)
    metadata = os.fstat(descriptor)
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        os.close(descriptor)
        fail("Feature Brief directory owner or type is unsafe")
    return descriptor


def open_feature_file(
    repo_descriptor: int, parts: tuple[str, ...]
) -> tuple[int, list[tuple[str, tuple[int, int, int, int]]]]:
    current = os.dup(repo_descriptor)
    directories: list[tuple[str, tuple[int, int, int, int]]] = []
    walked: list[str] = []
    try:
        for component in parts[:-1]:
            child = open_directory(current, component)
            os.close(current)
            current = child
            walked.append(component)
            directories.append(("/".join(walked), descriptor_metadata(current)))
        flags = os.O_RDONLY
        if hasattr(os, "O_CLOEXEC"):
            flags |= os.O_CLOEXEC
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(parts[-1], flags, dir_fd=current)
    finally:
        os.close(current)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
        os.close(descriptor)
        fail("Feature Brief file owner or type is unsafe")
    return descriptor, directories


def file_digest(descriptor: int) -> str:
    digest = hashlib.sha256()
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def lifecycle_snapshot(repo: Path, *, before: bool) -> str:
    tracked = changed_paths(repo, cached=False)
    staged = changed_paths(repo, cached=True)
    if before and (tracked or staged):
        fail("starting tracked or staged changes are not allowed")
    paths = sorted(set(untracked_paths(repo)) | set(ignored_feature_paths(repo)))
    lifecycle: list[tuple[str, tuple[str, ...]]] = []
    for relative in paths:
        parts = lifecycle_parts(relative)
        if parts is not None:
            lifecycle.append((relative, parts))
        elif before:
            fail(f"starting untracked path is not lifecycle state: {relative}")

    root_flags = os.O_RDONLY | os.O_DIRECTORY
    if hasattr(os, "O_CLOEXEC"):
        root_flags |= os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        root_flags |= os.O_NOFOLLOW
    root_descriptor = os.open(repo, root_flags)
    records: list[tuple[object, ...]] = []
    directory_records: dict[str, tuple[int, int, int, int]] = {}
    try:
        for relative, parts in sorted(lifecycle):
            descriptor, directories = open_feature_file(root_descriptor, parts)
            try:
                metadata = descriptor_metadata(descriptor)
                content = file_digest(descriptor)
            finally:
                os.close(descriptor)
            for path, directory_metadata in directories:
                previous = directory_records.setdefault(path, directory_metadata)
                if previous != directory_metadata:
                    fail("Feature Brief directory changed during snapshot")
            records.append((relative, *metadata, content))
    finally:
        os.close(root_descriptor)
    payload = {
        "directories": sorted((path, *metadata) for path, metadata in directory_records.items()),
        "files": records,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_changes(repo: Path) -> str:
    keys = lock_keys(repo)
    managed: set[str] = set()
    for relative in changed_paths(repo, cached=False) + changed_paths(repo, cached=True):
        if not managed_path(relative, keys):
            fail(f"updater touched a forbidden tracked path: {relative}")
        managed.add(relative)
    for relative in untracked_paths(repo):
        if lifecycle_parts(relative) is not None:
            continue
        if not managed_path(relative, keys):
            fail(f"updater touched a forbidden untracked path: {relative}")
        managed.add(relative)
    return "changed" if managed else "clean"


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("snapshot-before", "snapshot-after", "validate-changes"))
    value.add_argument("--repo", type=Path, required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    repo = arguments.repo.resolve(strict=True)
    if not repo.is_dir():
        fail("repository root is not a directory")
    if arguments.command == "snapshot-before":
        print(lifecycle_snapshot(repo, before=True))
    elif arguments.command == "snapshot-after":
        print(lifecycle_snapshot(repo, before=False))
    else:
        print(validate_changes(repo))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, UpdateStateError, ValueError) as error:
        raise SystemExit(f"managed-skill-update-state: {error}") from None

#!/usr/bin/env python3
"""Stable identities for non-PLAN repository content and staged evidence."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


PLAN_PARTS = ("features", "PLAN.md")


class SnapshotError(RuntimeError):
    pass


def git(root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)
    if check and result.returncode != 0:
        raise SnapshotError(result.stderr.decode("utf-8", "replace").strip() or "git snapshot command failed")
    return result.stdout


def frame(digest: hashlib._Hash, label: bytes, value: bytes) -> None:
    digest.update(len(label).to_bytes(4, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def is_plan(relative: str) -> bool:
    parts = Path(relative).parts
    return len(parts) == 3 and parts[0] == PLAN_PARTS[0] and parts[2] == PLAN_PARTS[1]


def artifact_id(repo: Path) -> str:
    root = Path(git(repo.resolve(), "rev-parse", "--show-toplevel").decode().strip()).resolve()
    digest = hashlib.sha256()
    raw = git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    paths = sorted({part.decode("utf-8", "surrogateescape") for part in raw.split(b"\0") if part})
    for relative in paths:
        normalized = Path(relative).as_posix()
        if is_plan(normalized):
            continue
        path = root / relative
        if not os.path.lexists(path):
            continue
        metadata = path.lstat()
        frame(digest, b"path", normalized.encode("utf-8", "surrogateescape"))
        frame(digest, b"mode", str(metadata.st_mode).encode("ascii"))
        if path.is_symlink():
            frame(digest, b"content", os.readlink(path).encode("utf-8", "surrogateescape"))
            continue
        if path.is_dir():
            frame(digest, b"gitlink", git(path, "rev-parse", "HEAD", check=False).strip())
            frame(digest, b"gitlink-status", git(root, "submodule", "status", "--", relative, check=False))
            continue
        if not path.is_file():
            frame(digest, b"special", b"")
            continue
        content = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                content.update(chunk)
        frame(digest, b"content-sha256", content.digest())
    return "sha256:" + digest.hexdigest()


def snapshot_id(repo: Path) -> str:
    root = Path(git(repo.resolve(), "rev-parse", "--show-toplevel").decode().strip()).resolve()
    digest = hashlib.sha256()
    frame(digest, b"artifact-id", artifact_id(root).encode("ascii"))
    index_diff = git(
        root, "diff", "--cached", "--binary", "--no-ext-diff", "--no-textconv", "--", ".",
        ":(exclude,glob)features/*/PLAN.md", check=False,
    )
    frame(digest, b"index-diff", index_diff)
    return "sha256:" + digest.hexdigest()


if __name__ == "__main__":
    functions = {"artifact": artifact_id, "snapshot": snapshot_id}
    if len(sys.argv) != 3 or sys.argv[1] not in functions:
        raise SystemExit(f"usage: {sys.argv[0]} <artifact|snapshot> <repo>")
    print(functions[sys.argv[1]](Path(sys.argv[2])))

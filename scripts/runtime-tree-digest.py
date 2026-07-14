#!/usr/bin/env python3
"""Digest one installed runtime tree without following symlinks."""

from __future__ import annotations

import hashlib
import os
import stat
import sys
from pathlib import Path


def frame(digest, label: bytes, value: bytes) -> None:
    digest.update(len(label).to_bytes(4, "big"))
    digest.update(label)
    digest.update(len(value).to_bytes(8, "big"))
    digest.update(value)


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix().encode("utf-8", "surrogateescape")
        metadata = path.lstat()
        frame(digest, b"path", relative)
        frame(digest, b"mode", str(stat.S_IMODE(metadata.st_mode)).encode("ascii"))
        if path.is_symlink():
            frame(digest, b"link", os.readlink(path).encode("utf-8", "surrogateescape"))
        elif path.is_file():
            frame(digest, b"file", path.read_bytes())
        elif path.is_dir():
            frame(digest, b"dir", b"")
        else:
            raise ValueError(f"unsupported runtime entry: {relative.decode('utf-8', 'replace')}")
    return digest.hexdigest()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <directory>")
    print(tree_digest(Path(sys.argv[1]).resolve()))

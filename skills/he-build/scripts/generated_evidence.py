#!/usr/bin/env python3
"""Compact deterministic evidence for machine-generated lock data."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


NPM_LOCK = "runtime/npm/package-lock.json"


class GeneratedEvidenceError(ValueError):
    pass


def lock_summary(data: bytes, state: str) -> str:
    if not data:
        return f"{state}=absent"
    try:
        value = json.loads(data)
        packages = value["packages"]
        root = packages[""]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GeneratedEvidenceError("generated npm lock schema is invalid") from exc
    entries = [metadata for name, metadata in packages.items() if name]
    if any(not isinstance(item, dict) for item in entries):
        raise GeneratedEvidenceError("generated npm lock package entry is invalid")
    missing = sum(not item.get("resolved") or not item.get("integrity") for item in entries)
    dependencies = json.dumps(root.get("dependencies", {}), sort_keys=True, separators=(",", ":"))
    return "\n".join((
        f"{state}.sha256={hashlib.sha256(data).hexdigest()}",
        f"{state}.bytes={len(data)}",
        f"{state}.lockfileVersion={value.get('lockfileVersion')}",
        f"{state}.packages={len(entries)}",
        f"{state}.missing-resolved-or-integrity={missing}",
        f"{state}.root-dependencies={dependencies}",
    ))


def git_blob(root: Path, revision: str, relative: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{relative}"], capture_output=True, check=False
    )
    return result.stdout if result.returncode == 0 else b""


def generated_diff(root: Path, relative: str, revisions: tuple[str, ...]) -> str | None:
    if relative != NPM_LOCK:
        return None
    if revisions == ("--cached",):
        before, after = git_blob(root, "HEAD", relative), git_blob(root, "", relative)
    elif len(revisions) == 2:
        before, after = git_blob(root, revisions[0], relative), git_blob(root, revisions[1], relative)
    else:
        before = git_blob(root, revisions[0], relative)
        path = root / relative
        after = path.read_bytes() if path.is_file() and not path.is_symlink() else b""
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
            capture_output=True, check=False,
        ).returncode == 0
        if not tracked:
            return ""
    if before == after:
        return ""
    return "# Generated npm lock diff\n" + lock_summary(before, "before") + "\n" + lock_summary(after, "after")


def generated_file(path: Path, relative: str) -> str | None:
    if relative != NPM_LOCK:
        return None
    return "# Generated npm lock\n" + lock_summary(path.read_bytes(), "current")

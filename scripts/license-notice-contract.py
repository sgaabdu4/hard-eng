#!/usr/bin/env python3
"""Validate current managed-skill attribution and historical path claims."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
BOUNDED = ROOT / "skills/deterministic-checks/scripts"
if str(BOUNDED) not in sys.path:
    sys.path.insert(0, str(BOUNDED))

from bounded_run import run_captured
from git_env import git_env

NOTICE = ROOT / "THIRD_PARTY_NOTICES.md"
REVISIONS = {
    "vercel-react-best-practices": "dc8367e6f91c022d83361f03c3313fa05e848ee5",
    "appwrite-backend": "2ba10db98f7872ed93f5ee643097740840d4bdcc",
    "building-flutter-apps": "da683aa74e3627ca1563e0170bea8322189a5d96",
}
HISTORICAL_ADD = "12f52b733b688edede4add9ed75b3a6f2bdde39c"
HISTORICAL_DELETE = "1ef715a2984ce4714c928c454328369c681f6b16"
HISTORICAL_PATHS = ("skills/tdd", "skills/prototype", "skills/improve-codebase-architecture")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"license-notice-contract: FAIL: {message}")


def git(*arguments: str) -> str:
    result = run_captured(["git", *arguments], timeout=30, grace=1, cwd=str(ROOT), env=git_env())
    if result.returncode:
        fail(result.stderr.decode("utf-8", "replace").strip() or "Git query failed")
    return result.stdout.decode("utf-8", "strict").strip()


def main() -> int:
    notice = NOTICE.read_text(encoding="utf-8")
    lock = json.loads((ROOT / ".skill-lock.json").read_text(encoding="utf-8"))
    skills = lock.get("skills")
    if not isinstance(skills, dict) or set(skills) != set(REVISIONS):
        fail("notice inventory does not match managed skill inventory")
    for name, revision in REVISIONS.items():
        entry = skills[name]
        path = f"skills/{name}"
        tree = git("rev-parse", f"HEAD:{path}")
        values = (path, entry.get("sourceUrl"), revision, entry.get("skillFolderHash"))
        if tree != entry.get("skillFolderHash"):
            fail(f"managed skill tree does not match lock: {name}")
        if any(not isinstance(value, str) or value not in notice for value in values):
            fail(f"notice is missing exact provenance for {name}")
    deleted = git("show", "--format=", "--name-status", HISTORICAL_DELETE)
    for path in HISTORICAL_PATHS:
        if (ROOT / path).exists() or (ROOT / path).is_symlink():
            fail(f"obsolete attributed path still exists: {path}")
        if git("cat-file", "-t", f"{HISTORICAL_ADD}:{path}") != "tree":
            fail(f"historical attribution source path is unproven: {path}")
        if f"D\t{path}/" not in deleted:
            fail(f"historical deletion is unproven: {path}")
        if path not in notice:
            fail(f"historical notice omits removed path: {path}")
    for value in (HISTORICAL_ADD, HISTORICAL_DELETE, "MIT"):
        if value not in notice:
            fail(f"historical attribution is missing {value}")
    for value in (
        "Copyright (c) 2026 sgaabdu4",
        "metadata.author: vercel",
        "Permission is hereby granted, free of charge",
        'THE SOFTWARE IS PROVIDED "AS IS"',
    ):
        if value not in notice:
            fail(f"managed-skill licence notice is incomplete: {value}")
    print("license-notice-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

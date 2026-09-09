#!/usr/bin/env python3
"""Bind critical repository claims to wired positive and negative fixtures."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "critical-behavior-inventory.json"
DISPATCHERS = (
    ROOT / "scripts/check-skill-contracts.py",
    ROOT / "scripts/setup-contract-check.py",
    ROOT / "skills/he-plan/scripts/check.py",
)
REQUIRED = {
    "one-time-direct-authorization",
    "safe-setup-publication",
    "green-snapshot-commit-admission",
    "bounded-process-groups",
    "walkthrough-network-containment",
    "walkthrough-review-integrity",
    "visual-field-provenance",
    "explicit-git-currency",
    "github-delivery-identity",
    "skill-package-semantics",
    "git-environment-scrub",
    "bounded-operation-inventory",
    "real-screen-ux-reference",
    "complete-appwrite-schema",
    "managed-skill-lifecycle-state",
    "repository-security-governance",
}


def fail(message: str) -> NoReturn:
    raise SystemExit(f"critical-behavior-inventory: FAIL: {message}")


def owned_file(value: object, field: str) -> Path:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        fail(f"{field} must be a repository-relative file")
    relative = Path(value)
    if any(part in {"", ".", ".."} for part in relative.parts):
        fail(f"{field} has an unsafe path")
    current = ROOT
    for part in relative.parts:
        current = current / part
        metadata = current.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            fail(f"{field} contains a symlink: {value}")
    if not stat.S_ISREG(current.lstat().st_mode):
        fail(f"{field} is not a regular file: {value}")
    return current


def wired(fixture: str) -> bool:
    filename = Path(fixture).name
    stem = Path(fixture).stem.replace("-", "_")
    if (
        fixture.startswith("scripts/setup-")
        and "-contract-check." in fixture
        and "scripts/setup-*-contract-check.*" in (ROOT / "scripts/setup-contract-check.py").read_text(encoding="utf-8")
    ):
        return True
    return any(
        fixture in source or filename in source or stem in source
        for source in (path.read_text(encoding="utf-8") for path in DISPATCHERS)
    )


def validate(payload: object) -> None:
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        fail("schema_version must be 1")
    claims = payload.get("claims")
    if not isinstance(claims, list):
        fail("claims must be a list")
    seen: set[str] = set()
    keys = {"id", "owner", "owner_anchor", "fixture", "positive_anchor", "negative_anchor"}
    for index, claim in enumerate(claims):
        if not isinstance(claim, dict) or set(claim) != keys:
            fail(f"claims[{index}] keys mismatch")
        identifier = claim["id"]
        if not isinstance(identifier, str) or identifier in seen:
            fail(f"claims[{index}].id is missing or duplicate")
        seen.add(identifier)
        owner = owned_file(claim["owner"], f"claims[{index}].owner")
        fixture = owned_file(claim["fixture"], f"claims[{index}].fixture")
        owner_anchor = claim["owner_anchor"]
        positive = claim["positive_anchor"]
        negative = claim["negative_anchor"]
        if not all(isinstance(value, str) and value for value in (owner_anchor, positive, negative)):
            fail(f"claims[{index}] anchors must be non-empty strings")
        if positive == negative:
            fail(f"claims[{index}] positive and negative anchors are identical")
        if owner_anchor not in owner.read_text(encoding="utf-8"):
            fail(f"claims[{index}] owner anchor is missing")
        fixture_source = fixture.read_text(encoding="utf-8")
        if positive not in fixture_source or negative not in fixture_source:
            fail(f"claims[{index}] positive or negative fixture anchor is missing")
        if not wired(claim["fixture"]):
            fail(f"claims[{index}] fixture is not aggregate-wired")
    if seen != REQUIRED:
        fail(f"critical claim set drifted: missing={sorted(REQUIRED - seen)} extra={sorted(seen - REQUIRED)}")


def main() -> int:
    try:
        payload = json.loads(INVENTORY.read_text(encoding="utf-8"))
        validate(payload)
    except (OSError, json.JSONDecodeError) as error:
        fail(str(error))
    print("critical-behavior-inventory: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

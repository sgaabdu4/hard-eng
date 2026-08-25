#!/usr/bin/env python3
"""Enforce the 700-line file limit with a shrink-only ratchet for existing debt."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GIT_ENV_SCRIPTS = REPO / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from bounded_run import run_captured
from git_env import git_env

LIMIT = 700
EXTENSIONS = {
    ".py",
    ".js",
    ".mjs",
    ".cjs",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".pl",
    ".ps1",
    ".dart",
    ".swift",
    ".kt",
    ".md",
}
RATCHET: dict[str, tuple[int, str]] = {
    "scripts/agent-hook-contract-check.py": (1115, "split pending"),
    "scripts/setup-contract-check.py": (946, "split pending"),
    "skills/deterministic-checks/scripts/slice_gate.py": (815, "split pending"),
    "skills/deterministic-checks/scripts/slice_gate_regression_check.py": (1031, "dense contract test"),
    "skills/he-plan/scripts/check.py": (885, "split pending"),
    "skills/he/scripts/execution_evidence_regression.py": (783, "dense contract test"),
    "skills/he/scripts/ticket_state_regression.py": (760, "dense contract test"),
}


def managed_prefixes() -> tuple[str, ...]:
    manifest = json.loads((REPO / "repository.manifest.json").read_text(encoding="utf-8"))
    managed = manifest["skills"]["managed"]
    if not isinstance(managed, list) or not all(isinstance(name, str) and name for name in managed):
        raise SystemExit("check-file-size: repository.manifest.json managed skill list is invalid")
    return tuple(f"skills/{name}/" for name in managed)


def line_count(path: Path) -> int:
    data = path.read_bytes()
    if not data:
        return 0
    count = data.count(b"\n")
    if not data.endswith(b"\n"):
        count += 1
    return count


def tracked_paths() -> list[str]:
    result = run_captured(("git", "ls-files", "-z"), timeout=30, grace=1, cwd=str(REPO), env=git_env())
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(f"check-file-size: cannot enumerate tracked files: {detail}")
    return [item.decode("utf-8") for item in result.stdout.split(b"\0") if item]


def audit(
    root: Path, relative_paths: list[str], excluded_prefixes: tuple[str, ...], ratchet: dict[str, tuple[int, str]]
) -> list[str]:
    findings: list[str] = []
    seen: set[str] = set()
    for relative in sorted(relative_paths):
        if Path(relative).suffix not in EXTENSIONS:
            continue
        if excluded_prefixes and relative.startswith(excluded_prefixes):
            continue
        file_path = root / relative
        if file_path.is_symlink() or not file_path.is_file():
            continue
        lines = line_count(file_path)
        entry = ratchet.get(relative)
        if entry is not None:
            seen.add(relative)
            ceiling, reason = entry
            if lines <= LIMIT:
                findings.append(f"{relative}: {lines} lines is within the {LIMIT}-line limit; remove its ratchet entry")
            elif lines > ceiling:
                findings.append(f"{relative}: {lines} lines exceeds its ratchet ceiling of {ceiling} ({reason})")
            continue
        if lines > LIMIT:
            findings.append(f"{relative}: {lines} lines exceeds the {LIMIT}-line limit")
    for relative in sorted(set(ratchet) - seen):
        findings.append(f"{relative}: ratchet entry matches no scanned tracked file; remove it")
    return findings


def self_check() -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="check-file-size-") as scratch:
        root = Path(scratch)
        (root / "over.py").write_text("x = 1\n" * (LIMIT + 1), encoding="utf-8")
        (root / "valid.py").write_text("x = 1\n" * LIMIT, encoding="utf-8")
        (root / "pinned.py").write_text("x = 1\n" * 800, encoding="utf-8")
        (root / "shrunk.py").write_text("x = 1\n" * 10, encoding="utf-8")
        cases: list[tuple[str, list[str], dict[str, tuple[int, str]], int]] = [
            ("violation fixture", ["over.py"], {}, 1),
            ("valid fixture", ["valid.py"], {}, 0),
            ("ratchet ceiling hold", ["pinned.py"], {"pinned.py": (800, "fixture")}, 0),
            ("ratchet growth", ["pinned.py"], {"pinned.py": (799, "fixture")}, 1),
            ("stale ratchet entry", ["shrunk.py"], {"shrunk.py": (800, "fixture")}, 1),
            ("orphan ratchet entry", ["valid.py"], {"gone.py": (800, "fixture")}, 1),
        ]
        for label, paths, ratchet, expected in cases:
            actual = len(audit(root, paths, (), ratchet))
            if actual != expected:
                failures.append(f"self-check {label}: expected {expected} finding(s), got {actual}")
    return failures


def main() -> int:
    failures = self_check()
    if failures:
        for failure in failures:
            print(f"check-file-size: {failure}", file=sys.stderr)
        return 2
    findings = audit(REPO, tracked_paths(), managed_prefixes(), RATCHET)
    for finding in findings:
        print(f"check-file-size: {finding}")
    if findings:
        return 1
    print(f"check-file-size: PASS limit={LIMIT} ratchet_entries={len(RATCHET)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

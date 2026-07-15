"""Exact-input cache for immutable candidate-admission receipts."""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


CACHE_VERSION = 1
CACHE_MAX_ENTRIES = 64
REPORT_KEYS = frozenset({
    "mode", "result", "unitId", "approvedPlanDigest", "completedSlices",
    "accumulatedPathCount", "accumulatedStateDigest", "candidateState",
    "preservedWipPathCount", "baseSnapshotId", "baseSha", "candidateDigest",
    "candidateSnapshotId", "changedPathCount", "relatedContext", "packet",
    "largestUnits", "reviewShardCount", "error",
})


def digest_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


@functools.lru_cache(maxsize=1)
def tool_digest(script_directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(script_directory.glob("*.py")):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return "sha256:" + digest.hexdigest()


def cache_key(
    *, script_directory: Path, source_snapshot: str, plan_bytes: bytes,
    patch_bytes: bytes, unit_id: str,
) -> str:
    payload = {
        "version": CACHE_VERSION,
        "tool": tool_digest(script_directory.resolve()),
        "sourceSnapshot": source_snapshot,
        "planDigest": digest_bytes(plan_bytes),
        "patchDigest": digest_bytes(patch_bytes),
        "unitId": unit_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def cache_directory(root: Path) -> Path:
    raw = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "--git-common-dir"], text=True,
    ).strip()
    common = Path(raw)
    if not common.is_absolute():
        common = root / common
    directory = common.resolve() / "hard-eng-admission-cache"
    directory.mkdir(mode=0o700, exist_ok=True)
    directory.chmod(0o700)
    return directory


def load(root: Path, key: str) -> dict[str, object] | None:
    try:
        path = cache_directory(root) / f"{key}.json"
        if path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
            return None
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict) or value.get("cacheKey") != key:
        return None
    report = value.get("report")
    return report if isinstance(report, dict) else None


def matches(
    report: dict[str, object] | None, *, unit_id: str, approved_plan_digest: str,
    completed_slices: tuple[str, ...], changed_path_count: int,
    accumulated_state_digest: str, candidate_state: str, source_snapshot: str,
    patch_digest: str,
) -> bool:
    return bool(
        report is not None
        and set(report) == REPORT_KEYS
        and report.get("mode") == "candidate"
        and report.get("result") == "pass"
        and report.get("unitId") == unit_id
        and report.get("approvedPlanDigest") == approved_plan_digest
        and report.get("completedSlices") == list(completed_slices)
        and report.get("changedPathCount") == changed_path_count
        and report.get("accumulatedStateDigest") == accumulated_state_digest
        and report.get("candidateState") == candidate_state
        and report.get("baseSnapshotId") == source_snapshot
        and report.get("candidateDigest") == patch_digest
        and isinstance(report.get("reviewShardCount"), int)
        and report["reviewShardCount"] >= 1
        and isinstance(report.get("candidateSnapshotId"), str)
        and re.fullmatch(r"sha256:[0-9a-f]{64}", report["candidateSnapshotId"])
        and report.get("error") is None
    )


def store(root: Path, key: str, report: dict[str, object]) -> None:
    directory = cache_directory(root)
    payload = json.dumps(
        {"cacheKey": key, "report": report}, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{key}.", dir=directory)
    path = Path(temporary)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        path.replace(directory / f"{key}.json")
        entries = sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime_ns)
        for expired in entries[:-CACHE_MAX_ENTRIES]:
            if not expired.is_symlink():
                expired.unlink(missing_ok=True)
    except BaseException:
        path.unlink(missing_ok=True)
        raise

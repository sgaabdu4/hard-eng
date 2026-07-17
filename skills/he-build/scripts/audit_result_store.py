#!/usr/bin/env python3
"""Atomically persist complete audit aggregates outside the product snapshot."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import tempfile
from pathlib import Path

from audit_contract import AuditError, RESULT_KEYS, SNAPSHOT, parse_usage, validate_result
from secret_scanner import secret_marker


STORED_KEYS = RESULT_KEYS | {"usage", "performance"}
RECEIPT_KEYS = {
    "result", "schemaVersion", "snapshot_id", "verdict", "findingCount", "unknownCount",
    "inventoryStable", "reviewMode", "resultSha256", "resultPath",
}


def _common_git_dir(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise AuditError("audit result store cannot resolve Git metadata")
    return Path(result.stdout.strip()).resolve()


def _validated_payload(result: object) -> bytes:
    if not isinstance(result, dict) or set(result) != STORED_KEYS:
        raise AuditError("audit result store received invalid aggregate keys")
    snapshot = result.get("snapshot_id")
    if not isinstance(snapshot, str) or not SNAPSHOT.fullmatch(snapshot):
        raise AuditError("audit result store received invalid snapshot")
    findings, unknowns = result.get("findings"), result.get("unknowns")
    if not isinstance(findings, list) or not isinstance(unknowns, list):
        raise AuditError("audit result store received invalid evidence lists")
    validate_result(
        {key: result[key] for key in RESULT_KEYS}, snapshot,
        max_findings=len(findings), max_unknowns=len(unknowns),
        max_related_evidence=max((len(item.get("related_evidence", [])) for item in findings), default=0),
    )
    parse_usage(result["usage"])
    performance = result["performance"]
    if (
        not isinstance(performance, dict)
        or not isinstance(performance.get("inventoryStable"), bool)
        or performance.get("reviewMode") not in {"inventory", "re-audit"}
    ):
        raise AuditError("audit result store received invalid performance receipt")
    payload = json.dumps(result, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    marker = secret_marker(payload.decode("utf-8"), "audit-result.json")
    if marker:
        raise AuditError(f"{marker} content blocks audit result storage")
    return payload


def store_audit_result(root: Path, plan: Path, result: object) -> dict[str, object]:
    payload = _validated_payload(result)
    digest = hashlib.sha256(payload).hexdigest()
    plan_digest = hashlib.sha256(plan.read_bytes()).hexdigest()
    snapshot = str(result["snapshot_id"])
    common = _common_git_dir(root)
    parent = common / "hard-eng"
    directory = parent / "audit-results"
    for path in (parent, directory):
        if path.is_symlink():
            raise AuditError("audit result store path is a symlink")
        path.mkdir(mode=0o700, exist_ok=True)
        os.chmod(path, 0o700)
    target = directory / f"{snapshot.removeprefix('sha256:')}-{plan_digest}-{digest}.json"
    if target.exists():
        if target.is_symlink() or target.read_bytes() != payload:
            raise AuditError("audit result store collision")
    else:
        descriptor, temporary = tempfile.mkstemp(prefix=".audit-", dir=directory)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    os.chmod(target, 0o600)
    if not stat.S_ISREG(target.stat().st_mode):
        raise AuditError("audit result store output is not a regular file")
    performance = result["performance"]
    return {
        "result": "stored", "schemaVersion": 1,
        "snapshot_id": snapshot, "verdict": result["verdict"],
        "findingCount": len(result["findings"]), "unknownCount": len(result["unknowns"]),
        "inventoryStable": performance["inventoryStable"],
        "reviewMode": performance["reviewMode"],
        "resultSha256": f"sha256:{digest}", "resultPath": str(target),
    }


def verify_stored_result(receipt: dict[str, object]) -> dict[str, object]:
    if not isinstance(receipt, dict) or set(receipt) != RECEIPT_KEYS:
        raise AuditError("stored audit result receipt is invalid")
    path = Path(str(receipt.get("resultPath", "")))
    if path.is_symlink() or not path.is_file():
        raise AuditError("stored audit result is missing or unsafe")
    payload = path.read_bytes()
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    if digest != receipt.get("resultSha256"):
        raise AuditError("stored audit result digest mismatch")
    result = json.loads(payload)
    _validated_payload(result)
    performance = result["performance"]
    expected = {
        "result": "stored", "schemaVersion": 1,
        "snapshot_id": result["snapshot_id"], "verdict": result["verdict"],
        "findingCount": len(result["findings"]), "unknownCount": len(result["unknowns"]),
        "inventoryStable": performance["inventoryStable"], "reviewMode": performance["reviewMode"],
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise AuditError("stored audit result receipt binding mismatch")
    return result

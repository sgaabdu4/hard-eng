#!/usr/bin/env python3
"""Regression proof for completed audit result preservation and aggregation."""

from __future__ import annotations

import tempfile
from pathlib import Path

import audit_result


def reject_completed(module, path: Path, snapshot: str, raw: str, fail, label: str) -> None:
    path.write_text(raw, encoding="utf-8")
    try:
        module.load_audit_result(path, snapshot, 1)
    except module.AuditError as error:
        if isinstance(error, module.RetryableAuditError):
            fail(f"completed {label} incorrectly entered retry")
    else:
        fail(f"completed {label} did not fail closed")


def check_raw_result_regressions(module, fail, snapshot: str) -> None:
    with tempfile.TemporaryDirectory(prefix="he-raw-audit-result-") as temporary:
        path = Path(temporary) / "result.json"
        malformed = f'{{"snapshot_id":"{snapshot}","verdict"'
        for label, raw in (("non-JSON", "review completed"), ("malformed JSON", malformed)):
            path.write_text(raw, encoding="utf-8")
            preserved = module.load_audit_result(path, snapshot, 1)
            evidence = "".join(item.split(": ", 1)[1] for item in preserved["unknowns"])
            if preserved["verdict"] != "concerns" or preserved["findings"] or evidence != raw:
                fail(f"completed {label} was discarded, repaired, or guessed")
        try:
            module.load_audit_result(path, snapshot, 0)
        except module.RetryableAuditError:
            pass
        else:
            fail("zero-item malformed result skipped its bounded infrastructure retry")
        opaque = "Ab12Cd34" * 4
        reject_completed(module, path, snapshot, '{"message":"sk-' + opaque, fail, "unsafe raw result")
        reject_completed(
            module, path, snapshot, "x" * (audit_result.MAX_RAW_RESULT_BYTES + 1),
            fail, "oversized raw result",
        )


def check_aggregate_regressions(fail, snapshot: str) -> None:
    shards = []
    for index in range(1, 82):
        findings = [{
            "id": "A-1", "axis": "standards", "severity": "low",
            "evidence": f"owner-{index}.py:1", "risk": f"risk-{index}",
            "fix": f"fix-{index}", "required": False,
        }] if index <= 41 else []
        unknowns = [f"unknown-{index}"] if index <= 21 else []
        shards.append({
            "snapshot_id": snapshot,
            "verdict": "concerns" if findings or unknowns else "pass",
            "findings": findings, "unknowns": unknowns, "summary": f"shard-{index}",
        })
    combined = audit_result.aggregate_audit_results(snapshot, tuple(shards))
    if (len(combined["findings"]) != 41 or len(combined["unknowns"]) != 21
            or combined["findings"][40]["id"] != "A-41"
            or combined["findings"][40]["evidence"] != "owner-41.py:1"
            or combined["unknowns"][20] != "unknown-21"):
        fail("valid 81-shard aggregate lost or reordered decision-bearing evidence")
    if audit_result.aggregate_evidence_limits(81) != (3240, 1620):
        fail("81-shard aggregate capacity was not determinable before review")


def check_audit_result_regressions(module, fail, snapshot: str) -> None:
    check_raw_result_regressions(module, fail, snapshot)
    check_aggregate_regressions(fail, snapshot)

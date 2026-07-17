#!/usr/bin/env python3
"""Regression proof for completed audit result preservation and aggregation."""

from __future__ import annotations

import json
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
            "root": f"owner-{index}.py::contract-{index}",
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

    duplicates = tuple({
        "snapshot_id": snapshot, "verdict": "fail", "unknowns": [],
        "summary": f"duplicate-{index}",
        "findings": [{
            "id": "A-1", "axis": "standards", "severity": "medium",
            "root": "scripts/gate.py::runtime-contract", "required": True,
            "evidence": f"scripts/gate.py:{index} wording-{index}",
            "risk": "same contract can pass incorrectly", "fix": "repair the gate owner",
        }],
    } for index in range(1, 6))
    distinct = {
        "snapshot_id": snapshot, "verdict": "fail", "unknowns": [], "summary": "distinct",
        "findings": [{
            "id": "A-1", "axis": "standards", "severity": "medium",
            "root": "scripts/gate.py::timeout-contract", "required": True,
            "evidence": "scripts/gate.py:20 distinct timeout break",
            "risk": "timeout can leak a process", "fix": "repair timeout ownership",
        }],
    }
    deduped = audit_result.aggregate_audit_results(snapshot, (*duplicates, distinct))
    if len(deduped["findings"]) != 2:
        fail("semantic roots were duplicated or distinct risks were suppressed")
    merged = deduped["findings"][0]
    evidence = [merged["evidence"], *merged.get("related_evidence", [])]
    if evidence != [f"scripts/gate.py:{index} wording-{index}" for index in range(1, 6)]:
        fail("semantic root aggregation lost or reordered duplicate evidence")


def check_final_citation_regressions(module, fail, snapshot: str) -> None:
    with tempfile.TemporaryDirectory(prefix="he-final-citation-") as temporary:
        path = Path(temporary) / "result.json"
        result = {
            "snapshot_id": snapshot, "verdict": "concerns", "unknowns": [], "summary": "claim",
            "findings": [{"id": "A-1", "axis": "standards", "severity": "low",
                          "root": "stale.py::current-state",
                          "evidence": "stale.py:1 staged defect", "risk": "wrong state",
                          "fix": "review final owner", "required": False}],
        }
        path.write_text(json.dumps(result), encoding="utf-8")
        preserved = module.load_audit_result(path, snapshot, 1, (), ("final.py",))
        if preserved["findings"] or preserved["verdict"] != "concerns" or "stale.py:1" not in "".join(preserved["unknowns"]):
            fail("citation outside final shard evidence was accepted or discarded")
        result["findings"][0]["evidence"] = "final.py:1 current defect"
        result["findings"][0]["root"] = "final.py::current-state"
        path.write_text(json.dumps(result), encoding="utf-8")
        accepted = module.load_audit_result(path, snapshot, 1, (), ("final.py",))
        if accepted["findings"][0]["evidence"] != "final.py:1 current defect":
            fail("citation bound to final shard evidence was rejected")

        result["findings"][0]["root"] = "stale.py::current-state"
        path.write_text(json.dumps(result), encoding="utf-8")
        preserved = module.load_audit_result(path, snapshot, 1, (), ("final.py",))
        evidence = "\n".join(preserved["unknowns"])
        if (preserved["verdict"] != "concerns" or preserved["findings"]
                or "stale.py::current-state" not in evidence
                or "final.py:1 current defect" not in evidence):
            fail("completed root/citation mismatch was accepted, discarded, or guessed")
        try:
            module.load_audit_result(path, snapshot, 0, (), ("final.py",))
        except module.RetryableAuditError:
            pass
        else:
            fail("zero-item root/citation mismatch skipped bounded retry")

        unsafe = "sk-" + "Ab12Cd34" * 4
        invalid_values = (
            ("unsafe", {**result["findings"][0], "risk": unsafe}),
            ("oversized", {**result["findings"][0], "risk": "x" * (audit_result.MAX_TEXT + 1)}),
            ("malformed", {**result["findings"][0], "related_evidence": 1}),
        )
        for label, finding in invalid_values:
            path.write_text(json.dumps({**result, "findings": [finding]}), encoding="utf-8")
            try:
                module.load_audit_result(path, snapshot, 1, (), ("final.py",))
            except module.AuditError as error:
                if isinstance(error, module.RetryableAuditError):
                    fail(f"completed {label} root mismatch incorrectly entered retry")
            else:
                fail(f"completed {label} root mismatch did not fail closed")


def check_parent_snapshot_binding(module, fail, snapshot: str) -> None:
    schema = module.output_schema()
    if "snapshot_id" in schema["properties"] or "snapshot_id" in schema["required"]:
        fail("child output schema still delegates parent-owned snapshot binding")
    with tempfile.TemporaryDirectory(prefix="he-parent-snapshot-") as temporary:
        path = Path(temporary) / "result.json"
        child = {"verdict": "pass", "findings": [], "unknowns": [], "summary": "clean"}
        for supplied in (child, {**child, "snapshot_id": "sha256:" + "9" * 64}):
            path.write_text(json.dumps(supplied), encoding="utf-8")
            bound = module.load_audit_result(path, snapshot, 1)
            if bound != {**child, "snapshot_id": snapshot}:
                fail("parent did not bind exact snapshot without losing completed child evidence")


def check_audit_result_regressions(module, fail, snapshot: str) -> None:
    check_raw_result_regressions(module, fail, snapshot)
    check_aggregate_regressions(fail, snapshot)
    check_final_citation_regressions(module, fail, snapshot)
    check_parent_snapshot_binding(module, fail, snapshot)

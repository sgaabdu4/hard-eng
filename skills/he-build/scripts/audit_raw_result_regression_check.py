#!/usr/bin/env python3
"""Regression proof for malformed completed audit result preservation."""

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


def check_audit_raw_result_regressions(module, fail, snapshot: str) -> None:
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

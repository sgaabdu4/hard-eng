#!/usr/bin/env python3
"""Regression proof for durable, transport-safe audit aggregates."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


def check_audit_result_store(module, fail) -> None:
    with tempfile.TemporaryDirectory(prefix="he-audit-store-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# PLAN\n", encoding="utf-8")
        snapshot = "sha256:" + "7" * 64
        findings = [{
            "id": f"A-{index}", "axis": "standards", "severity": "medium",
            "root": f"owner_{index}.py::fixture-{index}",
            "evidence": f"owner_{index}.py:{index}", "risk": f"risk {index}",
            "fix": f"fix {index}", "required": True,
        } for index in range(1, 20)]
        result = {
            "snapshot_id": snapshot, "verdict": "fail", "findings": findings,
            "unknowns": ["unknown one", "unknown two"], "summary": "complete aggregate",
            "usage": {"input_tokens": 10, "cached_input_tokens": 2, "output_tokens": 3},
            "performance": {"inventoryStable": False, "reviewMode": "inventory"},
        }
        receipt = module.store_audit_result(root, plan, result)
        path = Path(receipt["resultPath"])
        stored = module.verify_stored_result(receipt)
        if (
            receipt["findingCount"] != 19 or receipt["unknownCount"] != 2
            or len(json.dumps(receipt)) > 2048 or stored["findings"][3:16] != findings[3:16]
            or stat_mode(path) != 0o600
        ):
            fail("audit result store lost middle evidence or emitted an oversized transport payload")
        if module.store_audit_result(root, plan, result) != receipt:
            fail("audit result store is not idempotent for one exact aggregate")
        altered = {**receipt, "findingCount": 18}
        try:
            module.verify_stored_result(altered)
        except module.AuditError:
            pass
        else:
            fail("audit result store accepted a receipt binding mismatch")
        unsafe = {**result, "unknowns": ["api_key=" + "x" * 24]}
        try:
            module.store_audit_result(root, plan, unsafe)
        except module.AuditError:
            pass
        else:
            fail("audit result store accepted unsafe evidence")
        path.write_text("{}", encoding="utf-8")
        try:
            module.verify_stored_result(receipt)
        except module.AuditError:
            pass
        else:
            fail("audit result store accepted a digest mismatch")


def stat_mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777

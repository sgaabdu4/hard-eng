#!/usr/bin/env python3
"""Synthetic regressions for exact-snapshot build evidence receipts."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

import build_evidence


AXES = (
    "intent-spec:pass,deterministic:pass,tests:pass,review:pending,security:pass,"
    "ui-design:na,e2e-runtime:na,docs-context:pass,unknowns:pass"
)


def check_build_evidence_regressions(_module, fail) -> None:
    module = build_evidence
    snapshot = "sha256:" + "1" * 64
    artifact = "sha256:" + "2" * 64
    plan_digest = "sha256:" + "4" * 64
    state = {
        "plan_id": "fixture",
        "approved_plan_digest": plan_digest,
        "build_axes": AXES,
    }
    with tempfile.TemporaryDirectory(prefix="he-build-evidence-") as temporary:
        root = Path(temporary)
        (root / ".git").mkdir()
        module.git_location = lambda _root, _flag: root / ".git"

        def rejected(expected: str, action) -> None:
            try:
                action()
            except module.BuildEvidenceError as error:
                if expected not in str(error):
                    fail(f"build evidence rejection lost actionable code: {error}")
            else:
                fail(f"build evidence accepted invalid proof: {expected}")

        rejected(
            "BUILD_EVIDENCE_MISSING",
            lambda: module.validate_current_build_evidence(
                root, state, snapshot, artifact
            ),
        )
        for axis in ("deterministic", "tests", "security", "docs-context"):
            kind = "focused" if axis == "deterministic" else "specialist"
            module.write_receipt(
                root,
                module.receipt_payload(
                    state["plan_id"],
                    plan_digest,
                    axis,
                    kind,
                    snapshot,
                    artifact,
                    ("gate", axis),
                    1,
                ),
            )
        rejected(
            "BUILD_EVIDENCE_FOCUSED_ONLY",
            lambda: module.validate_current_build_evidence(
                root, state, snapshot, artifact
            ),
        )
        module.write_receipt(
            root,
            module.receipt_payload(
                state["plan_id"],
                plan_digest,
                "deterministic",
                "full-matrix",
                snapshot,
                artifact,
                ("gate", "full"),
                1,
            ),
        )
        receipts = module.validate_current_build_evidence(root, state, snapshot, artifact)
        provenance = module.build_evidence_provenance(receipts)
        expected = (
            f"snapshot_id={snapshot}", f"artifact_id={artifact}",
            f"approved_plan_digest={plan_digest}", "axis=deterministic",
            "kind=full-matrix", "result=pass",
        )
        if len(receipts) != 4 or not all(value in provenance for value in expected):
            fail("validated build evidence did not project exact admission provenance")
        rejected(
            "BUILD_EVIDENCE_STALE",
            lambda: module.validate_current_build_evidence(
                root,
                {**state, "approved_plan_digest": "sha256:" + "5" * 64},
                snapshot,
                artifact,
            ),
        )
        rejected(
            "BUILD_EVIDENCE_STALE",
            lambda: module.validate_current_build_evidence(
                root,
                state,
                "sha256:" + "6" * 64,
                artifact,
            ),
        )
        rejected(
            "BUILD_EVIDENCE_STALE",
            lambda: module.validate_current_build_evidence(
                root,
                state,
                snapshot,
                "sha256:" + "3" * 64,
            ),
        )

        plan = root / "PLAN.md"
        plan.write_text("fixture\n", encoding="utf-8")
        module.git_identity = lambda _repo: (root, "main", "0" * 40)
        module.canonical_plan = lambda _plan, _root: plan
        module.validate_document = lambda _plan, _text: {
            **state,
            "lifecycle_status": "building",
            "active_slice": "final",
            "snapshot_id": snapshot,
            "artifact_id": artifact,
        }
        module.validate_approval_receipt = lambda _root, _state: None
        module.snapshot_id = lambda _root: snapshot
        module.artifact_id = lambda _root: artifact
        recorded = module.record(
            root,
            plan,
            ("deterministic", "tests"),
            "full-matrix",
            5,
            (sys.executable, "-c", "raise SystemExit(0)"),
        )
        if recorded["result"] != "recorded" or recorded["axes"] != [
            "deterministic",
            "tests",
        ]:
            fail("successful bounded matrix did not write exact multi-axis receipts")

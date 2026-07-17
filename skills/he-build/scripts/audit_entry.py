#!/usr/bin/env python3
"""Validate the exact PLAN and artifact entering final audit."""

from __future__ import annotations

from pathlib import Path

from build_evidence import (
    BuildEvidenceError,
    build_evidence_provenance,
    validate_current_build_evidence,
)
from plan_approval import validate_approval_receipt
from plan_contract import parse_build_axes, readiness_for
from plan_state import validate_document
from repository_snapshot import artifact_id


def validate_audit_state(
    state: dict[str, str], snapshot: str, artifact: str, error: type[Exception]
) -> None:
    axes = parse_build_axes(state["build_axes"])
    valid_axes = axes is not None and axes["review"] == "pending" and all(
        status in {"pass", "na"} for axis, status in axes.items() if axis != "review"
    )
    valid = (
        state["lifecycle_status"] == "building"
        and state["current_stage"] == "build"
        and state["active_slice"] == "final"
        and state["snapshot_id"] == snapshot
        and state["artifact_id"] == artifact
        and valid_axes
        and state["build_readiness"] == str(readiness_for(axes))
        and state["build_evidence"] == "stale"
        and all(state[key] == "none" for key in ("open_blockers", "open_issues", "open_unknowns"))
    )
    if not valid:
        raise error("PLAN is not at the exact final-audit entry gate")


def validate_audit_entry(plan: Path, root: Path, snapshot: str, error: type[Exception]) -> str:
    state = validate_document(plan, plan.read_text(encoding="utf-8"))
    artifact = artifact_id(root)
    validate_audit_state(state, snapshot, artifact, error)
    try:
        validate_approval_receipt(root, state)
        receipts = validate_current_build_evidence(root, state, snapshot, artifact)
    except (BuildEvidenceError, ValueError) as exc:
        raise error(str(exc)) from exc
    return build_evidence_provenance(receipts)

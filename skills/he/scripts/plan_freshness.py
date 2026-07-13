#!/usr/bin/env python3
"""Reconcile PLAN evidence with effective repository content."""

from __future__ import annotations

from plan_contract import BUILD_AXES


def snapshot_drift(state: dict[str, str], snapshot: str, artifact: str) -> bool:
    return state["lifecycle_status"] in {"building", "green", "shipping"} and (
        state["snapshot_id"] != snapshot or state["artifact_id"] != artifact
    )


def snapshot_reconciliation(state: dict[str, str], snapshot: str, artifact: str) -> dict[str, str]:
    if not snapshot_drift(state, snapshot, artifact):
        return {}
    active = state["active_slice"] if state["lifecycle_status"] == "building" else "final"
    post_build = state["lifecycle_status"] in {"green", "shipping"}
    return {
        "lifecycle_status": "building",
        "current_stage": "build",
        "stage_status": "in-progress",
        "waiting_for": "agent",
        "next_action": "Repository snapshot changed; rerun final build convergence.",
        "active_slice": active,
        "build_round": str(int(state["build_round"]) + 1) if post_build else state["build_round"],
        "snapshot_id": snapshot,
        "artifact_id": artifact,
        "build_axes": ",".join(f"{axis}:pending" for axis in BUILD_AXES),
        "build_readiness": "0",
        "build_evidence": "stale",
    }

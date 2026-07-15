#!/usr/bin/env python3
"""Hard Eng PLAN state values and lifecycle invariants."""

from __future__ import annotations

import re
from datetime import datetime


REQUIRED = (
    "state_version",
    "plan_id",
    "feature_slug",
    "repository_root",
    "branch",
    "base_sha",
    "head_sha",
    "updated_at_utc",
    "lifecycle_status",
    "current_stage",
    "plan_stage",
    "approved_plan_stages",
    "skipped_plan_stages",
    "stage_status",
    "next_action",
    "waiting_for",
    "plan_approved",
    "approved_plan_digest",
    "open_blockers",
    "open_issues",
    "open_unknowns",
    "active_slice",
    "slice_count",
    "completed_slices",
    "build_round",
    "snapshot_id",
    "artifact_id",
    "build_axes",
    "build_readiness",
    "build_evidence",
)
TERMINAL = {"shipped", "cancelled"}
LIFECYCLE = {"planning", "build-ready", "building", "green", "shipping", *TERMINAL}
STAGES = {"plan", "build", "ship"}
ROUTE_TARGETS = {
    "planning": "$he-plan",
    "build-ready": "$he-build",
    "building": "$he-build",
    "green": "$he-ship",
    "shipping": "$he-ship",
    "shipped": "none",
    "cancelled": "none",
}
LIFECYCLE_CHANGES = {
    "planning": {"planning", "build-ready", "cancelled"},
    "build-ready": {"planning", "build-ready", "building", "cancelled"},
    "building": {"planning", "building", "green", "cancelled"},
    "green": {"planning", "building", "green", "shipping", "cancelled"},
    "shipping": {"planning", "building", "shipping", "shipped", "cancelled"},
    "shipped": {"planning", "shipped"},
    "cancelled": {"planning", "cancelled"},
}
PLAN_STAGES = (
    "repository",
    "research",
    "feature",
    "flows",
    "ux",
    "contracts",
    "technical",
    "testing",
    "rollout",
    "slices",
    "consistency",
    "approval",
)
BUILD_AXES = (
    "intent-spec",
    "deterministic",
    "tests",
    "review",
    "security",
    "ui-design",
    "e2e-runtime",
    "docs-context",
    "unknowns",
)
BUILD_AXIS_STATUS = {"pending", "pass", "fail", "na"}
STAGE_STATUS = {"pending", "in-progress", "awaiting-user", "blocked", "complete"}
WAITING_FOR = {"agent", "user", "external", "none"}
ITEM_KEYS = {
    "open_blockers": ("B", "blocker"),
    "open_issues": ("I", "issue"),
    "open_unknowns": ("U", "unknown"),
}
MUTABLE_STATE_KEYS = {
    "lifecycle_status",
    "current_stage",
    "plan_stage",
    "approved_plan_stages",
    "skipped_plan_stages",
    "stage_status",
    "next_action",
    "waiting_for",
    "plan_approved",
    "active_slice",
    "slice_count",
    "completed_slices",
    "build_round",
    "snapshot_id",
    "artifact_id",
    "build_axes",
    "build_readiness",
    "build_evidence",
}
ITEM_FIELD_INDEX = {"evidence": 2, "impact": 3, "owner": 4, "next-action": 5}
ITEM_STATUS = {"open", "closed"}
AUDIT_ITEM = re.compile(
    r"^audit=A-[1-9][0-9]*; snapshot=sha256:[0-9a-f]{64}; axis=(?:standards|spec); "
    r"severity=(?:critical|medium|low|info); source=.+$"
)
STATE_LINE = re.compile(r"^- ([a-z][a-z0-9_]*) = (.+)$")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SHA = re.compile(r"^(?:[0-9a-f]{40}|UNBORN)$")
ITEM_HEADER = ("ID", "Type", "Evidence", "Impact", "Owner", "Next proof/action", "Status")


class PlanStateError(ValueError):
    pass


def parse_build_axes(value: str) -> dict[str, str] | None:
    if value == "none":
        return None
    entries = tuple(part.partition(":") for part in value.split(","))
    if any(not separator or not name or not status for name, separator, status in entries):
        raise PlanStateError("invalid build_axes")
    if tuple(name for name, _, _ in entries) != BUILD_AXES:
        raise PlanStateError("invalid build_axes")
    axes = {name: status for name, _, status in entries}
    if any(status not in BUILD_AXIS_STATUS for status in axes.values()):
        raise PlanStateError("invalid build_axes")
    return axes


def validate_audit_items(items: dict[str, tuple[str, ...]]) -> None:
    for item_id, row in items.items():
        if not row[2].startswith("audit="):
            continue
        if row[1] != "issue" or row[4] != "$he-build" or not AUDIT_ITEM.fullmatch(row[2]):
            raise PlanStateError(f"invalid audit issue provenance: {item_id}")
        if row[6] == "open":
            valid = re.fullmatch(r"disposition=open; proof=pending; re-audit=pending; fix=.+", row[5])
        else:
            valid = re.fullmatch(
                r"disposition=(?:fixed|rejected); proof=(?!pending(?:;|$)).+; "
                r"re-audit=(?:pending|pass@sha256:[0-9a-f]{64})", row[5]
            )
        if not valid:
            raise PlanStateError(f"invalid audit issue disposition: {item_id}")


def audit_receipt_snapshot(row: tuple[str, ...]) -> str | None:
    receipt = re.search(r"re-audit=pass@(sha256:[0-9a-f]{64})$", row[5])
    return receipt.group(1) if receipt else None


def validate_audit_reaudit_complete(items: dict[str, tuple[str, ...]], current_snapshot: str) -> None:
    for row in items.values():
        if not row[2].startswith("audit="):
            continue
        if audit_receipt_snapshot(row) != current_snapshot:
            raise PlanStateError("post-build audit finding lacks current-snapshot re-audit")


def readiness_for(axes: dict[str, str]) -> int:
    applicable = tuple(status for status in axes.values() if status != "na")
    if not applicable:
        raise PlanStateError("build_axes has no applicable axis")
    return sum(status == "pass" for status in applicable) * 100 // len(applicable)


def validate_values(state: dict[str, str]) -> None:
    if state["state_version"] != "4":
        raise PlanStateError("unsupported state_version")
    for key in ("plan_id", "feature_slug"):
        if not SLUG.fullmatch(state[key]):
            raise PlanStateError(f"invalid {key}")
    for key in ("base_sha", "head_sha"):
        if not SHA.fullmatch(state[key]):
            raise PlanStateError(f"invalid {key}")
    if state["lifecycle_status"] not in LIFECYCLE:
        raise PlanStateError("invalid lifecycle_status")
    if state["current_stage"] not in STAGES:
        raise PlanStateError("invalid current_stage")
    if state["plan_stage"] != "none" and state["plan_stage"] not in PLAN_STAGES:
        raise PlanStateError("invalid plan_stage")
    if state["stage_status"] not in STAGE_STATUS:
        raise PlanStateError("invalid stage_status")
    if state["waiting_for"] not in WAITING_FOR:
        raise PlanStateError("invalid waiting_for")
    if state["plan_approved"] not in {"yes", "no"}:
        raise PlanStateError("invalid plan_approved")
    digest = state["approved_plan_digest"]
    if digest != "none" and not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise PlanStateError("invalid approved_plan_digest")
    if (state["plan_approved"] == "yes") != (digest != "none"):
        raise PlanStateError("plan approval and digest must agree")
    if state["active_slice"] != "none" and not re.fullmatch(r"(?:S-[1-9][0-9]*|final)", state["active_slice"]):
        raise PlanStateError("invalid active_slice")
    if state["slice_count"] != "none" and not re.fullmatch(r"[1-9][0-9]*", state["slice_count"]):
        raise PlanStateError("invalid slice_count")
    completed_slices(state)
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)", state["build_round"]):
        raise PlanStateError("invalid build_round")
    for key in ("snapshot_id", "artifact_id"):
        if state[key] != "none" and not re.fullmatch(r"sha256:[0-9a-f]{64}", state[key]):
            raise PlanStateError(f"invalid {key}")
    parse_build_axes(state["build_axes"])
    if state["build_readiness"] != "none":
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", state["build_readiness"]):
            raise PlanStateError("invalid build_readiness")
        if int(state["build_readiness"]) > 100:
            raise PlanStateError("invalid build_readiness")
    if state["build_evidence"] not in {"none", "stale", "current"}:
        raise PlanStateError("invalid build_evidence")
    try:
        datetime.strptime(state["updated_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PlanStateError("invalid updated_at_utc") from exc
    for key, (prefix, _) in ITEM_KEYS.items():
        value = state[key]
        if value == "none":
            continue
        ids = [item.strip() for item in value.split(",")]
        if not ids or any(not re.fullmatch(rf"{prefix}-[0-9]+", item) for item in ids):
            raise PlanStateError(f"invalid {key}")


def parse_plan_stage_list(state: dict[str, str], key: str) -> tuple[str, ...]:
    value = state[key]
    if value == "none":
        return ()
    stages = tuple(item.strip() for item in value.split(","))
    if not stages or any(stage not in PLAN_STAGES for stage in stages):
        raise PlanStateError(f"invalid {key}")
    if len(stages) != len(set(stages)):
        raise PlanStateError(f"duplicate {key}")
    positions = tuple(PLAN_STAGES.index(stage) for stage in stages)
    if positions != tuple(sorted(positions)):
        raise PlanStateError(f"unordered {key}")
    return stages


def completed_slices(state: dict[str, str]) -> tuple[str, ...]:
    value = state["completed_slices"]
    if value == "none":
        return ()
    slices = tuple(part.strip() for part in value.split(","))
    expected = tuple(f"S-{index}" for index in range(1, len(slices) + 1))
    if slices != expected:
        raise PlanStateError("completed_slices must be an ordered contiguous prefix")
    if state["slice_count"] == "none" or len(slices) > int(state["slice_count"]):
        raise PlanStateError("completed_slices exceeds slice_count")
    return slices


def validate_transition(state: dict[str, str]) -> None:
    lifecycle = state["lifecycle_status"]
    stage = state["current_stage"]
    approved_stages = parse_plan_stage_list(state, "approved_plan_stages")
    skipped_stages = parse_plan_stage_list(state, "skipped_plan_stages")
    if set(approved_stages) & set(skipped_stages):
        raise PlanStateError("plan stage both approved and skipped")
    if "approval" in skipped_stages:
        raise PlanStateError("approval plan stage cannot be skipped")
    accounted = set(approved_stages) | set(skipped_stages)
    completed = completed_slices(state)
    expected_stage = {
        "planning": "plan",
        "build-ready": "build",
        "building": "build",
        "green": "ship",
        "shipping": "ship",
    }
    if lifecycle in expected_stage and stage != expected_stage[lifecycle]:
        raise PlanStateError("lifecycle/current_stage mismatch")
    if lifecycle == "planning":
        if state["plan_approved"] != "no" or state["plan_stage"] == "none":
            raise PlanStateError("planning state requires unapproved plan_stage")
        current_index = PLAN_STAGES.index(state["plan_stage"])
        if accounted != set(PLAN_STAGES[:current_index]):
            raise PlanStateError("planning stages are not an exact completed prefix")
        slices_index = PLAN_STAGES.index("slices")
        if current_index <= slices_index and state["slice_count"] != "none":
            raise PlanStateError("slice_count is owned by slices completion")
        if current_index > slices_index and state["slice_count"] == "none":
            raise PlanStateError("post-slices planning requires slice_count")
    elif state["plan_stage"] != "none":
        raise PlanStateError("non-planning state requires plan_stage=none")
    post_plan = {"build-ready", "building", "green", "shipping", "shipped"}
    if lifecycle in post_plan:
        if state["plan_approved"] != "yes":
            raise PlanStateError("post-plan lifecycle requires approval")
        if accounted != set(PLAN_STAGES) or "approval" not in approved_stages:
            raise PlanStateError("post-plan lifecycle requires every plan stage accounted and approval approved")
        if state["slice_count"] == "none":
            raise PlanStateError("post-plan lifecycle requires slice_count")
    if lifecycle == "build-ready":
        if any(state[key] != "none" for key in ITEM_KEYS):
            raise PlanStateError("build-ready state has open blockers/issues/unknowns")
        if state["stage_status"] != "pending":
            raise PlanStateError("build-ready state requires pending build stage")
    initial_build = {
        "active_slice": "none",
        "completed_slices": "none",
        "build_round": "0",
        "snapshot_id": "none",
        "artifact_id": "none",
        "build_axes": "none",
        "build_readiness": "none",
        "build_evidence": "none",
    }
    if lifecycle in {"planning", "build-ready"} and any(state[key] != value for key, value in initial_build.items()):
        raise PlanStateError("pre-build lifecycle has build execution state")
    axes = parse_build_axes(state["build_axes"])
    if lifecycle == "building":
        if state["active_slice"] == "none" or "none" in (state["snapshot_id"], state["artifact_id"]):
            raise PlanStateError("building state requires active slice, snapshot, and artifact")
        if axes is None or state["build_readiness"] == "none" or state["build_evidence"] == "none":
            raise PlanStateError("building state requires axes, readiness, and evidence status")
        if int(state["build_readiness"]) != readiness_for(axes):
            raise PlanStateError("build_readiness does not match build_axes")
        count = int(state["slice_count"])
        if state["active_slice"] == "final":
            if len(completed) != count:
                raise PlanStateError("final convergence requires every slice complete")
        else:
            active = int(state["active_slice"].removeprefix("S-"))
            if active != len(completed) + 1 or active > count:
                raise PlanStateError("active_slice must follow completed_slices")
    if lifecycle in {"green", "shipping", "shipped"}:
        if any(state[key] != "none" for key in ITEM_KEYS):
            raise PlanStateError("post-build lifecycle has open blockers/issues/unknowns")
        if state["active_slice"] != "none":
            raise PlanStateError("post-build lifecycle has active slice")
        if len(completed) != int(state["slice_count"]):
            raise PlanStateError("post-build lifecycle requires every slice complete")
        if axes is None or any(status not in {"pass", "na"} for status in axes.values()):
            raise PlanStateError("post-build lifecycle has incomplete build axis")
        if axes["review"] != "pass":
            raise PlanStateError("post-build lifecycle requires review pass")
        if "none" in (state["snapshot_id"], state["artifact_id"]) or state["build_readiness"] != "100" or state["build_evidence"] != "current":
            raise PlanStateError("post-build lifecycle requires current readiness 100 evidence")
        if readiness_for(axes) != 100:
            raise PlanStateError("post-build lifecycle readiness mismatch")
    if lifecycle == "green" and state["stage_status"] != "pending":
        raise PlanStateError("green state requires pending ship stage")
    if lifecycle == "shipped" and (stage != "ship" or state["stage_status"] != "complete"):
        raise PlanStateError("shipped state is incomplete")


def validate_state_change(before: dict[str, str], after: dict[str, str]) -> None:
    old_lifecycle = before["lifecycle_status"]
    new_lifecycle = after["lifecycle_status"]
    if new_lifecycle not in LIFECYCLE_CHANGES[old_lifecycle]:
        raise PlanStateError("illegal lifecycle transition")
    if before["slice_count"] != after["slice_count"]:
        set_at_slices = (
            old_lifecycle == "planning"
            and new_lifecycle == "planning"
            and before["plan_stage"] == "slices"
            and before["slice_count"] == "none"
            and after["slice_count"] != "none"
        )
        reset_for_replan = new_lifecycle == "planning" and after["slice_count"] == "none"
        if not (set_at_slices or reset_for_replan):
            raise PlanStateError("slice_count can change only at slices completion or replan reset")
    if (
        before["approved_plan_digest"] != after["approved_plan_digest"]
        and not (
            old_lifecycle == "planning"
            and new_lifecycle == "build-ready"
            and before["approved_plan_digest"] == "none"
        )
        and not (new_lifecycle == "planning" and after["approved_plan_digest"] == "none")
    ):
        raise PlanStateError("approved plan digest can change only at approval or replan reset")
    if new_lifecycle in {"planning", "cancelled"}:
        return

    old_completed = len(completed_slices(before))
    new_completed = len(completed_slices(after))
    if new_completed < old_completed or new_completed > old_completed + 1:
        raise PlanStateError("completed_slices must advance exactly one slice")
    if old_lifecycle == "building" and new_lifecycle == "green" and before["active_slice"] != "final":
        raise PlanStateError("green requires prior final convergence")

    old_round = int(before["build_round"])
    new_round = int(after["build_round"])
    if old_lifecycle == "build-ready" and new_lifecycle == "building" and new_round != 0:
        raise PlanStateError("build must start at round 0")
    if old_lifecycle == "building" and new_lifecycle in {"building", "green"}:
        if new_round < old_round or new_round > old_round + 1:
            raise PlanStateError("build_round must stay or increment once")
        if new_round > old_round and after["build_evidence"] != "stale":
            raise PlanStateError("new build round requires stale evidence")
    if old_lifecycle in {"green", "shipping"} and new_lifecycle == "building":
        if new_round != old_round + 1 or after["build_evidence"] != "stale":
            raise PlanStateError("ship return requires one new stale build round")

    identity_changed = any(before[key] != after[key] for key in ("snapshot_id", "artifact_id"))
    reconciliation = (
        old_lifecycle == new_lifecycle
        and old_lifecycle == "shipping"
        and before["head_sha"] != after["head_sha"]
        and before["artifact_id"] == after["artifact_id"]
        and before["build_evidence"] == after["build_evidence"]
    )
    if identity_changed and after["build_evidence"] != "stale" and not reconciliation:
        raise PlanStateError("new repository identity requires stale build evidence")
    if old_lifecycle in {"green", "shipping", "shipped"} and new_lifecycle != "building" and identity_changed and not reconciliation:
        raise PlanStateError("post-build repository identity cannot change")
    if before["build_evidence"] == "stale" and after["build_evidence"] == "current":
        axes = parse_build_axes(after["build_axes"])
        if axes is None or any(status not in {"pass", "na"} for status in axes.values()):
            raise PlanStateError("current build evidence requires complete axes")
        if any(after[key] != "none" for key in ITEM_KEYS):
            raise PlanStateError("current build evidence requires no open items")

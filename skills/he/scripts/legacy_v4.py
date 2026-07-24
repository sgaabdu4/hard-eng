"""Exact one-time reader and archive owner for legacy Hard Eng v4 plans."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path


class LegacyV4Error(ValueError):
    pass


KEYS = (
    "state_version", "plan_id", "feature_slug", "repository_root", "branch",
    "base_sha", "head_sha", "updated_at_utc", "lifecycle_status", "current_stage",
    "plan_stage", "approved_plan_stages", "skipped_plan_stages", "stage_status",
    "next_action", "waiting_for", "plan_approved", "approved_plan_digest",
    "open_blockers", "open_issues", "open_unknowns", "active_slice", "slice_count",
    "completed_slices", "build_round", "snapshot_id", "artifact_id", "build_axes",
    "build_readiness", "build_evidence",
)
STATE_ROW = re.compile(r"^- ([a-z_]+) = (.*)$")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLICE = re.compile(r"S-([1-9][0-9]*)")
FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
SHA = re.compile(r"(?:[0-9a-f]{40}|UNBORN)")
PLAN_STAGES = (
    "repository", "research", "feature", "flows", "ux", "contracts",
    "technical", "testing", "rollout", "slices", "consistency", "approval",
)
AXES = (
    "intent-spec", "deterministic", "tests", "review", "security",
    "ui-design", "e2e-runtime", "docs-context", "unknowns",
)
AXIS_STATUS = {"pending", "pass", "fail", "na"}
LIFECYCLES = {"planning", "build-ready", "building", "green", "shipping", "shipped", "cancelled"}


def _list(value: str, allowed: tuple[str, ...], label: str) -> tuple[str, ...]:
    if value == "none":
        return ()
    result = tuple(part.strip() for part in value.split(","))
    if (
        any(item not in allowed for item in result)
        or len(result) != len(set(result))
        or tuple(allowed.index(item) for item in result)
        != tuple(sorted(allowed.index(item) for item in result))
    ):
        raise LegacyV4Error(f"invalid {label}")
    return result


def _axes(value: str) -> dict[str, str] | None:
    if value == "none":
        return None
    parts = tuple(part.partition(":") for part in value.split(","))
    if (
        tuple(name for name, separator, _ in parts if separator) != AXES
        or len(parts) != len(AXES)
        or any(status not in AXIS_STATUS for _, _, status in parts)
    ):
        raise LegacyV4Error("invalid build_axes")
    return {name: status for name, _, status in parts}


def _readiness(axes: dict[str, str]) -> int:
    applicable = tuple(value for value in axes.values() if value != "na")
    if not applicable:
        raise LegacyV4Error("build_axes has no applicable axis")
    return sum(value == "pass" for value in applicable) * 100 // len(applicable)


def _validate(values: dict[str, str]) -> None:
    if any(value == "" for value in values.values()):
        raise LegacyV4Error("legacy v4 State values must be nonempty")
    if values["state_version"] != "4":
        raise LegacyV4Error("unsupported legacy state_version")
    if not SLUG.fullmatch(values["plan_id"]) or not SLUG.fullmatch(values["feature_slug"]):
        raise LegacyV4Error("invalid legacy identity")
    if not values["repository_root"] or not values["branch"]:
        raise LegacyV4Error("missing legacy repository provenance")
    if not SHA.fullmatch(values["base_sha"]) or not SHA.fullmatch(values["head_sha"]):
        raise LegacyV4Error("invalid legacy SHA")
    try:
        datetime.strptime(values["updated_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise LegacyV4Error("invalid legacy updated_at_utc") from error
    lifecycle = values["lifecycle_status"]
    if lifecycle not in LIFECYCLES:
        raise LegacyV4Error("invalid legacy lifecycle_status")
    if values["current_stage"] not in {"plan", "build", "ship"}:
        raise LegacyV4Error("invalid legacy current_stage")
    plan_stage = values["plan_stage"]
    if plan_stage != "none" and plan_stage not in PLAN_STAGES:
        raise LegacyV4Error("invalid legacy plan_stage")
    if values["stage_status"] not in {"pending", "in-progress", "awaiting-user", "blocked", "complete"}:
        raise LegacyV4Error("invalid legacy stage_status")
    if values["waiting_for"] not in {"agent", "user", "external", "none"}:
        raise LegacyV4Error("invalid legacy waiting_for")
    approved = values["plan_approved"]
    digest = values["approved_plan_digest"]
    if approved not in {"yes", "no"} or ((approved == "yes") != bool(FINGERPRINT.fullmatch(digest))):
        if not (approved == "no" and digest == "none"):
            raise LegacyV4Error("legacy approval and digest disagree")
    approved_stages = _list(values["approved_plan_stages"], PLAN_STAGES, "approved_plan_stages")
    skipped_stages = _list(values["skipped_plan_stages"], PLAN_STAGES, "skipped_plan_stages")
    if set(approved_stages) & set(skipped_stages) or "approval" in skipped_stages:
        raise LegacyV4Error("invalid legacy planning stage accounting")
    accounted = set(approved_stages) | set(skipped_stages)
    if plan_stage != "none":
        index = PLAN_STAGES.index(plan_stage)
        if accounted != set(PLAN_STAGES[:index]):
            raise LegacyV4Error("legacy planning stages are not an exact prefix")
    for key, prefix in (("open_blockers", "B"), ("open_issues", "I"), ("open_unknowns", "U")):
        value = values[key]
        if value != "none" and any(
            not re.fullmatch(rf"{prefix}-[0-9]+", item.strip())
            for item in value.split(",")
        ):
            raise LegacyV4Error(f"invalid {key}")
    count = values["slice_count"]
    if count != "none" and not re.fullmatch(r"[1-9][0-9]*", count):
        raise LegacyV4Error("invalid slice_count")
    completed = () if values["completed_slices"] == "none" else tuple(
        part.strip() for part in values["completed_slices"].split(",")
    )
    if completed != tuple(f"S-{index}" for index in range(1, len(completed) + 1)):
        raise LegacyV4Error("completed_slices must be a contiguous prefix")
    if completed and (count == "none" or len(completed) > int(count)):
        raise LegacyV4Error("completed_slices exceeds slice_count")
    active = values["active_slice"]
    if active not in {"none", "final"} and not SLICE.fullmatch(active):
        raise LegacyV4Error("invalid active_slice")
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)", values["build_round"]):
        raise LegacyV4Error("invalid build_round")
    for key in ("snapshot_id", "artifact_id"):
        if values[key] != "none" and not FINGERPRINT.fullmatch(values[key]):
            raise LegacyV4Error(f"invalid {key}")
    axes = _axes(values["build_axes"])
    readiness = values["build_readiness"]
    if readiness != "none" and (
        not re.fullmatch(r"(?:0|[1-9][0-9]{0,2})", readiness) or int(readiness) > 100
    ):
        raise LegacyV4Error("invalid build_readiness")
    if values["build_evidence"] not in {"none", "stale", "current"}:
        raise LegacyV4Error("invalid build_evidence")
    expected_stage = {
        "planning": "plan", "build-ready": "build", "building": "build",
        "green": "ship", "shipping": "ship", "shipped": "ship",
    }
    if lifecycle in expected_stage and values["current_stage"] != expected_stage[lifecycle]:
        raise LegacyV4Error("legacy lifecycle/current_stage mismatch")
    if lifecycle == "planning":
        if approved != "no" or plan_stage == "none":
            raise LegacyV4Error("invalid planning approval state")
        slices_index = PLAN_STAGES.index("slices")
        current_index = PLAN_STAGES.index(plan_stage)
        if (current_index <= slices_index) != (count == "none"):
            raise LegacyV4Error("invalid planning slice_count ownership")
    elif lifecycle != "cancelled":
        if plan_stage != "none" or approved != "yes" or accounted != set(PLAN_STAGES):
            raise LegacyV4Error("invalid post-plan approval state")
    initial = (
        active == "none" and not completed and values["build_round"] == "0"
        and values["snapshot_id"] == values["artifact_id"] == "none"
        and axes is None and readiness == values["build_evidence"] == "none"
    )
    if lifecycle in {"planning", "build-ready"} and not initial:
        raise LegacyV4Error("pre-build state contains execution evidence")
    if lifecycle == "build-ready" and (
        values["stage_status"] != "pending"
        or any(values[key] != "none" for key in ("open_blockers", "open_issues", "open_unknowns"))
        or count == "none"
    ):
        raise LegacyV4Error("invalid build-ready state")
    if lifecycle == "building":
        if (
            count == "none" or active in {"none"}
            or values["snapshot_id"] == "none" or values["artifact_id"] == "none"
            or axes is None or readiness == "none" or values["build_evidence"] == "none"
            or int(readiness) != _readiness(axes)
        ):
            raise LegacyV4Error("invalid building evidence")
        if active == "final":
            valid_active = len(completed) == int(count)
        else:
            active_number = int(active.removeprefix("S-"))
            valid_active = active_number == len(completed) + 1 and active_number <= int(count)
        if not valid_active:
            raise LegacyV4Error("active_slice does not follow completed_slices")
    if lifecycle in {"green", "shipping", "shipped"}:
        if (
            count == "none" or active != "none" or len(completed) != int(count)
            or axes is None or any(value not in {"pass", "na"} for value in axes.values())
            or axes["review"] != "pass" or values["snapshot_id"] == "none"
            or values["artifact_id"] == "none" or readiness != "100"
            or values["build_evidence"] != "current"
        ):
            raise LegacyV4Error("invalid post-build evidence")
    if lifecycle == "shipped" and values["stage_status"] != "complete":
        raise LegacyV4Error("invalid shipped state")


def parse(text: str, repo: Path, path: Path) -> dict[str, str]:
    lines = text.splitlines()
    headings = [index for index, line in enumerate(lines) if line == "## State"]
    if len(headings) != 1:
        raise LegacyV4Error("legacy v4 requires exactly one ## State section")
    start = headings[0] + 1
    end = next(
        (index for index in range(start, len(lines)) if lines[index].startswith("## ")),
        len(lines),
    )
    values: dict[str, str] = {}
    for raw in lines[start:end]:
        if not raw.strip():
            continue
        match = STATE_ROW.fullmatch(raw.strip())
        if not match or match.group(1) in values:
            raise LegacyV4Error("legacy v4 State section is malformed")
        values[match.group(1)] = match.group(2).strip()
    if set(values) != set(KEYS):
        raise LegacyV4Error("legacy v4 State keys do not match the exact supported schema")
    _validate(values)
    if (
        values["feature_slug"] != path.parent.name
    ):
        raise LegacyV4Error("legacy v4 identity does not match repository and canonical path")
    lifecycle = values["lifecycle_status"]
    supported = (
        lifecycle == "planning"
        and values["current_stage"] == "plan"
        and values["plan_approved"] == "no"
        and values["approved_plan_digest"] == "none"
    ) or (
        lifecycle in {"build-ready", "building"}
        and values["plan_approved"] == "yes"
        and FINGERPRINT.fullmatch(values["approved_plan_digest"]) is not None
    )
    if not supported and lifecycle not in {"shipped", "cancelled"}:
        raise LegacyV4Error("legacy v4 state has no exact lean mapping; owner decision required")
    return values


def migration_sections(
    source: str, legacy: dict[str, str], source_hash: str
) -> tuple[dict[str, str], str, str]:
    risk = re.search(r"(?m)^- risk_tier = (standard|critical)$", source)
    risk_level = risk.group(1) if risk else "critical"
    overlay = (
        "none" if risk_level == "standard"
        else "active legacy slice + preserved v4 safety contract proof"
    )
    quoted = "\n".join(f"> {line}" if line else ">" for line in source.splitlines())
    completed_count = (
        0
        if legacy["completed_slices"] == "none"
        else len(legacy["completed_slices"].split(","))
    )
    active = (
        legacy["active_slice"]
        if SLICE.fullmatch(legacy["active_slice"])
        else "final"
        if legacy["active_slice"] == "final"
        else f"S-{completed_count + 1}"
    )
    approved = legacy["plan_approved"] == "yes"
    outcome = (
        "Preserve the accepted legacy v4 outcome without semantic rewriting."
        if approved
        else "Carry the legacy v4 intended outcome forward for alignment without semantic rewriting."
    )
    boundary = (
        "Migration does not change the accepted product boundary."
        if approved
        else "Migration does not approve a product boundary; the legacy planning content remains pending review."
    )
    source_label = (
        "accepted legacy v4 document"
        if approved
        else "unapproved legacy v4 planning document"
    )
    sections = {
        "## Outcome\n- TBD": (
            f"## Outcome\n- {outcome}"
        ),
        "## Non-goals\n- TBD": (
            f"## Non-goals\n- {boundary}"
        ),
        "## Material decisions\n- TBD": (
            "## Material decisions\n"
            f"- migration_source_sha256 = {source_hash}\n"
            f"- legacy_approval_digest = {legacy['approved_plan_digest']}\n"
            f"- legacy_lifecycle_status = {legacy['lifecycle_status']}\n"
            f"- legacy_archive = PLAN.legacy-v4.{source_hash.removeprefix('sha256:')}.md\n"
            f"- {source_label}, readable content-preserving view:\n"
            f"{quoted}"
        ),
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n"
            "- Preserve every legacy example and proof in the embedded v4 document."
        ),
        "## Affected canonical areas\n- TBD": (
            "## Affected canonical areas\n"
            "- Preserve the canonical areas named by the embedded legacy v4 document."
        ),
        "- rollback = TBD": (
            "- rollback = restore the byte-exact archived v4 PLAN before new v1 mutation."
        ),
        "## First vertical slice\n- S-1 = TBD\n- proof = TBD": (
            "## First vertical slice\n"
            f"- {active} = continue the active legacy vertical slice.\n"
            "- proof = preserve and complete its embedded legacy proof contract."
        ),
    }
    return sections, risk_level, overlay

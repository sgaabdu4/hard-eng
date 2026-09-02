#!/usr/bin/env python3
"""Machine-checked planning method: one receipt per required planning step, refused approval until complete."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_lib import (
    EvidenceError,
    enforcement_configured,
    git_value,
    load_receipt,
    plan_id,
    receipt_path,
    safe_receipt_json,
    utc_now,
    utc_text,
)
from execution_evidence import validate_research
from plan_sections import PlanError, parse_sections, parse_slices

RECEIPT_NAME = "plan-steps.json"
SCHEMA_VERSION = 1
STEPS = ("code-study", "research", "edge-scan", "decisions", "slices", "closing")
RECORDED_STEPS = tuple(step for step in STEPS if step != "research")
AXES = (
    "actors",
    "empty-error-retry",
    "data-lifecycle",
    "delivery-form",
    "external-concurrency",
    "accessibility",
    "rollout-rollback",
)
DECISION_STATUSES = ("settled", "user-decision", "deferred", "out-of-scope", "blocked-external")
OPEN_DECISION_STATUS = "user-decision"
TICKET_CHOICES = ("none", "local", "github", "jira", "azdo")
SLICE_ID = re.compile(r"^S-([1-9][0-9]*)$")
DECISION_ID = re.compile(r"^D-[1-9][0-9]*$")


class PlanStepError(Exception):
    """Invalid planning-step receipt or payload."""


def _text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PlanStepError(f"{key} must be a nonempty string")
    return value.strip()


def _string_list(payload: dict[str, object], key: str, *, allow_empty: bool) -> list[str]:
    value = payload.get(key)
    if value is None and allow_empty:
        return []
    if not isinstance(value, list) or (not value and not allow_empty):
        raise PlanStepError(f"{key} must be a {'' if allow_empty else 'nonempty '}list of strings")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise PlanStepError(f"{key} entries must be nonempty strings")
    return [item.strip() for item in value]


def _repository_file(repo: Path, item: str) -> None:
    raw = Path(item)
    if raw.is_absolute() or ".." in raw.parts:
        raise PlanStepError(f"owners must be repository-relative: {item}")
    path = repo / raw
    if not path.is_file() or path.is_symlink():
        raise PlanStepError(f"owner is not a repository file: {item}")


def validate_code_study(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    owners = _string_list(payload, "owners", allow_empty=False)
    for item in owners:
        _repository_file(repo, item)
    return {
        "owners": owners,
        "callers": _string_list(payload, "callers", allow_empty=True),
        "notes": _text(payload, "notes"),
    }


def validate_edge_scan(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    axes = payload.get("axes")
    if not isinstance(axes, dict):
        raise PlanStepError("axes must be an object with one entry per axis")
    missing = [axis for axis in AXES if not isinstance(axes.get(axis), str) or not str(axes[axis]).strip()]
    if missing:
        raise PlanStepError(f"edge-scan requires every axis: missing {', '.join(missing)}")
    unknown = sorted(set(axes) - set(AXES))
    if unknown:
        raise PlanStepError(f"edge-scan has unknown axes: {', '.join(unknown)}")
    return {"axes": {axis: str(axes[axis]).strip() for axis in AXES}}


def validate_decisions(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    entries = payload.get("decisions")
    if not isinstance(entries, list) or not entries:
        raise PlanStepError("decisions must be a nonempty list")
    seen: set[str] = set()
    decisions: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise PlanStepError("each decision must be an object")
        identifier = _text(entry, "id")
        if not DECISION_ID.match(identifier) or identifier in seen:
            raise PlanStepError(f"decision ids must be unique D-<n>: {identifier}")
        seen.add(identifier)
        status = _text(entry, "status")
        if status not in DECISION_STATUSES:
            raise PlanStepError(f"{identifier} status must be one of {', '.join(DECISION_STATUSES)}")
        decisions.append(
            {
                "id": identifier,
                "decision": _text(entry, "decision"),
                "status": status,
                "settled_by": _text(entry, "settled_by"),
            }
        )
    return {"decisions": decisions}


def brief_slices(plan: Path) -> list[dict[str, object]]:
    try:
        graph = parse_slices(parse_sections(plan.read_text(encoding="utf-8"))["Vertical slices"])
    except (OSError, UnicodeError, PlanError) as error:
        raise PlanStepError(f"Vertical slices section is not recordable: {error}") from error
    return [{"id": identifier, "depends_on": list(dependencies)} for identifier, dependencies in graph.items()]


def validate_slices(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    entries = payload.get("slices")
    if not isinstance(entries, list) or not entries:
        raise PlanStepError("slices must be a nonempty list")
    graph: dict[str, list[str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise PlanStepError("each slice must be an object")
        identifier = _text(entry, "id")
        if not SLICE_ID.match(identifier) or identifier in graph:
            raise PlanStepError(f"slice ids must be unique S-<n>: {identifier}")
        graph[identifier] = _string_list(entry, "depends_on", allow_empty=True)
    expected = [f"S-{index}" for index in range(1, len(graph) + 1)]
    if list(graph) != expected:
        raise PlanStepError("slices must be numbered S-1..S-n in order without gaps")
    for identifier, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph or dependency == identifier:
                raise PlanStepError(f"{identifier} depends on unknown slice {dependency}")
    assert_acyclic(graph)
    return {"slices": [{"id": identifier, "depends_on": graph[identifier]} for identifier in graph]}


def assert_acyclic(graph: dict[str, list[str]]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in done:
            return
        if node in visiting:
            raise PlanStepError("slice dependency loop: " + " -> ".join((*path, node)))
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency, (*path, node))
        visiting.discard(node)
        done.add(node)

    for node in graph:
        visit(node, ())


def validate_closing(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    tickets = _text(payload, "tickets")
    if tickets not in TICKET_CHOICES:
        raise PlanStepError(f"tickets must be one of {', '.join(TICKET_CHOICES)}")
    return {"tickets": tickets, "tracker": _text(payload, "tracker"), "reply": _text(payload, "reply")}


VALIDATORS = {
    "code-study": validate_code_study,
    "edge-scan": validate_edge_scan,
    "decisions": validate_decisions,
    "slices": validate_slices,
    "closing": validate_closing,
}


def current_head(repo: Path) -> str:
    try:
        return git_value(repo, "rev-parse", "--verify", "HEAD")
    except EvidenceError:
        return "unborn"


def load(repo: Path, plan: Path) -> dict[str, object]:
    path = receipt_path(plan, RECEIPT_NAME)
    if not path.is_file() or path.is_symlink():
        return {"schema_version": SCHEMA_VERSION, "plan_id": plan_id(plan), "steps": {}}
    try:
        value, _, _ = load_receipt(repo, plan, RECEIPT_NAME)
    except EvidenceError as error:
        raise PlanStepError(str(error)) from error
    if value.get("schema_version") != SCHEMA_VERSION or value.get("plan_id") != plan_id(plan):
        raise PlanStepError("plan-steps receipt does not belong to this Feature Brief")
    if not isinstance(value.get("steps"), dict):
        raise PlanStepError("plan-steps receipt requires a steps object")
    return value


def record(repo: Path, plan: Path, step: str, payload: dict[str, object]) -> dict[str, object]:
    if step not in VALIDATORS:
        raise PlanStepError(f"step must be one of {', '.join(RECORDED_STEPS)}")
    receipt = load(repo, plan)
    if step == "slices" and "slices" not in payload:
        payload = {"slices": brief_slices(plan)}
    entry = VALIDATORS[step](repo, payload)
    entry["recorded_at"] = utc_text(utc_now())
    entry["repository_head"] = current_head(repo)
    existing = receipt["steps"]
    assert isinstance(existing, dict)
    steps: dict[str, object] = dict(existing)
    steps[step] = entry
    receipt["steps"] = steps
    path = receipt_path(plan, RECEIPT_NAME)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        safe_receipt_json(repo, path, receipt)
    except EvidenceError as error:
        raise PlanStepError(str(error)) from error
    return entry


def status(repo: Path, plan: Path) -> dict[str, list[str]]:
    receipt = load(repo, plan)
    steps = receipt["steps"]
    assert isinstance(steps, dict)
    done: list[str] = []
    missing: list[str] = []
    stale: list[str] = []
    open_decisions: list[str] = []
    head = current_head(repo)
    for step in STEPS:
        if step == "research":
            try:
                validate_research(repo, plan)
            except EvidenceError:
                missing.append(step)
            else:
                done.append(step)
            continue
        entry = steps.get(step)
        if not isinstance(entry, dict):
            missing.append(step)
        elif step == "code-study" and entry.get("repository_head") != head:
            stale.append(step)
        else:
            done.append(step)
            if step == "decisions":
                open_decisions.extend(
                    str(item["id"])
                    for item in entry.get("decisions", [])
                    if isinstance(item, dict) and item.get("status") == OPEN_DECISION_STATUS
                )
    return {"done": done, "missing": missing, "stale": stale, "open_decisions": open_decisions}


def approval_error(repo: Path, plan: Path) -> str | None:
    if not enforcement_configured(repo):
        return None
    summary = status(repo, plan)
    if summary["missing"]:
        return f"planning step not recorded: {summary['missing'][0]} (plan_state.py record-step)"
    if summary["stale"]:
        return f"planning step is stale for the current HEAD: {summary['stale'][0]} (re-run record-step)"
    if summary["open_decisions"]:
        return f"decisions still waiting on the user: {', '.join(summary['open_decisions'])}"
    return None


def emit_lines(repo: Path, plan: Path) -> list[str]:
    try:
        summary = status(repo, plan)
    except PlanStepError as error:
        return [f"plan_steps=invalid: {error}"]
    lines = [f"plan_steps={len(summary['done'])}/{len(STEPS)}"]
    pending = [*summary["missing"], *(f"{step} (stale)" for step in summary["stale"])]
    if pending:
        lines.append("plan_steps_missing=" + ", ".join(pending))
    if summary["open_decisions"]:
        lines.append("plan_steps_open_decisions=" + ", ".join(summary["open_decisions"]))
    return lines


def read_payload(value: str) -> dict[str, object]:
    raw = sys.stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise PlanStepError(f"payload is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise PlanStepError("payload must be a JSON object")
    return payload

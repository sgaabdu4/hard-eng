#!/usr/bin/env python3
"""Machine-checked build method: edges, green, review, and verify records per slice, bound to the tree."""

from __future__ import annotations

import hashlib
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
    load_receipt,
    plan_id,
    receipt_path,
    safe_receipt_json,
    utc_now,
    utc_text,
)
from review_packet import digest, packet_path, verify_packet_path
from safe_plan_io import SafePlanIOError, repository_artifact

sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "e2e" / "scripts"))
from visual_evidence import EvidenceError as MediaError
from visual_evidence import probe_media

RECEIPT_NAME = "build-steps.json"
SCHEMA_VERSION = 1
STEPS = ("edges", "green", "review", "verify")
FULL = "full"
MAX_REVIEW_ROUNDS = 3
FINDING_STATUSES = ("open", "fixed", "rejected", "replan")
VERIFY_MODES = ("ui", "logic")
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
VIDEO_SUFFIXES = frozenset({".mp4", ".webm", ".mov"})
SLICE_ID = re.compile(r"^S-[1-9][0-9]*$")
COMPLETED_ROW = re.compile(r"(?m)^- completed_slices = (.+)$")
PLACEHOLDERS = frozenset({"tbd", "todo", "tba", "n/a", "?"})


class BuildStepError(Exception):
    """Invalid build-step receipt or payload."""


def _text(payload: dict[str, object], key: str, *, label: str = "") -> str:
    value = payload.get(key)
    where = f"{label}." if label else ""
    if not isinstance(value, str) or not value.strip():
        raise BuildStepError(f"{where}{key} must be a nonempty string")
    if value.strip().lower() in PLACEHOLDERS:
        raise BuildStepError(f"{where}{key} is a placeholder, not an answer: {value.strip()}")
    return value.strip()


def _rows(payload: dict[str, object], key: str, *, allow_empty: bool = False) -> list[dict[str, object]]:
    value = payload.get(key)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise BuildStepError(f"{key} must be a list of objects")
    if not value and not allow_empty:
        raise BuildStepError(f"{key} must not be empty")
    return list(value)


def _unknown_keys(payload: dict[str, object], allowed: tuple[str, ...], label: str) -> None:
    extra = sorted(key for key in payload if key not in allowed)
    if extra:
        raise BuildStepError(f"{label} has unknown keys: {', '.join(extra)}")


def validate_edges(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    _unknown_keys(payload, ("cases",), "edges")
    cases: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in _rows(payload, "cases"):
        _unknown_keys(row, ("name", "success_test", "failure_test"), "edge case")
        name = _text(row, "name", label="edge case")
        if name in seen:
            raise BuildStepError(f"edge case listed twice: {name}")
        seen.add(name)
        for key in ("success_test", "failure_test"):
            if not isinstance(row.get(key), str) or not str(row[key]).strip():
                raise BuildStepError(f"edge case {name} lacks its {key} id")
        cases.append(
            {
                "name": name,
                "success_test": str(row["success_test"]).strip(),
                "failure_test": str(row["failure_test"]).strip(),
            }
        )
    return {"cases": cases}


def validate_green(repo: Path, payload: dict[str, object]) -> dict[str, object]:
    _unknown_keys(payload, ("command", "exit"), "green")
    command = payload.get("command")
    if isinstance(command, str):
        command = command.split()
    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item for item in command):
        raise BuildStepError("green.command must be the exact command as a nonempty list of strings")
    if payload.get("exit") != 0:
        raise BuildStepError(f"green requires exit 0, got {payload.get('exit')!r}")
    return {"command": list(command), "exit": 0}


def _finding(row: dict[str, object], round_number: int) -> dict[str, str]:
    _unknown_keys(row, ("id", "text", "status", "reason"), f"round {round_number} finding")
    identifier = _text(row, "id", label=f"round {round_number} finding")
    status = _text(row, "status", label=f"finding {identifier}")
    if status not in FINDING_STATUSES:
        raise BuildStepError(f"finding {identifier} status must be one of {', '.join(FINDING_STATUSES)}")
    entry = {"id": identifier, "text": _text(row, "text", label=f"finding {identifier}"), "status": status}
    if status == "rejected":
        entry["reason"] = _text(row, "reason", label=f"rejected finding {identifier}")
    return entry


def validate_review(repo: Path, payload: dict[str, object], plan: Path, name: str) -> dict[str, object]:
    _unknown_keys(payload, ("rounds",), "review")
    rounds: list[dict[str, object]] = []
    rows = _rows(payload, "rounds")
    if len(rows) > MAX_REVIEW_ROUNDS:
        raise BuildStepError(f"review allows at most {MAX_REVIEW_ROUNDS} rounds; round {len(rows)} needs the user")
    for index, row in enumerate(rows, start=1):
        _unknown_keys(row, ("reviewer", "packet_sha256", "findings"), f"round {index}")
        packet = packet_path(plan, name, index)
        expected = digest(packet)
        if expected is None:
            raise BuildStepError(f"round {index} has no packet; run plan_state.py review-packet --slice {name} first")
        if row.get("packet_sha256") != expected:
            raise BuildStepError(f"round {index} packet_sha256 does not match {packet.name}")
        findings = [_finding(item, index) for item in _rows(row, "findings", allow_empty=True)]
        rounds.append(
            {
                "round": index,
                "reviewer": _text(row, "reviewer", label=f"round {index}"),
                "packet_sha256": expected,
                "findings": findings,
            }
        )
    return {"rounds": rounds}


def open_findings(entry: dict[str, object]) -> list[str]:
    rounds = entry.get("rounds")
    if not isinstance(rounds, list) or not rounds:
        return []
    last = rounds[-1]
    findings = last.get("findings", []) if isinstance(last, dict) else []
    return [
        f"{item['id']}: {item['text']}" for item in findings if isinstance(item, dict) and item.get("status") == "open"
    ]


def _evidence_matches_mode(target: Path, relative: str, mode: str) -> None:
    if target.suffix.lower() in VIDEO_SUFFIXES:
        try:
            probe_media(target, "video")
        except MediaError as error:
            raise BuildStepError(f"walkthrough video is not decodable: {relative}: {error}") from error
        return
    if mode == "ui":
        if target.suffix.lower() not in IMAGE_SUFFIXES:
            raise BuildStepError(f"ui evidence must be a screenshot image: {relative}")
        try:
            probe_media(target, "image")
        except MediaError as error:
            raise BuildStepError(f"ui evidence is not a decodable image: {relative}: {error}") from error
        return
    if target.suffix.lower() != ".json":
        raise BuildStepError(f"logic evidence must be recorded input/output JSON: {relative}")
    try:
        json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BuildStepError(f"logic evidence is not valid JSON: {relative}") from error


def _hashed_paths(repo: Path, payload: dict[str, object], key: str, mode: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in _rows(payload, key):
        _unknown_keys(row, ("path", "sha256"), f"{key} evidence")
        relative = _text(row, "path", label=key)
        target = repo / relative
        if not target.is_file():
            raise BuildStepError(f"{key} evidence file is missing: {relative}")
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if row.get("sha256") != digest:
            raise BuildStepError(f"{key} evidence hash does not match the file: {relative}")
        _evidence_matches_mode(target, relative, mode)
        rows.append({"path": relative, "sha256": digest})
    return rows


def validate_verify(repo: Path, payload: dict[str, object], plan: Path, name: str) -> dict[str, object]:
    keys = ("mode", "packet_sha256", "fakes", "outside_calls", "before", "after", "edge_cases")
    _unknown_keys(payload, keys, "verify")
    mode = _text(payload, "mode")
    if mode not in VERIFY_MODES:
        raise BuildStepError(f"verify.mode must be one of {', '.join(VERIFY_MODES)}")
    packet = verify_packet_path(plan, name)
    expected = digest(packet)
    if expected is None:
        raise BuildStepError(f"verify has no packet; run plan_state.py verify-packet --slice {name} first")
    if payload.get("packet_sha256") != expected:
        raise BuildStepError(f"verify packet_sha256 does not match {packet.name}")
    fakes: list[dict[str, str]] = []
    for row in _rows(payload, "fakes", allow_empty=True):
        _unknown_keys(row, ("host", "log"), "fake")
        log = _text(row, "log", label="fake")
        if not (repo / log).is_file():
            raise BuildStepError(f"fake log is missing: {log}")
        fakes.append({"host": _text(row, "host", label="fake"), "log": log})
    faked = {item["host"] for item in fakes}
    calls = payload.get("outside_calls", [])
    if not isinstance(calls, list) or any(not isinstance(item, str) for item in calls):
        raise BuildStepError("verify.outside_calls must be a list of host names")
    real = sorted(host for host in calls if host not in faked)
    if real:
        raise BuildStepError(f"verify saw a real outside call to {real[0]}; every outside host needs a fake")
    edge_cases = payload.get("edge_cases", [])
    if not isinstance(edge_cases, list) or any(not isinstance(item, str) or not item.strip() for item in edge_cases):
        raise BuildStepError("verify.edge_cases must be a list of edge case names")
    return {
        "mode": mode,
        "packet_sha256": expected,
        "fakes": fakes,
        "outside_calls": sorted(str(item) for item in calls),
        "before": _hashed_paths(repo, payload, "before", mode),
        "after": _hashed_paths(repo, payload, "after", mode),
        "edge_cases": [item.strip() for item in edge_cases],
    }


VALIDATORS = {"edges": validate_edges, "green": validate_green}
BOUND_VALIDATORS = {"review": validate_review, "verify": validate_verify}


def load(repo: Path, plan: Path) -> dict[str, object]:
    path = receipt_path(plan, RECEIPT_NAME)
    if not path.is_file() or path.is_symlink():
        return {"schema_version": SCHEMA_VERSION, "plan_id": plan_id(plan), "slices": {}}
    try:
        value, _, _ = load_receipt(repo, plan, RECEIPT_NAME)
    except EvidenceError as error:
        raise BuildStepError(str(error)) from error
    if value.get("schema_version") != SCHEMA_VERSION or value.get("plan_id") != plan_id(plan):
        raise BuildStepError("build-steps receipt does not belong to this Feature Brief")
    if not isinstance(value.get("slices"), dict):
        raise BuildStepError("build-steps receipt requires a slices object")
    return value


def _slice_entry(receipt: dict[str, object], name: str) -> dict[str, object]:
    slices = receipt["slices"]
    assert isinstance(slices, dict)
    entry = slices.get(name)
    return dict(entry) if isinstance(entry, dict) else {}


def _unknown_edge_cases(slice_entry: dict[str, object], payload: dict[str, object]) -> list[str]:
    edges = slice_entry.get("edges")
    cases = edges.get("cases") if isinstance(edges, dict) else None
    known = {str(item.get("name")) for item in cases if isinstance(item, dict)} if isinstance(cases, list) else set()
    requested = payload.get("edge_cases")
    if not isinstance(requested, list):
        return []
    return [item for item in requested if isinstance(item, str) and item not in known]


def record(repo: Path, plan: Path, name: str, step: str, payload: dict[str, object]) -> dict[str, object]:
    if step not in STEPS:
        raise BuildStepError(f"step must be one of {', '.join(STEPS)}")
    if name != FULL and not SLICE_ID.fullmatch(name):
        raise BuildStepError("--slice must be S-N or full")
    if name == FULL and step != "verify":
        raise BuildStepError("full accepts only the verify record")
    receipt = load(repo, plan)
    slice_entry = _slice_entry(receipt, name)
    if step == "verify" and name != FULL and (unknown := _unknown_edge_cases(slice_entry, payload)):
        raise BuildStepError(f"verify names an edge case missing from the edges record: {unknown[0]}")
    entry = (
        BOUND_VALIDATORS[step](repo, payload, plan, name)
        if step in BOUND_VALIDATORS
        else VALIDATORS[step](repo, payload)
    )
    entry["recorded_at"] = utc_text(utc_now())
    try:
        entry["artifact"] = repository_artifact(repo)
    except SafePlanIOError as error:
        raise BuildStepError(str(error)) from error
    slice_entry[step] = entry
    slices = receipt["slices"]
    assert isinstance(slices, dict)
    receipt["slices"] = {**slices, name: slice_entry}
    path = receipt_path(plan, RECEIPT_NAME)
    path.parent.mkdir(mode=0o700, exist_ok=True)
    try:
        safe_receipt_json(repo, path, receipt)
    except EvidenceError as error:
        raise BuildStepError(str(error)) from error
    return entry


def completed_slices(plan: Path) -> tuple[str, ...]:
    match = COMPLETED_ROW.search(plan.read_text(encoding="utf-8"))
    value = match.group(1).strip() if match else "none"
    return () if value == "none" else tuple(item.strip() for item in value.split(","))


def slice_error(repo: Path, receipt: dict[str, object], name: str, *, artifact: str | None) -> str | None:
    entry = _slice_entry(receipt, name)
    for step in STEPS:
        record_entry = entry.get(step)
        if not isinstance(record_entry, dict):
            return f"slice {name} has no {step} record (plan_state.py record-build --slice {name} --step {step})"
        if artifact is not None and record_entry.get("artifact") != artifact:
            return f"slice {name} {step} record is stale: the tree changed after it was recorded"
    review = entry.get("review")
    if isinstance(review, dict) and (pending := open_findings(review)):
        return f"slice {name} review still has an open finding: {pending[0]}"
    return None


def gate_error(repo: Path, plan: Path, name: str) -> str | None:
    if not enforcement_configured(repo):
        return None
    try:
        receipt = load(repo, plan)
        artifact = repository_artifact(repo)
    except (BuildStepError, SafePlanIOError, EvidenceError) as error:
        return str(error).replace("\n", " ")
    if name != FULL:
        return slice_error(repo, receipt, name, artifact=artifact)
    for completed in completed_slices(plan):
        if error := slice_error(repo, receipt, completed, artifact=None):
            return error
    verify = _slice_entry(receipt, FULL).get("verify")
    if not isinstance(verify, dict):
        return "full gate has no verify record (plan_state.py record-build --slice full --step verify)"
    if verify.get("artifact") != artifact:
        return "full verify record is stale: the tree changed after it was recorded"
    return None


def edges_of(repo: Path, plan: Path, name: str) -> dict[str, object] | None:
    entry = _slice_entry(load(repo, plan), name).get("edges")
    return entry if isinstance(entry, dict) else None


def next_review_round(repo: Path, plan: Path, name: str) -> int:
    review = _slice_entry(load(repo, plan), name).get("review")
    rounds = review.get("rounds") if isinstance(review, dict) else None
    return (len(rounds) if isinstance(rounds, list) else 0) + 1


def emit_lines(repo: Path, plan: Path, name: str) -> list[str]:
    if not enforcement_configured(repo) or name == "none":
        return []
    try:
        receipt = load(repo, plan)
    except BuildStepError as error:
        return [f"build_steps=invalid: {error}"]
    entry = _slice_entry(receipt, name)
    done = [step for step in STEPS if isinstance(entry.get(step), dict)]
    lines = [f"build_steps={name}:{len(done)}/{len(STEPS)}"]
    missing = [step for step in STEPS if step not in done]
    if missing:
        lines.append("build_steps_missing=" + ", ".join(missing))
    review = entry.get("review")
    if isinstance(review, dict) and (pending := open_findings(review)):
        lines.append("build_steps_open_finding=" + pending[0])
    return lines


def read_payload(value: str) -> dict[str, object]:
    raw = sys.stdin.read() if value == "-" else Path(value).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BuildStepError(f"payload is not valid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise BuildStepError("payload must be a JSON object")
    return payload

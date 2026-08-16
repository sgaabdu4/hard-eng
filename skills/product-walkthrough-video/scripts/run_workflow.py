#!/usr/bin/env python3
"""Validate and run an explicit product-walkthrough phase without shell or retries."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from workflow_boundary import (
    BoundaryError,
    BoundaryPlan,
    digest_file as digest,
    execute_boundary,
    read_json_file as read_json,
    reject_symlink_components,
    validate_boundary,
    write_json_once as write_receipt,
)

sys.dont_write_bytecode = True

PREVIEW_PHASES = ("discovery", "scenario", "storyboard", "capture", "render", "qa")
PRODUCTION_PHASES = (
    "discovery",
    "scenario",
    "storyboard",
    "script-approval",
    "capture",
    "narration",
    "render",
    "qa",
    "review",
)
NARRATION_MODES = {"captions-only", "elevenlabs", "supplied-human"}
SAFETY = {
    "data_source": "synthetic-only",
    "allow_production_data": False,
    "allow_client_pii": False,
    "allow_production_credentials": False,
    "allow_production_mutation": False,
    "allow_external_session_links": False,
    "allow_upload": False,
}
SCENE_FIELDS = {
    "id",
    "coverage_ids",
    "chapter",
    "route_state",
    "target_locator",
    "action",
    "expected_result",
    "duration_seconds",
    "hold_seconds",
    "camera_target",
    "zoom",
    "caption",
    "narration",
    "safety_mode",
}
SECRET_NAME = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)
LEDGER_ROW = re.compile(r"^\|\s*([A-Z][A-Z0-9-]+)\s*\|")
ATTEMPT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
STEP_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HTTP_METHOD = re.compile(r"^[A-Z]{3,12}$")
SHA256 = re.compile(r"^[a-f0-9]{64}$")
FORBIDDEN_FAILURE_MATERIAL = re.compile(
    r"(?:authorization\s*:|set-cookie\s*:|cookie\s*:|bearer\s+[A-Za-z0-9]|(?:api[_-]?key|password|secret|token)\s*[=:]|(?:https?://|/)\S*\?)",
    re.I,
)
FAILURE_FIELDS = {
    "schema_version",
    "attempt_id",
    "phase",
    "status",
    "last_completed_step_id",
    "failing_step_id",
    "error",
    "same_origin_requests",
    "page_errors",
    "console_errors",
    "request_failures",
    "server_logs",
    "cleanup",
    "approach_fingerprint",
    "original_violation",
    "artifacts",
}
MAX_FAILURE_RECEIPT_BYTES = 256 * 1024


class ContractError(ValueError):
    pass


class FailureEvidenceError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def exact_fields(value: Any, fields: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != fields:
        raise FailureEvidenceError(code)
    return value


def bounded_text(value: Any, code: str, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum or "\n" in value or "\r" in value:
        raise FailureEvidenceError(code)
    if FORBIDDEN_FAILURE_MATERIAL.search(value):
        raise FailureEvidenceError("forbidden-material")
    return value


def stable_id(value: Any, code: str) -> str:
    text = bounded_text(value, code, maximum=128)
    if STEP_ID.fullmatch(text) is None:
        raise FailureEvidenceError(code)
    return text


def bounded_list(value: Any, code: str, *, maximum: int) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum:
        raise FailureEvidenceError(code)
    return value


def request_path(value: Any) -> str:
    text = bounded_text(value, "request-path")
    if not text.startswith("/") or "?" in text or "#" in text or "://" in text:
        raise FailureEvidenceError("request-path")
    return text


def validate_failure_events(value: Any, code: str) -> None:
    for raw in bounded_list(value, code, maximum=50):
        event = exact_fields(raw, {"type", "message"}, code)
        bounded_text(event["type"], code, maximum=128)
        bounded_text(event["message"], code)


def validate_failure_receipt(path: Path, context: dict[str, Any], phase_id: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise FailureEvidenceError("missing")
    if path.stat().st_size > MAX_FAILURE_RECEIPT_BYTES:
        raise FailureEvidenceError("oversized")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FailureEvidenceError("unreadable") from exc
    receipt = exact_fields(document, FAILURE_FIELDS, "field-mismatch")
    if receipt["schema_version"] != 1 or receipt["status"] != "fail":
        raise FailureEvidenceError("identity")
    if receipt["attempt_id"] != context["attempt_id"] or receipt["phase"] != phase_id:
        raise FailureEvidenceError("identity")
    last_completed = receipt["last_completed_step_id"]
    if last_completed is not None:
        stable_id(last_completed, "last-completed-step")
    stable_id(receipt["failing_step_id"], "failing-step")
    error = exact_fields(receipt["error"], {"type", "message"}, "error")
    bounded_text(error["type"], "error-type", maximum=128)
    bounded_text(error["message"], "error-message")
    for raw in bounded_list(receipt["same_origin_requests"], "same-origin-requests", maximum=50):
        request = exact_fields(raw, {"method", "path", "status"}, "same-origin-request")
        if not isinstance(request["method"], str) or HTTP_METHOD.fullmatch(request["method"]) is None:
            raise FailureEvidenceError("request-method")
        request_path(request["path"])
        status = request["status"]
        if status is not None and (not isinstance(status, int) or isinstance(status, bool) or not 100 <= status <= 599):
            raise FailureEvidenceError("request-status")
    validate_failure_events(receipt["page_errors"], "page-errors")
    validate_failure_events(receipt["console_errors"], "console-errors")
    for raw in bounded_list(receipt["request_failures"], "request-failures", maximum=50):
        failure = exact_fields(raw, {"method", "path", "type", "message"}, "request-failure")
        if not isinstance(failure["method"], str) or HTTP_METHOD.fullmatch(failure["method"]) is None:
            raise FailureEvidenceError("request-method")
        request_path(failure["path"])
        bounded_text(failure["type"], "request-failure-type", maximum=128)
        bounded_text(failure["message"], "request-failure-message")
    for line in bounded_list(receipt["server_logs"], "server-logs", maximum=20):
        bounded_text(line, "server-log")
    cleanup = bounded_list(receipt["cleanup"], "cleanup", maximum=20)
    if not cleanup:
        raise FailureEvidenceError("cleanup")
    for raw in cleanup:
        item = exact_fields(raw, {"actor", "status"}, "cleanup")
        stable_id(item["actor"], "cleanup-actor")
        if item["status"] not in {"not-started", "closed", "stopped", "failed"}:
            raise FailureEvidenceError("cleanup-status")
    bounded_text(receipt["approach_fingerprint"], "approach-fingerprint")
    bounded_text(receipt["original_violation"], "original-violation")
    artifacts: list[dict[str, Any]] = []
    seen_artifacts: set[Path] = set()
    for raw in bounded_list(receipt["artifacts"], "artifacts", maximum=20):
        item = exact_fields(raw, {"path", "sha256", "bytes"}, "artifact")
        try:
            artifact = require_inside(item["path"], context["artifact_root"], "failure artifact")
        except ContractError as exc:
            raise FailureEvidenceError("artifact-path") from exc
        if artifact.is_symlink() or not artifact.is_file() or artifact in seen_artifacts:
            raise FailureEvidenceError("artifact-path")
        seen_artifacts.add(artifact)
        if not isinstance(item["sha256"], str) or SHA256.fullmatch(item["sha256"]) is None:
            raise FailureEvidenceError("artifact-sha256")
        if not isinstance(item["bytes"], int) or isinstance(item["bytes"], bool) or item["bytes"] < 0:
            raise FailureEvidenceError("artifact-bytes")
        actual_sha256 = digest(artifact)
        actual_bytes = artifact.stat().st_size
        if item["sha256"] != actual_sha256 or item["bytes"] != actual_bytes:
            raise FailureEvidenceError("artifact-mismatch")
        artifacts.append({"path": str(artifact), "sha256": actual_sha256, "bytes": actual_bytes})
    return {
        "status": "valid",
        "path": str(path),
        "sha256": digest(path),
        "bytes": path.stat().st_size,
        "artifacts": artifacts,
    }


def require_inside(raw: Any, owner: Path, field: str, *, must_exist: bool = True) -> Path:
    if not isinstance(raw, str) or not raw:
        raise ContractError(f"{field} must be an absolute path")
    path = Path(raw)
    if not path.is_absolute():
        raise ContractError(f"{field} must be absolute")
    resolved = Path(os.path.abspath(path))
    owner = Path(os.path.abspath(owner))
    try:
        resolved.relative_to(owner)
    except ValueError as exc:
        raise ContractError(f"{field} escapes project root") from exc
    try:
        reject_symlink_components(resolved, include_final=must_exist)
    except BoundaryError as exc:
        raise ContractError(str(exc)) from exc
    if must_exist and not resolved.exists():
        raise ContractError(f"{field} does not exist: {resolved}")
    return resolved


def ledger_ids(path: Path) -> set[str]:
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LEDGER_ROW.match(line)
        if match:
            result.add(match.group(1))
    if not result:
        raise ContractError("coverage ledger has no machine-readable ID rows")
    return result


def validate_scenes(path: Path, required_ids: set[str]) -> tuple[int, set[str]]:
    document = read_json(path)
    if document.get("schema_version") != 1:
        raise ContractError("scene_manifest.schema_version must equal 1")
    scenes = document.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ContractError("scene_manifest.scenes must be a non-empty list")
    scene_ids: set[str] = set()
    covered: set[str] = set()
    for index, raw in enumerate(scenes):
        if not isinstance(raw, dict):
            raise ContractError(f"scene {index} must be an object")
        missing = sorted(SCENE_FIELDS - set(raw))
        extra = sorted(set(raw) - SCENE_FIELDS)
        if missing or extra:
            raise ContractError(f"scene {index} field mismatch missing={missing} extra={extra}")
        scene_id = raw["id"]
        if not isinstance(scene_id, str) or not scene_id or scene_id in scene_ids:
            raise ContractError(f"scene {index} id must be unique and non-empty")
        scene_ids.add(scene_id)
        coverage = raw["coverage_ids"]
        if not isinstance(coverage, list) or not coverage or any(not isinstance(item, str) or not item for item in coverage):
            raise ContractError(f"scene {scene_id} coverage_ids must be non-empty strings")
        covered.update(coverage)
        for field in ("chapter", "route_state", "target_locator", "action", "expected_result", "camera_target", "caption", "narration"):
            if not isinstance(raw[field], str):
                raise ContractError(f"scene {scene_id} {field} must be a string")
        duration = raw["duration_seconds"]
        hold = raw["hold_seconds"]
        zoom = raw["zoom"]
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration <= 0:
            raise ContractError(f"scene {scene_id} duration_seconds must be positive")
        if not isinstance(hold, (int, float)) or isinstance(hold, bool) or hold < 0:
            raise ContractError(f"scene {scene_id} hold_seconds must be non-negative")
        if not isinstance(zoom, (int, float)) or isinstance(zoom, bool) or not 1 <= zoom <= 2.5:
            raise ContractError(f"scene {scene_id} zoom must be from 1 through 2.5")
        if raw["safety_mode"] not in {"synthetic-read-only", "synthetic-intercepted-write"}:
            raise ContractError(f"scene {scene_id} has invalid safety_mode")
    missing_coverage = sorted(required_ids - covered)
    if missing_coverage:
        raise ContractError(f"scene manifest misses required coverage IDs: {missing_coverage}")
    return len(scenes), covered


def validate_job(job_path: Path) -> dict[str, Any]:
    job = read_json(job_path)
    if job.get("schema_version") != 1:
        raise ContractError("job.schema_version must equal 1")
    mode = job.get("mode")
    if mode not in {"preview", "production"}:
        raise ContractError("job.mode must be preview or production")
    project = job.get("project")
    if not isinstance(project, dict) or not isinstance(project.get("name"), str) or not project["name"].strip():
        raise ContractError("project.name must be non-empty")
    root_raw = project.get("root")
    if not isinstance(root_raw, str) or not Path(root_raw).is_absolute():
        raise ContractError("project.root must be absolute")
    root = Path(os.path.abspath(root_raw))
    reject_symlink_components(root)
    if not root.is_dir():
        raise ContractError("project.root must exist")
    artifacts = job.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ContractError("artifacts must be an object")
    artifact_root = require_inside(artifacts.get("root"), root, "artifacts.root", must_exist=False)
    receipts = require_inside(artifacts.get("receipts"), artifact_root, "artifacts.receipts", must_exist=False)
    attempt_id = artifact_root.name
    if ATTEMPT_ID.fullmatch(attempt_id) is None:
        raise ContractError("artifacts.root basename must be a stable attempt ID")
    ledger = require_inside(job.get("coverage_ledger"), root, "coverage_ledger")
    scene_manifest = require_inside(job.get("scene_manifest"), root, "scene_manifest")
    required_raw = job.get("required_coverage_ids")
    if not isinstance(required_raw, list) or not required_raw or any(not isinstance(item, str) or not item for item in required_raw):
        raise ContractError("required_coverage_ids must be non-empty strings")
    if len(required_raw) != len(set(required_raw)):
        raise ContractError("required_coverage_ids must be unique")
    required = set(required_raw)
    absent = sorted(required - ledger_ids(ledger))
    if absent:
        raise ContractError(f"required coverage IDs absent from ledger: {absent}")
    scene_count, covered = validate_scenes(scene_manifest, required)
    narration = job.get("narration")
    if not isinstance(narration, dict) or narration.get("mode") not in NARRATION_MODES:
        raise ContractError("narration.mode is invalid")
    if job.get("safety") != SAFETY:
        raise ContractError("safety must equal the zero-production-data/zero-client-PII contract")
    phases = job.get("phases")
    phase_order = PREVIEW_PHASES if mode == "preview" else PRODUCTION_PHASES
    if not isinstance(phases, dict) or set(phases) != set(phase_order):
        raise ContractError(f"phases must equal {list(phase_order)}")
    boundary_plans: dict[str, BoundaryPlan] = {}
    phase_fields = {
        "argument_schema",
        "argv",
        "containment",
        "cwd",
        "endpoints",
        "evidence",
        "executable_sha256",
        "external_effect",
        "timeout_seconds",
    }
    for phase_id in phase_order:
        phase = phases[phase_id]
        if not isinstance(phase, dict):
            raise ContractError(f"phase {phase_id} must be an object")
        if set(phase) != phase_fields:
            raise ContractError(f"phase {phase_id} fields do not match the execution contract")
        effect = phase.get("external_effect")
        expected_effect = "paid" if phase_id == "narration" and narration["mode"] == "elevenlabs" else "none"
        if effect != expected_effect:
            raise ContractError(f"phase {phase_id} external_effect must be {expected_effect}")
        argv = phase["argv"]
        if any(isinstance(item, str) and SECRET_NAME.search(item) for item in argv):
            raise ContractError(f"phase {phase_id} argv may not contain secret-bearing names")
        try:
            boundary_plans[phase_id] = validate_boundary(
                phase_id,
                phase,
                root=root,
                artifact_root=artifact_root,
                job_path=job_path,
            )
        except BoundaryError as exc:
            raise ContractError(str(exc)) from exc
        evidence = phase.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise ContractError(f"phase {phase_id} evidence must be non-empty")
        for index, raw in enumerate(evidence):
            require_inside(raw, root, f"phase {phase_id} evidence[{index}]", must_exist=False)
        timeout = phase.get("timeout_seconds")
        if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 1800:
            raise ContractError(f"phase {phase_id} timeout_seconds must be 1..1800")
    return {
        "job": job,
        "job_path": job_path.resolve(),
        "job_sha256": digest(job_path),
        "root": root,
        "artifact_root": artifact_root,
        "attempt_id": attempt_id,
        "receipts": receipts,
        "ledger": ledger,
        "scene_manifest": scene_manifest,
        "scene_count": scene_count,
        "covered": covered,
        "phase_order": phase_order,
        "boundary_plans": boundary_plans,
    }


def prior_receipts(context: dict[str, Any], phase_id: str) -> None:
    order = context["phase_order"]
    index = order.index(phase_id)
    for prior in order[:index]:
        path = context["receipts"] / f"{prior}.json"
        if not path.is_file():
            raise ContractError(f"missing prior phase receipt: {prior}")
        receipt = read_json(path)
        if receipt.get("status") != "pass" or receipt.get("job_sha256") != context["job_sha256"]:
            raise ContractError(f"stale or failed prior phase receipt: {prior}")
        receipt_attempt = receipt.get("attempt_id")
        if receipt_attempt is not None and receipt_attempt != context["attempt_id"]:
            raise ContractError(f"prior phase receipt belongs to another attempt: {prior}")


def paid_approval(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    receipt = read_json(path)
    required = {"status", "job_sha256", "script_sha256", "settings_sha256", "characters", "impact", "user_reply"}
    if not required.issubset(receipt):
        raise ContractError("paid approval receipt is incomplete")
    if receipt["status"] != "approved" or receipt["job_sha256"] != context["job_sha256"]:
        raise ContractError("paid approval receipt is stale or unapproved")
    if not isinstance(receipt["characters"], int) or receipt["characters"] < 0:
        raise ContractError("paid approval characters must be non-negative")
    return {key: receipt[key] for key in sorted(required - {"user_reply"})}


def bind_attempt(context: dict[str, Any]) -> tuple[Path, str]:
    path = context["artifact_root"] / "attempt.json"
    expected = {
        "schema_version": 1,
        "attempt_id": context["attempt_id"],
        "artifact_root": str(context["artifact_root"]),
        "job_path": str(context["job_path"]),
        "job_sha256": context["job_sha256"],
    }
    if path.exists():
        if path.is_symlink():
            raise ContractError("attempt binding may not be a symlink")
        if read_json(path) != expected:
            raise ContractError("attempt root is already bound to another job")
        return path, digest(path)
    if context["receipts"].is_dir():
        for receipt_path in sorted(context["receipts"].glob("*.json")):
            if receipt_path.is_symlink():
                raise ContractError("attempt receipt may not be a symlink")
            receipt = read_json(receipt_path)
            if receipt.get("job_sha256") != context["job_sha256"]:
                raise ContractError("attempt root contains a receipt for another job")
            receipt_attempt = receipt.get("attempt_id")
            if receipt_attempt is not None and receipt_attempt != context["attempt_id"]:
                raise ContractError("attempt root contains a receipt for another attempt")
    write_receipt(path, expected)
    return path, digest(path)


def failure_summary(path: Path, context: dict[str, Any], phase_id: str) -> dict[str, Any]:
    try:
        return validate_failure_receipt(path, context, phase_id)
    except FailureEvidenceError as exc:
        result: dict[str, Any] = {"status": "missing" if exc.code == "missing" else "invalid", "path": str(path)}
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_FAILURE_RECEIPT_BYTES:
            result.update({"sha256": digest(path), "bytes": path.stat().st_size})
        if exc.code != "missing":
            result["reason"] = exc.code
        return result


def persist_runner_failure(
    path: Path,
    context: dict[str, Any],
    phase_id: str,
    actor_exit_code: int | None,
    runner_failure: str | None,
) -> None:
    if actor_exit_code is not None and actor_exit_code != 0:
        error_type = "ActorExit"
        error_message = f"phase actor exited {actor_exit_code} without actor-owned failure evidence"
        failing_step = f"{phase_id}.actor"
        cleanup_status = "closed"
    elif runner_failure == "timeout":
        error_type = "ActorTimeout"
        error_message = "phase actor timed out without actor-owned failure evidence"
        failing_step = f"{phase_id}.actor"
        cleanup_status = "failed"
    elif runner_failure == "launch-error":
        error_type = "ActorLaunch"
        error_message = "phase actor could not launch"
        failing_step = f"{phase_id}.actor"
        cleanup_status = "not-started"
    else:
        error_type = "RunnerEvidence"
        error_message = "phase actor exited without the declared success evidence"
        failing_step = f"{phase_id}.evidence"
        cleanup_status = "closed"
    write_receipt(
        path,
        {
            "schema_version": 1,
            "attempt_id": context["attempt_id"],
            "phase": phase_id,
            "status": "fail",
            "last_completed_step_id": None,
            "failing_step_id": failing_step,
            "error": {"type": error_type, "message": error_message},
            "same_origin_requests": [],
            "page_errors": [],
            "console_errors": [],
            "request_failures": [],
            "server_logs": [],
            "cleanup": [{"actor": "phase-actor", "status": cleanup_status}],
            "approach_fingerprint": f"declared {phase_id} phase actor + product-walkthrough runner",
            "original_violation": "phase did not produce valid declared evidence",
            "artifacts": [],
        },
    )


def run_phase(context: dict[str, Any], phase_id: str, approval_path: Path | None) -> Path:
    if phase_id not in context["phase_order"]:
        raise ContractError(f"phase {phase_id} is not valid for mode {context['job']['mode']}")
    receipt_path = context["receipts"] / f"{phase_id}.json"
    if receipt_path.exists():
        raise ContractError(f"phase receipt is immutable; use a new attempt root: {phase_id}")
    prior_receipts(context, phase_id)
    binding_path, binding_sha256 = bind_attempt(context)
    failure_path = context["artifact_root"] / f"{phase_id}-failure.json"
    if failure_path.exists():
        raise ContractError(f"failure receipt already exists; use a new attempt root: {phase_id}")
    phase = context["job"]["phases"][phase_id]
    approval_summary: dict[str, Any] | None = None
    if phase["external_effect"] == "paid":
        if approval_path is None:
            raise ContractError("paid narration requires --paid-approval-receipt")
        approval_summary = paid_approval(approval_path, context)
    started = time.time()
    runner_failure: str | None = None
    boundary_evidence: dict[str, Any] | None = None
    try:
        result, boundary_evidence = execute_boundary(
            context["boundary_plans"][phase_id], phase["timeout_seconds"]
        )
        actor_exit_code: int | None = result.returncode
        exit_code = actor_exit_code
        if result.returncode == 124:
            runner_failure = "timeout"
            actor_exit_code = None
        elif not result.terminal:
            runner_failure = "process-group-not-terminal"
            actor_exit_code = None
        elif result.stdout_truncated or result.stderr_truncated:
            runner_failure = "output-limit"
            actor_exit_code = None
    except BoundaryError:
        actor_exit_code = None
        exit_code = 126
        runner_failure = "execution-boundary"
    except OSError:
        actor_exit_code = None
        exit_code = 126
        runner_failure = "launch-error"
    evidence: list[dict[str, Any]] = []
    failure_evidence: dict[str, Any] | None = None
    if exit_code == 0:
        if failure_path.exists():
            exit_code = 65
            runner_failure = "unexpected-failure-evidence"
            failure_evidence = failure_summary(failure_path, context, phase_id)
        else:
            for raw in phase["evidence"]:
                path = Path(raw)
                if not path.is_file():
                    exit_code = 65
                    runner_failure = "missing-success-evidence"
                    evidence = []
                    break
                evidence.append({"path": str(path), "sha256": digest(path), "bytes": path.stat().st_size})
    if exit_code != 0:
        if not failure_path.exists():
            persist_runner_failure(failure_path, context, phase_id, actor_exit_code, runner_failure)
        failure_evidence = failure_summary(failure_path, context, phase_id)
    receipt = {
        "schema_version": 1,
        "skill": "product-walkthrough-video",
        "invocation": f"product-walkthrough-video --job {context['job_path']} --phase {phase_id}",
        "job_path": str(context["job_path"]),
        "job_sha256": context["job_sha256"],
        "attempt_id": context["attempt_id"],
        "attempt_root": str(context["artifact_root"]),
        "attempt_binding": {"path": str(binding_path), "sha256": binding_sha256},
        "mode": context["job"]["mode"],
        "phase": phase_id,
        "external_effect": phase["external_effect"],
        "started_unix": started,
        "finished_unix": time.time(),
        "actor_exit_code": actor_exit_code,
        "exit_code": exit_code,
        "status": "pass" if exit_code == 0 else "fail",
        "runner_failure": runner_failure,
        "safety_declaration": SAFETY,
        "execution_boundary": boundary_evidence,
        "evidence": evidence,
        "failure_evidence": failure_evidence,
        "paid_approval": approval_summary,
    }
    write_receipt(receipt_path, receipt)
    if exit_code != 0:
        failure_status = None if failure_evidence is None else failure_evidence.get("status")
        if actor_exit_code == 0 and runner_failure == "unexpected-failure-evidence":
            failure_clause = "; unexpected failure receipt produced after successful actor exit"
        elif actor_exit_code == 0:
            failure_clause = ""
        elif failure_status == "valid":
            failure_clause = "; sanitized failure receipt captured"
        elif failure_status == "invalid":
            failure_clause = "; required sanitized failure receipt invalid"
        else:
            failure_clause = "; required sanitized failure receipt missing"
        suffix = "; paid retry authority ended" if phase["external_effect"] == "paid" else "; automatic retry disabled"
        runner_clause = "" if runner_failure is None else f"; runner_failure={runner_failure}"
        raise ContractError(f"phase {phase_id} failed with exit {exit_code}{runner_clause}{failure_clause}{suffix}")
    return receipt_path


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--job", required=True, type=Path)
    run = commands.add_parser("run")
    run.add_argument("--job", required=True, type=Path)
    run.add_argument("--phase", required=True)
    run.add_argument("--paid-approval-receipt", type=Path)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        context = validate_job(Path(os.path.abspath(args.job)))
        if args.command == "validate":
            print(
                json.dumps(
                    {
                        "result": "PASS",
                        "skill": "product-walkthrough-video",
                        "job": str(context["job_path"]),
                        "job_sha256": context["job_sha256"],
                        "attempt_id": context["attempt_id"],
                        "mode": context["job"]["mode"],
                        "scenes": context["scene_count"],
                        "required_coverage_ids": sorted(context["job"]["required_coverage_ids"]),
                        "safety_declaration": SAFETY,
                        "containment": {
                            phase: context["boundary_plans"][phase].mode
                            for phase in context["phase_order"]
                        },
                    },
                    sort_keys=True,
                )
            )
            return 0
        receipt = run_phase(context, args.phase, args.paid_approval_receipt)
        print(f"result=PASS receipt={receipt}")
        return 0
    except (BoundaryError, ContractError, OSError, subprocess.SubprocessError) as exc:
        print(f"product-walkthrough-video: FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

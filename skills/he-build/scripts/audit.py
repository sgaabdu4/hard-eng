#!/usr/bin/env python3
"""Run one exact-snapshot, read-only Codex final audit for Hard Eng build."""
from __future__ import annotations
import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
SCRIPT_DIR = Path(__file__).resolve().parent
AGENTS_ROOT = SCRIPT_DIR.parents[2]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
STATE_SCRIPT_DIR = SCRIPT_DIR.parents[1] / "he/scripts"
if str(STATE_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(STATE_SCRIPT_DIR))
from audit_contract import (  # noqa: E402
    PLAN_PATH,
    AuditError,
    RetryableAuditError,
    finding_issue,
    output_schema,
    parse_usage,
    validate_result,
)
from audit_admission import (  # noqa: E402
    ADMISSION_MAX_PACKET_BYTES,
    ADMISSION_MAX_RELATED_BYTES,
    ADMISSION_MAX_RELATED_SECTIONS,
    error_detail as admission_error_detail,
    evaluate_admission,
    evaluate_estimate,
    parse_planned_manifests,
    parse_planned_paths,
)
import admission_cache  # noqa: E402
from audit_candidate import (  # noqa: E402
    CandidateError,
    candidate_binding,
    load_patch,
    materialized_candidate,
)
from audit_result import (  # noqa: E402
    aggregate_audit_results,
    audit_prompt,
    bounded_timeout,
    load_audit_result,
    one_infrastructure_retry,
)
from audit_runtime import (  # noqa: E402
    MAX_AUDIT_WORKERS,
    audit_performance_metrics,
    common_prefix_bytes,
    file_digest,
    isolated_environment,
    require_unchanged_file,
    require_unchanged_snapshot,
    set_workspace_writable,
    warm_then_parallel,
)
from audit_entry import validate_audit_entry, validate_audit_state  # noqa: E402
from audit_packet import (  # noqa: E402
    ReviewScopeOverflow,
    add_required_related_context as append_required_related_context,
    changed_paths,
    git,
    partition_review_scopes,
    plan_base_sha,
    repository_root,
    review_packet as build_review_packet,
    review_packet_parts,
    snapshot_id,
)
from generated_evidence import GeneratedEvidenceError  # noqa: E402
from related_context import MAX_BYTES as FINAL_RELATED_BYTES  # noqa: E402
from related_context import MAX_SECTIONS as FINAL_RELATED_SECTIONS  # noqa: E402
from related_context import related_context  # noqa: E402,F401
from repository_index import RepositoryIndex, repository_source_index  # noqa: E402
from repository_snapshot import artifact_id as repository_artifact_id  # noqa: E402
from plan_contract import PlanStateError  # noqa: E402
from plan_approval import validate_approval_receipt  # noqa: E402
from plan_state import validate_document  # noqa: E402
from secret_scanner import secret_marker, sensitive_path  # noqa: E402
MAX_PACKET_BYTES = 800 * 1024
MAX_TOOL_CALLS = 0
DEFAULT_TIMEOUT = 600
TOOL_IDLE_TIMEOUT = 180
SYNTHESIS_IDLE_TIMEOUT = 360
HEARTBEAT_SECONDS = 30
ALLOWED_ITEM_TYPES = {"agent_message", "reasoning", "error"}
ITEM_EVENTS = {"item.started", "item.updated", "item.completed"}
DISABLED_TOOL_FEATURES = (
    "apps", "auth_elicitation", "browser_use", "browser_use_external", "browser_use_full_cdp_access",
    "code_mode_host", "computer_use", "default_mode_request_user_input", "goals", "hooks", "image_generation",
    "in_app_browser", "multi_agent", "plugins", "remote_plugin", "request_permissions_tool", "shell_tool",
    "skill_mcp_dependency_install", "tool_call_mcp_elicitation", "tool_suggest", "unified_exec", "workspace_dependencies",
)
def add_required_related_context(sections, context, max_packet_bytes: int | None = None) -> None:
    limit = MAX_PACKET_BYTES if max_packet_bytes is None else max_packet_bytes
    append_required_related_context(sections, context, limit)
def review_packet(repo: Path, plan: Path, *, max_packet_bytes: int | None = None) -> str:
    limit = MAX_PACKET_BYTES if max_packet_bytes is None else max_packet_bytes
    return build_review_packet(repo, plan, max_packet_bytes=limit)
def require_estimate_plan_state(root: Path, plan: Path, unit_id: str | None = None) -> dict[str, str]:
    try:
        state = validate_document(plan, plan.read_text(encoding="utf-8"))
        validate_approval_receipt(root, state)
    except PlanStateError as exc:
        raise AuditError(f"invalid PLAN state: {exc}") from exc
    head = git(root, "rev-parse", "HEAD").decode("ascii").strip()
    if state["repository_root"] != str(root) or state["head_sha"] != head:
        raise AuditError("invalid PLAN state: repository identity mismatch")
    approved = set() if state["approved_plan_stages"] == "none" else set(
        state["approved_plan_stages"].split(",")
    )
    proposed_slices = (
        state["lifecycle_status"] == "planning"
        and state["current_stage"] == "plan"
        and state["plan_stage"] == "slices"
        and state["slice_count"] == "none"
    )
    accepted_slices = (
        state["lifecycle_status"] in {"planning", "build-ready"}
        and "slices" in approved
        and state["slice_count"] != "none"
    )
    if not (proposed_slices or accepted_slices):
        raise AuditError("invalid PLAN state: estimate requires proposed or accepted slices")
    if state["slice_count"] != "none" and unit_id is not None:
        try:
            number = int(unit_id.removeprefix("S-"))
        except ValueError as exc:
            raise AuditError("invalid manifest: estimate unit is not a slice") from exc
        if number < 1 or number > int(state["slice_count"]):
            raise AuditError("invalid manifest: estimate unit exceeds accepted slice count")
    return state
def estimate_unit_report(
    root: Path, plan: Path, unit_id: str, planned: tuple[str, ...], snapshot: str,
    base: str, repository_index: RepositoryIndex | None = None,
) -> dict:
    unresolved = tuple(path for path in planned if not (root / path).exists())
    try:
        scopes = partition_review_scopes(
            root, plan, planned, max_related_sections=ADMISSION_MAX_RELATED_SECTIONS,
            max_related_bytes=ADMISSION_MAX_RELATED_BYTES,
            max_packet_bytes=ADMISSION_MAX_PACKET_BYTES, full_files=True,
            planned_unit_id=unit_id, repository_index=repository_index,
        )
        scope = max(scopes, key=lambda value: value.packet_bytes)
    except ReviewScopeOverflow as exc:
        scopes, scope = (), exc.scope
    require_unchanged_snapshot(root, snapshot)
    report = evaluate_estimate(
        base_snapshot_id=snapshot, base_sha=base, unit_id=unit_id,
        planned_paths=planned, unresolved_paths=unresolved, related_units=scope.related_units,
        packet_units=scope.packet_units, related_bytes_override=scope.related_bytes,
    )
    report["relatedContext"]["sections"] = scope.related_sections
    report["packet"]["bytes"] = scope.packet_bytes
    report["reviewShardCount"] = len(scopes) if scopes else 0
    return report
def estimate_admission_report(repo: Path, plan: Path, unit_id: str) -> dict:
    root = repository_root(repo.expanduser().resolve())
    resolved_plan = resolve_plan(root, plan.expanduser())
    require_estimate_plan_state(root, resolved_plan, unit_id)
    try:
        planned = parse_planned_paths(resolved_plan, unit_id, root, sensitive_path)
    except ValueError as exc:
        raise AuditError(f"invalid manifest: {exc}") from exc
    return estimate_unit_report(
        root, resolved_plan, unit_id, planned, snapshot_id(root),
        plan_base_sha(root, resolved_plan),
    )
def estimate_plan_reports(repo: Path, plan: Path):
    root = repository_root(repo.expanduser().resolve())
    resolved_plan = resolve_plan(root, plan.expanduser())
    state = require_estimate_plan_state(root, resolved_plan)
    try:
        manifests = parse_planned_manifests(resolved_plan, root, sensitive_path)
    except ValueError as exc:
        raise AuditError(f"invalid manifest: {exc}") from exc
    expected = tuple(f"S-{number}" for number in range(1, len(manifests) + 1))
    if tuple(unit_id for unit_id, _ in manifests) != expected:
        raise AuditError("invalid manifest: slice IDs must be contiguous and ordered")
    if state["slice_count"] != "none" and int(state["slice_count"]) != len(manifests):
        raise AuditError("invalid manifest: accepted slice count mismatch")
    snapshot = snapshot_id(root)
    base = plan_base_sha(root, resolved_plan)
    index = repository_source_index(root)
    for unit_id, planned in manifests:
        try:
            report = estimate_unit_report(
                root, resolved_plan, unit_id, planned, snapshot, base, index,
            )
        except (AuditError, GeneratedEvidenceError, OSError, UnicodeError) as exc:
            report = estimate_error_report(exc, unit_id)
        yield report
def estimate_error_report(error: Exception | str, unit_id: str | None = None) -> dict:
    detail = admission_error_detail(error)
    return {"mode": "estimate", "result": "fail", "baseSnapshotId": None, "baseSha": None,
            "unitId": unit_id, "plannedPathCount": None, "unresolvedPlannedPaths": [],
            "relatedContext": None, "packet": None, "largestUnits": [], "reviewShardCount": 0,
            "error": detail}
def candidate_admission_report(repo: Path, plan: Path, patch_bytes: bytes, unit_id: str) -> dict:
    root = repository_root(repo.expanduser().resolve())
    resolved_plan = resolve_plan(root, plan.expanduser())
    source_snapshot = snapshot_id(root)
    base_sha = git(root, "rev-parse", "HEAD").decode("ascii").strip()
    plan_bytes = resolved_plan.read_bytes()
    try:
        state = validate_document(resolved_plan, plan_bytes.decode("utf-8"))
        validate_approval_receipt(root, state)
    except PlanStateError as exc:
        raise AuditError(f"invalid PLAN state: {exc}") from exc
    approved = set(state["approved_plan_stages"].split(","))
    if (
        state["repository_root"] != str(root)
        or state["head_sha"] != base_sha
        or state["lifecycle_status"] != "building"
        or state["current_stage"] != "build"
        or state["plan_approved"] != "yes"
        or "slices" not in approved
        or state["active_slice"] != unit_id
        or state["snapshot_id"] != source_snapshot
    ):
        raise AuditError("invalid PLAN state: candidate requires exact active approved build state")
    key = admission_cache.cache_key(
        script_directory=SCRIPT_DIR, source_snapshot=source_snapshot,
        plan_bytes=plan_bytes, patch_bytes=patch_bytes, unit_id=unit_id,
    )
    probe, probe_paths, _ = candidate_binding(
        root, resolved_plan, unit_id, patch_bytes, sensitive=sensitive_path,
    )
    cached = admission_cache.load(root, key)
    if admission_cache.matches(
        cached, unit_id=unit_id, approved_plan_digest=state["approved_plan_digest"],
        completed_slices=probe.completed_slices, changed_path_count=len(probe_paths),
        accumulated_state_digest=probe.accumulated_digest, candidate_state=probe.candidate_state,
        source_snapshot=source_snapshot, patch_digest=admission_cache.digest_bytes(patch_bytes),
    ):
        emit_status("admission-cache-hit", unit=unit_id)
        require_unchanged_snapshot(root, source_snapshot)
        return cached
    with materialized_candidate(
        root, resolved_plan, patch_bytes, unit_id, sensitive=sensitive_path, snapshot_id=snapshot_id
    ) as (
        candidate, candidate_plan, patch_paths, digest, binding
    ):
        candidate_snapshot = snapshot_id(candidate)
        try:
            scopes = partition_review_scopes(
                candidate, candidate_plan, patch_paths,
                max_related_sections=ADMISSION_MAX_RELATED_SECTIONS,
                max_related_bytes=ADMISSION_MAX_RELATED_BYTES,
                max_packet_bytes=ADMISSION_MAX_PACKET_BYTES, full_files=True,
            )
            scope = max(scopes, key=lambda value: value.packet_bytes)
        except ReviewScopeOverflow as exc:
            scopes, scope = (), exc.scope
        base = plan_base_sha(candidate, candidate_plan)
        evaluated = evaluate_admission(
            snapshot_id=candidate_snapshot, base_sha=base_sha,
            changed_path_count=len(patch_paths), related_sections=scope.related_sections,
            related_bytes=scope.related_bytes, packet_bytes=scope.packet_bytes,
            largest_units=scope.packet_units, related_units=scope.related_units,
            packet_units=scope.packet_units,
        )
    require_unchanged_snapshot(root, source_snapshot)
    report = {
        "mode": "candidate", "result": evaluated["result"],
        "unitId": binding.unit_id, "approvedPlanDigest": binding.approved_plan_digest,
        "completedSlices": list(binding.completed_slices),
        "accumulatedPathCount": len(binding.accumulated_paths),
        "accumulatedStateDigest": binding.accumulated_digest,
        "candidateState": binding.candidate_state,
        "preservedWipPathCount": len(binding.preserved_wip_paths),
        "baseSnapshotId": source_snapshot, "baseSha": base_sha,
        "candidateDigest": digest, "candidateSnapshotId": candidate_snapshot,
        "changedPathCount": len(patch_paths), "relatedContext": evaluated["relatedContext"],
        "packet": evaluated["packet"], "largestUnits": evaluated["largestUnits"],
        "reviewShardCount": len(scopes) if scopes else 0, "error": evaluated["error"],
    }
    if report["result"] == "pass":
        try:
            admission_cache.store(root, key, report)
        except (OSError, subprocess.SubprocessError):
            emit_status("admission-cache-unavailable", unit=unit_id)
    return report
def candidate_error_report(error: Exception | str) -> dict:
    return {"mode": "candidate", "result": "fail", "unitId": None,
            "approvedPlanDigest": None,
            "completedSlices": [], "accumulatedPathCount": None, "accumulatedStateDigest": None,
            "candidateState": None, "preservedWipPathCount": None,
            "baseSnapshotId": None, "baseSha": None,
            "candidateDigest": None, "candidateSnapshotId": None, "changedPathCount": None,
            "relatedContext": None, "packet": None, "largestUnits": [], "reviewShardCount": 0,
            "error": admission_error_detail(error)}
@dataclass
class EventState:
    stage: str = "starting"
    action: str = "none"
    tool_calls: int = 0
    completed_items: int = 0
    usage: dict[str, int] | None = None
    forbidden_paths: tuple[str, ...] = ()
def new_event_state(forbidden_paths: tuple[str, ...] = ()) -> EventState:
    return EventState(forbidden_paths=forbidden_paths)
def emit_status(stage: str, **details: object) -> None:
    payload = {"type": "he.audit.status", "stage": stage, **details}
    print(json.dumps(payload, separators=(",", ":"), ensure_ascii=False), file=sys.stderr, flush=True)
def progress(state: EventState) -> None:
    emit_status(
        state.stage,
        action=state.action,
        tool_calls=state.tool_calls,
        tool_budget=MAX_TOOL_CALLS,
        completed_items=state.completed_items,
    )
def consume_event(line: str, state: EventState, emit_progress: bool) -> None:
    try:
        event = json.loads(line)
    except json.JSONDecodeError as exc:
        raise AuditError("codex audit event stream is not valid JSONL") from exc
    if not isinstance(event, dict):
        raise AuditError("codex audit event is invalid")
    event_type = event.get("type")
    item = event.get("item")
    item_type = item.get("type") if isinstance(item, dict) else None
    if event_type in ITEM_EVENTS and item_type == "error":
        state.stage = "transport-recovering"
        if emit_progress:
            progress(state)
        return
    if event_type in ITEM_EVENTS and item_type not in ALLOWED_ITEM_TYPES:
        raise AuditError(f"codex audit emitted unapproved item type: {item_type}")
    if event_type == "thread.started":
        state.stage = "packet-review"
    elif event_type == "item.started":
        state.stage = "synthesizing" if item_type == "agent_message" else "packet-review"
    elif event_type == "item.completed":
        state.completed_items += int(item_type == "agent_message")
        state.stage = "synthesizing" if item_type == "agent_message" else state.stage
    elif event_type == "turn.completed":
        state.usage = parse_usage(event.get("usage"))
        state.stage = "synthesizing"
    if emit_progress and event_type in {"thread.started", "item.started", "item.completed", "turn.completed"}:
        progress(state)
def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
        process.wait(timeout=3)
    except (ProcessLookupError, subprocess.TimeoutExpired):
        if process.poll() is None:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                return
def run_codex_stream(
    command: list[str],
    prompt: str,
    timeout: int,
    environment_overrides: dict[str, str] | None = None,
    forbidden_paths: tuple[str, ...] = (),
) -> tuple[dict[str, int], int]:
    environment = dict(environment_overrides or {})
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        start_new_session=os.name == "posix",
        env=environment,
    )
    if process.stdin is None or process.stdout is None:
        stop_process(process)
        raise AuditError("codex audit stream unavailable")
    selector = selectors.DefaultSelector()
    state = new_event_state(forbidden_paths)
    started = last_event = last_heartbeat = time.monotonic()
    buffered = b""
    progress(state)
    try:
        process.stdin.write(prompt.encode("utf-8"))
        process.stdin.close()
        os.set_blocking(process.stdout.fileno(), False)
        selector.register(process.stdout, selectors.EVENT_READ)
        while True:
            now = time.monotonic()
            elapsed = now - started
            idle = now - last_event
            idle_limit = (
                timeout if state.stage in {"starting", "packet-review"}
                else min(timeout, TOOL_IDLE_TIMEOUT if state.stage == "targeted-inspection" else SYNTHESIS_IDLE_TIMEOUT)
            )
            if elapsed >= timeout:
                error = RetryableAuditError if state.completed_items == 0 else AuditError
                raise error(f"codex audit timed out after {timeout}s")
            if idle >= idle_limit:
                raise AuditError(f"codex audit stalled after {idle_limit}s without event")
            if now - last_heartbeat >= HEARTBEAT_SECONDS:
                emit_status(
                    state.stage,
                    action=state.action,
                    heartbeat=True,
                    elapsed_s=int(elapsed),
                    idle_s=int(idle),
                    tool_calls=state.tool_calls,
                    tool_budget=MAX_TOOL_CALLS,
                    completed_items=state.completed_items,
                )
                last_heartbeat = now
            ready = selector.select(timeout=min(1.0, timeout - elapsed, idle_limit - idle))
            for key, _ in ready:
                while True:
                    try:
                        chunk = os.read(key.fileobj.fileno(), 65536)
                    except BlockingIOError:
                        break
                    if not chunk:
                        selector.unregister(key.fileobj)
                        break
                    buffered += chunk
                while b"\n" in buffered:
                    line, buffered = buffered.split(b"\n", 1)
                    last_event = time.monotonic()
                    try:
                        decoded = line.decode("utf-8")
                    except UnicodeError as exc:
                        raise AuditError("codex audit event stream is not UTF-8") from exc
                    consume_event(decoded, state, emit_progress=True)
            if process.poll() is not None:
                if buffered:
                    raise AuditError("codex audit event stream ended with a partial record")
                break
        if process.returncode != 0:
            raise (RetryableAuditError if state.completed_items == 0 else AuditError)(f"codex audit exited {process.returncode}")
        if state.usage is None:
            raise (RetryableAuditError if state.completed_items == 0 else AuditError)("codex audit produced no usage event")
        return state.usage, state.completed_items
    except BrokenPipeError as exc:
        stop_process(process)
        raise AuditError("codex audit input pipe closed") from exc
    except AuditError:
        stop_process(process)
        raise
    except BaseException:
        stop_process(process)
        raise
    finally:
        selector.close()
        process.stdout.close()
def codex_command(
    repo: Path, schema_path: Path, result_path: Path, denied_paths: tuple[str, ...] = ()
) -> list[str]:
    denied_rules = ", ".join(f"{json.dumps(path)} = \"deny\"" for path in denied_paths)
    denied = ["-c", f"permissions.hard-eng-audit.filesystem={{ {denied_rules} }}"]
    disabled = [argument for feature in DISABLED_TOOL_FEATURES for argument in ("--disable", feature)]
    return [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--strict-config",
        "-c",
        'approval_policy="never"',
        "-c",
        'default_permissions="hard-eng-audit"',
        "-c",
        'permissions.hard-eng-audit.extends=":read-only"',
        *denied,
        *disabled,
        "-c",
        'web_search="disabled"',
        "--model",
        "gpt-5.6-sol",
        "-c",
        'model_reasoning_effort="medium"',
        "--cd",
        str(repo),
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(result_path),
        "--json",
        "--color",
        "never",
        "-",
    ]
def resolve_plan(root: Path, plan_arg: Path) -> Path:
    plan = (plan_arg if plan_arg.is_absolute() else root / plan_arg).resolve()
    try:
        relative = plan.relative_to(root).as_posix()
    except ValueError as exc:
        raise AuditError("PLAN is outside repository") from exc
    if not PLAN_PATH.fullmatch(relative) or not plan.is_file():
        raise AuditError("PLAN must be features/<feature>/PLAN.md")
    return plan
def run_audit_scope(
    *, directory: Path, schema_path: Path, scope, index: int, shard_count: int,
    snapshot: str, plan_token: str, deadline: float,
    controller_codex: Path | None,
) -> tuple[dict[str, int], dict[str, object]]:
    shard_directory = directory / f"shard-{index}"
    shard_directory.mkdir()
    workspace = shard_directory / "workspace"
    workspace.mkdir()
    initialized = subprocess.run(
        ["git", "-C", str(workspace), "init", "-q", "-b", "audit"],
        capture_output=True, check=False,
    )
    if initialized.returncode != 0:
        raise AuditError("cannot initialize empty audit workspace")
    environment, forbidden_paths = isolated_environment(shard_directory, controller_codex)
    result_path = shard_directory / "result.json"
    set_workspace_writable(workspace, False)
    emit_status("shard-starting", shard=index, shards=shard_count)
    try:
        attempt = 0
        def action():
            nonlocal attempt
            attempt += 1
            result_path.unlink(missing_ok=True)
            requested = max(1, int(deadline - time.monotonic()))
            usage, completed_items = run_codex_stream(
                codex_command(workspace, schema_path, result_path, forbidden_paths),
                audit_prompt(
                    snapshot, plan_token, scope.packet,
                    shard_index=index, shard_count=shard_count,
                ),
                bounded_timeout(
                    deadline, requested, AuditError, reserve_retry=attempt == 1,
                ),
                environment, forbidden_paths,
            )
            return usage, load_audit_result(
                result_path, snapshot, completed_items, scope.primary_paths,
            )
        reviewed = one_infrastructure_retry(
            action, RetryableAuditError,
            lambda: emit_status(
                "audit-retrying", reason="invalid-review-item", shard=index,
            ),
        )
        emit_status("shard-completed", shard=index, shards=shard_count)
        return reviewed
    finally:
        set_workspace_writable(workspace, True)
def run_audit(repo: Path, plan_arg: Path, timeout: int, controller_codex: Path | None = None) -> dict[str, object]:
    started = time.monotonic()
    if timeout <= 0:
        raise AuditError("audit timeout must be positive")
    root = repository_root(repo.resolve())
    plan = resolve_plan(root, plan_arg)
    snapshot = snapshot_id(root)
    validate_audit_entry(plan, root, snapshot, AuditError)
    plan_token = file_digest(plan)
    audit_changed_paths = changed_paths(root, plan_base_sha(root, plan))
    scopes = partition_review_scopes(
        root, plan, audit_changed_paths,
        max_related_sections=FINAL_RELATED_SECTIONS,
        max_related_bytes=FINAL_RELATED_BYTES, max_packet_bytes=MAX_PACKET_BYTES,
    )
    with tempfile.TemporaryDirectory(prefix="hard-eng-audit-") as temporary:
        directory = Path(temporary)
        schema_path = directory / "schema.json"
        schema_path.write_text(json.dumps(output_schema(), separators=(",", ":")), encoding="utf-8")
        deadline = time.monotonic() + timeout
        workers = min(MAX_AUDIT_WORKERS, len(scopes))
        emit_status("audit-starting", shards=len(scopes), workers=1,
                    parallel_worker_cap=workers, cache_warm_shards=1)
        def review(index, scope):
            return run_audit_scope(
                directory=directory, schema_path=schema_path, scope=scope, index=index,
                shard_count=len(scopes), snapshot=snapshot, plan_token=plan_token,
                deadline=deadline, controller_codex=controller_codex,
            )
        prefix_bytes = common_prefix_bytes(audit_prompt(
            snapshot, plan_token, scope.packet, shard_index=index, shard_count=len(scopes),
        ) for index, scope in enumerate(scopes, 1))
        reviewed, schedule = warm_then_parallel(
            scopes, review, lambda result: result[0].get("cached_input_tokens", 0), workers,
        )
        usages = [usage for usage, _ in reviewed]
        results = [result for _, result in reviewed]
        validated = aggregate_audit_results(snapshot, tuple(results))
        usage = {
            key: sum(item.get(key, 0) for item in usages)
            for key in {name for item in usages for name in item}
        }
    require_unchanged_snapshot(root, snapshot)
    require_unchanged_file(plan, plan_token, "PLAN")
    validated["usage"] = usage
    elapsed_ms = max(0, round((time.monotonic() - started) * 1000))
    validated["performance"] = audit_performance_metrics(
        usages, elapsed_ms=elapsed_ms, shard_count=len(scopes),
        common_prefix_bytes=prefix_bytes, schedule=schedule)
    emit_status(
        "completed",
        verdict=validated["verdict"],
        cache_proven=schedule["cacheProven"],
        cache_hit_basis_points=validated["performance"]["cacheHitBasisPoints"],
        findings=len(validated["findings"]),
        unknowns=len(validated["unknowns"]),
    )
    return validated
def self_test() -> None:
    validate_result(
        {"snapshot_id": "sha256:" + "0" * 64, "verdict": "pass", "findings": [], "unknowns": [], "summary": "clean"},
        "sha256:" + "0" * 64,
    )
    json.dumps(output_schema())
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--plan")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    parser.add_argument("--admission", action="store_true")
    parser.add_argument("--estimate-plan", action="store_true")
    parser.add_argument("--estimate-unit")
    parser.add_argument("--candidate-patch")
    parser.add_argument("--unit")
    parser.add_argument("--snapshot-only", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.admission and (args.snapshot_only or args.self_test):
        parser.error("--admission is not allowed with --snapshot-only or --self-test")
    if (args.estimate_plan or args.estimate_unit or args.candidate_patch) and not args.admission:
        parser.error("admission modes require --admission")
    if args.unit and not (args.admission and args.candidate_patch):
        parser.error("--unit requires candidate admission")
    admission_modes = sum(bool(value) for value in (
        args.estimate_plan, args.estimate_unit, args.candidate_patch,
    ))
    if args.admission and admission_modes != 1:
        parser.error(
            "--admission requires exactly one of --estimate-plan, --estimate-unit, or --candidate-patch"
        )
    if args.admission and args.candidate_patch and not args.unit:
        parser.error("candidate admission requires --unit")
    try:
        if args.self_test:
            self_test()
            print("audit-self-test: PASS")
            return 0
        root = repository_root(Path(args.repo).expanduser().resolve())
        if args.admission:
            if not args.plan:
                raise AuditError("--plan is required")
            if args.estimate_plan:
                passed = True
                try:
                    for result in estimate_plan_reports(root, Path(args.plan)):
                        print(json.dumps(result, separators=(",", ":"), ensure_ascii=False), flush=True)
                        passed = passed and result["result"] == "pass"
                except (AuditError, GeneratedEvidenceError, OSError, UnicodeError) as exc:
                    result = estimate_error_report(exc)
                    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False), flush=True)
                    passed = False
                return 0 if passed else 1
            try:
                if args.estimate_unit:
                    result = estimate_admission_report(root, Path(args.plan), args.estimate_unit)
                else:
                    result = candidate_admission_report(
                        root, Path(args.plan), load_patch(Path(args.candidate_patch)), args.unit
                    )
            except (AuditError, CandidateError, GeneratedEvidenceError, OSError, UnicodeError) as exc:
                result = (estimate_error_report(exc) if args.estimate_unit
                          else candidate_error_report(exc))
            print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
            return 0 if result["result"] == "pass" else 1
        if args.snapshot_only:
            print(snapshot_id(root))
            return 0
        if not args.plan:
            raise AuditError("--plan is required")
        result = run_audit(root, Path(args.plan).expanduser(), args.timeout)
        print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
        return 0
    except (AuditError, GeneratedEvidenceError, OSError, UnicodeError) as exc:
        stage = "timed-out" if "timed out" in str(exc) or "stalled" in str(exc) else "blocked"
        emit_status(stage, reason=str(exc))
        print(f"audit: FAIL | {exc}", file=sys.stderr)
        return 1
if __name__ == "__main__":
    raise SystemExit(main())

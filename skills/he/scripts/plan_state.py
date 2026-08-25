#!/usr/bin/env python3
"""Small deterministic state owner for the Hard Eng Feature Brief."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from authorization_recovery import validate_reopen_authorization
from execution_evidence import (
    EvidenceError,
    authorize_execution,
    invalidate_direct_receipt,
    refresh_execution_state,
    validate_execution,
)
from lifecycle_excludes import LifecycleExcludeError, activate_lifecycle_artifacts, exclude_terminal_artifacts
from plan_parser import build as build_parser
from plan_paths import safe_plan_path as _resolve_safe_plan_path
from plan_template import render as render_template
from safe_plan_io import (
    SafePlanIOError,
    create_new,
    delivered_head_artifact,
    read_snapshot,
    replace_if_unchanged,
    repo_root,
    repository_artifact,
)
from setup_state import require_setup
from ux_reference import UXReferenceError, reference_value, source_value
from ux_reference import markdown as render_ux_reference_markdown

sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))
from slice_gate import checkpoint_error as receipt_checkpoint_error
from slice_gate import receipt_status


class PlanError(ValueError):
    """Invalid Feature Brief or transition."""


STATE_START = "<!-- hard-eng-state:v1 -->"
STATE_END = "<!-- /hard-eng-state -->"
STATE_KEYS = (
    "state_version",
    "plan_id",
    "lifecycle_status",
    "approval_status",
    "approval_fingerprint",
    "approval_provenance",
    "green_artifact",
    "active_slice",
    "completed_slices",
    "next_action",
    "replan_reason",
)
STATE_KEYS_V2 = STATE_KEYS + ("execution_mode",)
SECTIONS = (
    "Outcome",
    "Non-goals",
    "Material decisions",
    "Acceptance examples",
    "Affected canonical areas",
    "Risk and rollback",
    "First vertical slice",
)
FROZEN_SECTIONS = SECTIONS[:4]
ACTIVE = {"planning", "build-ready", "building", "green"}
STATUSES = ACTIVE | {"shipped", "cancelled"}
APPROVALS = {"pending", "approved"}
REPLAN_REASONS = {"changed-outcome", "material-safety-contract"}
MUTABLE_FIELDS = {"lifecycle_status", "active_slice", "completed_slices", "next_action"}
TRANSITIONS = {
    "planning": set(),
    "build-ready": {"building"},
    "building": {"green"},
    "green": {"building", "shipped"},
    "shipped": set(),
    "cancelled": set(),
}
ROUTES = {
    "planning": "he-plan",
    "build-ready": "he-build",
    "building": "he-build",
    "green": "he-ship",
    "shipped": "terminal",
    "cancelled": "terminal",
}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SLICE = re.compile(r"S-([1-9][0-9]*)")
FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
STATE_ROW = re.compile(r"^- ([a-z_]+) = (.*)$")
PLACEHOLDER = re.compile(
    r"(?im)(?:^-\s*(?:TBD|TODO|UNKNOWN|NONE PROVIDED)\s*\.?\s*$|"
    r"=\s*(?:TBD|TODO|UNKNOWN|NONE PROVIDED)\s*\.?\s*$)"
)


def token_for(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def safe_plan_path(repo: Path, value: str | Path) -> Path:
    try:
        return _resolve_safe_plan_path(repo, value)
    except SafePlanIOError as error:
        raise PlanError(str(error)) from error


@contextlib.contextmanager
def plan_lock(repo: Path, path: Path):
    identity = hashlib.sha256(f"{repo}\0{path}".encode()).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"hard-eng-plan-{identity}.lock"
    flags = os.O_CREAT | os.O_RDWR
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        if os.fstat(descriptor).st_uid != os.getuid():
            raise PlanError("plan lock is not owned by the current user")
        with os.fdopen(descriptor, "a+", encoding="utf-8") as handle:
            descriptor = -1
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def state_bounds(text: str) -> tuple[int, int]:
    if text.count(STATE_START) != 1 or text.count(STATE_END) != 1:
        raise PlanError("requires exactly one v1 State block")
    start = text.index(STATE_START) + len(STATE_START)
    end = text.index(STATE_END, start)
    if end <= start:
        raise PlanError("State block is malformed")
    return start, end


def parse_state(text: str) -> dict[str, str]:
    start, end = state_bounds(text)
    rows: dict[str, str] = {}
    for raw in text[start:end].strip().splitlines():
        match = STATE_ROW.fullmatch(raw.strip())
        if not match:
            raise PlanError(f"invalid State row: {raw[:80]}")
        key, value = match.groups()
        if key in rows:
            raise PlanError(f"duplicate State key: {key}")
        rows[key] = value.strip()
    keys = STATE_KEYS_V2 if rows.get("state_version") == "2" else STATE_KEYS
    missing = [key for key in keys if key not in rows]
    extra = sorted(set(rows) - set(keys))
    if missing or extra:
        raise PlanError(f"State keys mismatch; missing={missing}; extra={extra}")
    return rows


def parse_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\n", text))
    headings = [match.group(1).strip() for match in matches]
    if headings != list(SECTIONS):
        raise PlanError(f"required section order is: {' -> '.join(SECTIONS)}")
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[headings[index]] = text[match.end() : end].strip()
    return sections


def risk_fields(section: str) -> tuple[str, str]:
    values: dict[str, str] = {}
    for key in ("risk_level", "critical_overlay", "rollback"):
        matches = re.findall(rf"(?m)^- {key} = (.+)$", section)
        if len(matches) != 1:
            raise PlanError(f"Risk and rollback requires exactly one `{key}` row")
        values[key] = matches[0].strip()
    if values["risk_level"] not in {"standard", "critical"}:
        raise PlanError("risk_level must be standard or critical")
    overlay = values["critical_overlay"]
    if values["risk_level"] == "standard" and overlay != "none":
        raise PlanError("standard risk requires critical_overlay = none")
    if values["risk_level"] == "critical" and overlay == "none":
        raise PlanError("critical risk requires a scoped critical_overlay")
    return values["risk_level"], overlay


def ux_reference_markdown(repo: Path, text: str) -> str | None:
    section = parse_sections(text)["Material decisions"]
    try:
        return render_ux_reference_markdown(repo, reference_value(section), source_value(section))
    except UXReferenceError as error:
        raise PlanError(str(error)) from error


def require_ux_reference_target(repo: Path, text: str) -> None:
    ux_reference_markdown(repo, text)


def frozen_fingerprint(sections: dict[str, str]) -> str:
    risk_level, overlay = risk_fields(sections["Risk and rollback"])
    values = [f"{heading}\n{sections[heading].strip()}" for heading in FROZEN_SECTIONS]
    values.extend((f"risk_level\n{risk_level}", f"critical_overlay\n{overlay}"))
    return token_for("\n\n".join(values))


def completed_numbers(value: str) -> tuple[int, ...]:
    if value == "none":
        return ()
    matches = tuple(SLICE.fullmatch(item) for item in value.split(","))
    if any(match is None for match in matches):
        raise PlanError("completed_slices must be none or comma-separated S-N values")
    numbers = tuple(int(match.group(1)) for match in matches if match is not None)
    if numbers != tuple(range(1, len(numbers) + 1)):
        raise PlanError("completed_slices must be a contiguous ordered prefix from S-1")
    return numbers


def validate_text(
    text: str, *, ready: bool | None = None, allow_legacy_missing_ux_reference: bool = False
) -> dict[str, str]:
    state = parse_state(text)
    sections = parse_sections(text)
    if state["lifecycle_status"] not in STATUSES:
        raise PlanError("invalid lifecycle_status")
    if state["state_version"] not in {"1", "2"}:
        raise PlanError("state_version must be 1 or 2")
    if state["approval_status"] not in APPROVALS:
        raise PlanError("invalid approval_status")
    if not state["plan_id"] or any(c.isspace() for c in state["plan_id"]):
        raise PlanError("plan_id must be one nonempty token")
    if not SLICE.fullmatch(state["active_slice"]) and state["active_slice"] != "none":
        raise PlanError("active_slice must be S-N or none")
    completed_count = len(completed_numbers(state["completed_slices"]))
    active = SLICE.fullmatch(state["active_slice"])
    if active is not None and int(active.group(1)) != completed_count + 1:
        raise PlanError("active_slice must be the first slice after completed_slices")
    if not state["next_action"]:
        raise PlanError("next_action must be nonempty")
    fingerprint = state["approval_fingerprint"]
    if fingerprint != "none" and not FINGERPRINT.fullmatch(fingerprint):
        raise PlanError("approval_fingerprint must be none or sha256")
    provenance = state["approval_provenance"]
    if state["approval_status"] == "pending" and provenance != "none":
        raise PlanError("pending approval requires approval_provenance = none")
    if state["approval_status"] == "approved" and provenance != "ready-to-build":
        raise PlanError("approved state requires explicit approval_provenance")
    artifact = state["green_artifact"]
    if state["lifecycle_status"] in {"green", "shipped"}:
        if not FINGERPRINT.fullmatch(artifact):
            raise PlanError("green/shipped state requires green_artifact")
        if state["active_slice"] != "none" or state["completed_slices"] == "none":
            raise PlanError("green/shipped state requires completed slices and no active slice")
    elif state["lifecycle_status"] == "cancelled":
        if state["active_slice"] != "none":
            raise PlanError("cancelled state requires no active slice")
        if artifact != "none":
            raise PlanError("cancelled state requires green_artifact = none")
    elif artifact != "none":
        raise PlanError("non-green state requires green_artifact = none")
    risk_fields(sections["Risk and rollback"])
    ux_matches = re.findall(r"(?m)^- ux_reference = (.+)$", sections["Material decisions"])
    if not (allow_legacy_missing_ux_reference and not ux_matches):
        try:
            reference_value(sections["Material decisions"])
        except UXReferenceError as error:
            raise PlanError(str(error)) from error
    is_ready = state["approval_status"] == "approved" if ready is None else ready
    if is_ready:
        empty = [heading for heading, body in sections.items() if not body or PLACEHOLDER.search(body)]
        if empty:
            raise PlanError(f"Ready-to-build brief has placeholders: {', '.join(empty)}")
        if state["lifecycle_status"] == "planning":
            raise PlanError("approved plan cannot remain planning")
        expected = frozen_fingerprint(sections)
        if state["approval_fingerprint"] != expected:
            raise PlanError(
                "approved frozen bytes changed; restore them, or reopen only when "
                "accepted constraints materially changed"
            )
    else:
        if state["lifecycle_status"] not in {"planning", "cancelled"}:
            raise PlanError("pending approval requires planning or cancelled state")
        if state["approval_fingerprint"] != "none":
            raise PlanError("pending approval requires approval_fingerprint = none")
    if (
        state["lifecycle_status"] in {"build-ready", "building", "green", "shipped"}
        and state["approval_status"] != "approved"
    ):
        raise PlanError("post-planning state requires Ready-to-build approval")
    if state["replan_reason"] != "none" and state["replan_reason"] not in REPLAN_REASONS:
        raise PlanError("invalid replan_reason")
    return state


def render_state(text: str, changes: dict[str, str]) -> str:
    state = parse_state(text)
    state.update(changes)
    keys = STATE_KEYS_V2 if state.get("state_version") == "2" else STATE_KEYS
    block = "\n" + "\n".join(f"- {key} = {state[key]}" for key in keys) + "\n"
    start, end = state_bounds(text)
    return text[:start] + block + text[end:]


def approval_candidate(text: str) -> tuple[str, dict[str, str]]:
    state = parse_state(text)
    if state["lifecycle_status"] != "planning":
        raise PlanError("only a planning brief can receive Ready-to-build approval")
    sections = parse_sections(text)
    candidate = render_state(
        text,
        {
            "lifecycle_status": "build-ready",
            "approval_status": "approved",
            "approval_fingerprint": frozen_fingerprint(sections),
            "approval_provenance": "ready-to-build",
            "next_action": "Build the first vertical slice.",
            "replan_reason": "none",
        },
    )
    return candidate, validate_text(candidate, ready=True)


def template(slug: str, plan_id: str) -> str:
    return render_template(slug, plan_id, STATE_START, STATE_END)


TICKET_MD = re.compile(r"tickets/T-(?:[1-9][0-9]*|int)\.md")


def assert_single_plan_markdown(repo: Path, plan: Path) -> None:
    extras = sorted(
        item
        for item in plan.parent.rglob("*.md")
        if item != plan and not TICKET_MD.fullmatch(item.relative_to(plan.parent).as_posix())
    )
    if extras:
        raise PlanError(f"active feature has extra Markdown file: {extras[0].relative_to(repo)}")


def resolve_plan(repo: Path, value: str | None, *, require: bool = True) -> Path | None:
    repo = repo.resolve()
    if value:
        selected = safe_plan_path(repo, value)
        assert_single_plan_markdown(repo, selected)
        return selected
    candidates: list[Path] = []
    for path in sorted((repo / "features").glob("*/PLAN.md")):
        try:
            safe = safe_plan_path(repo, path)
            data, _ = read_snapshot(repo, safe.relative_to(repo))
            text = data.decode("utf-8")
            match = re.search(r"(?m)^- lifecycle_status = ([a-z-]+)$", text)
            if match is not None and match.group(1) in ACTIVE:
                assert_single_plan_markdown(repo, safe)
                candidates.append(safe)
        except OSError as error:
            raise PlanError(f"cannot read Feature Brief: {path}") from error
    if len(candidates) > 1:
        relative = [str(path.relative_to(repo)) for path in candidates]
        raise PlanError(f"multiple active Feature Briefs: {relative}")
    if not candidates and not require:
        return None
    if not candidates:
        raise PlanError("no active Feature Brief")
    return candidates[0]


def read_checked(
    repo: Path,
    value: str | None,
    *,
    allow_legacy_missing_ux_reference: bool = False,
    validate_authorization: bool = True,
    session_id: str | None = None,
    request_digest: str | None = None,
) -> tuple[Path, str, int, dict[str, str]]:
    path = resolve_plan(repo, value)
    assert path is not None
    try:
        relative = path.relative_to(repo)
    except ValueError as error:
        raise PlanError("PLAN must be inside the repository") from error
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "features"
        or not SLUG.fullmatch(relative.parts[1])
        or relative.parts[2] != "PLAN.md"
    ):
        raise PlanError("PLAN path must be features/<feature-slug>/PLAN.md")
    data, mode = read_snapshot(repo, relative)
    text = data.decode("utf-8")
    state = validate_text(text, allow_legacy_missing_ux_reference=allow_legacy_missing_ux_reference)
    if state["approval_status"] == "approved" and validate_authorization:
        validate_execution(
            repo,
            path,
            state["approval_fingerprint"],
            session_id or os.environ.get("HARD_ENG_SESSION_ID", ""),
            request_digest or os.environ.get("HARD_ENG_REQUEST_DIGEST", ""),
        )
    return path, text, mode, state


def adapter_context(args: argparse.Namespace) -> tuple[str, str]:
    return (
        args.session_id or os.environ.get("HARD_ENG_SESSION_ID", ""),
        args.request_digest or os.environ.get("HARD_ENG_REQUEST_DIGEST", ""),
    )


def add_ux_reference_placeholder(text: str) -> str:
    sections = parse_sections(text)
    has_reference = re.search(r"(?m)^- ux_reference = ", sections["Material decisions"])
    has_sources = re.search(r"(?m)^- ux_reference_sources = ", sections["Material decisions"])
    if has_reference and has_sources:
        return text
    heading = "## Material decisions\n"
    if text.count(heading) != 1:
        raise PlanError("requires exactly one Material decisions heading")
    rows = ""
    if not has_reference:
        rows += "- ux_reference = TBD\n"
    if not has_sources:
        rows += "- ux_reference_sources = TBD\n"
    return text.replace(heading, f"{heading}{rows}", 1)


def require_token(text: str, expected: str) -> None:
    actual = token_for(text)
    if expected != actual:
        raise PlanError(f"stale plan token; expected current token {actual}")


def emit(path: Path, text: str, state: dict[str, str]) -> None:
    print("result=valid")
    print(f"plan={path}")
    print(f"token={token_for(text)}")
    print(f"lifecycle_status={state['lifecycle_status']}")
    print(f"approval_status={state['approval_status']}")
    try:
        print(f"brief_fingerprint={frozen_fingerprint(parse_sections(text))}")
    except PlanError:
        pass
    print(f"route_target={ROUTES[state['lifecycle_status']]}")
    print(f"active_slice={state['active_slice']}")
    print(f"completed_slices={state['completed_slices']}")
    print(f"next_action={state['next_action']}")
    if state["lifecycle_status"] == "building":
        repo = path.parents[2]
        if state["active_slice"] != "none":
            print(f"slice_receipt={receipt_status(repo, path, state['plan_id'], state['active_slice'])}")
        elif state["completed_slices"] != "none":
            print(f"full_receipt={receipt_status(repo, path, state['plan_id'], 'full')}")
    repo = path.parents[2]
    if state.get("execution_mode") == "tickets":
        from ticket_state import board_summary

        for key, value in board_summary(repo, path).items():
            print(f"board_{key}={value}")
    try:
        markdown = ux_reference_markdown(repo, text)
    except PlanError:
        markdown = None
    if markdown is not None:
        print(f"ux_reference_markdown={markdown}")
    if state["lifecycle_status"] == "planning":
        try:
            approval_candidate(text)
            require_ux_reference_target(repo, text)
        except PlanError:
            pass
        else:
            print("ready_for_approval=yes")


def command_init(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    if blocked := require_setup(repo):
        raise PlanError(blocked)
    if not SLUG.fullmatch(args.feature_slug):
        raise PlanError("feature slug must be lowercase kebab-case")
    path = safe_plan_path(repo, repo / "features" / args.feature_slug / "PLAN.md")
    with plan_lock(repo, path):
        if path.exists() or path.is_symlink():
            raise PlanError(f"refusing to overwrite {path}")
        activate_lifecycle_artifacts(repo, path)
        plan_id = args.plan_id or f"{args.feature_slug}-{uuid.uuid4().hex[:8]}"
        text = template(args.feature_slug, plan_id)
        create_new(repo, path.relative_to(repo), text.encode("utf-8"), 0o644)
    emit(path, text, validate_text(text))


def command_inspect(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan, require=False)
    if path is None:
        print("result=none")
        raise SystemExit(2)
    session_id, request_digest = adapter_context(args)
    path, text, _, state = read_checked(repo, str(path), session_id=session_id, request_digest=request_digest)
    emit(path, text, state)


def command_validate(args: argparse.Namespace) -> None:
    session_id, request_digest = adapter_context(args)
    path, text, _, state = read_checked(
        repo_root(args.repo), args.plan, session_id=session_id, request_digest=request_digest
    )
    emit(path, text, state)


def command_approve(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    with plan_lock(repo, path):
        path, text, mode, _ = read_checked(repo, str(path))
        require_token(text, args.expect_token)
        candidate, approved = approval_candidate(text)
        require_ux_reference_target(repo, candidate)
        authorize_execution(
            repo,
            path,
            approved["approval_fingerprint"],
            args.approval_reply,
            args.session_id,
            args.request_digest,
            args.allowed_action,
            args.expires_in_seconds,
        )
        replace_if_unchanged(repo, path.relative_to(repo), text.encode("utf-8"), mode, candidate.encode("utf-8"))
    emit(path, candidate, approved)


def command_reopen(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    session_id, request_digest = adapter_context(args)
    with plan_lock(repo, path):
        path, text, mode, state = read_checked(
            repo, str(path), allow_legacy_missing_ux_reference=True, validate_authorization=False
        )
        require_token(text, args.expect_token)
        if state["approval_status"] != "approved":
            raise PlanError("only an approved brief can be reopened")
        if state["lifecycle_status"] in {"shipped", "cancelled"}:
            raise PlanError("terminal lifecycle state is immutable")
        validate_reopen_authorization(
            repo,
            path,
            state["approval_fingerprint"],
            session_id,
            request_digest,
            recover_invalid_authorization=args.recover_invalid_authorization,
        )
        candidate = render_state(
            text,
            {
                "lifecycle_status": "planning",
                "approval_status": "pending",
                "approval_fingerprint": "none",
                "approval_provenance": "none",
                "green_artifact": "none",
                "next_action": "Update changed frozen constraints and request Ready-to-build approval.",
                "replan_reason": args.reason,
            },
        )
        candidate = add_ux_reference_placeholder(candidate)
        reopened = validate_text(candidate, ready=False)
        replace_if_unchanged(repo, path.relative_to(repo), text.encode("utf-8"), mode, candidate.encode("utf-8"))
    emit(path, candidate, reopened)


def command_checkpoint(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    session_id, request_digest = adapter_context(args)
    with plan_lock(repo, path):
        path, text, mode, state = read_checked(repo, str(path), validate_authorization=False)
        require_token(text, args.expect_token)
        if state["lifecycle_status"] in {"shipped", "cancelled"}:
            raise PlanError("terminal lifecycle state is immutable")
        changes: dict[str, str] = {}
        if not args.set:
            raise PlanError("checkpoint requires at least one --set field=value")
        for assignment in args.set:
            if "=" not in assignment:
                raise PlanError("--set requires field=value")
            key, value = assignment.split("=", 1)
            if key not in MUTABLE_FIELDS or not value.strip():
                raise PlanError(f"checkpoint field is not mutable: {key}")
            changes[key] = value.strip()
        recovering_drift = state["lifecycle_status"] == "green" and changes.get("lifecycle_status") == "building"
        if "completed_slices" in changes and state["state_version"] == "2":
            from ticket_state import epic_green_gate_error

            if message := epic_green_gate_error(repo, path, {**state, **changes}):
                raise PlanError(message)
        elif "completed_slices" in changes:
            before = completed_numbers(state["completed_slices"])
            after = completed_numbers(changes["completed_slices"])
            if after[: len(before)] != before or len(after) > len(before) + 1:
                raise PlanError("completed_slices progress cannot regress or skip")
            if len(after) == len(before) + 1 and (
                state["lifecycle_status"] != "building" or state["active_slice"] != f"S-{after[-1]}"
            ):
                raise PlanError("only the current building slice can be completed")
            if len(after) == len(before) + 1 and (
                message := receipt_checkpoint_error(repo, path, state["plan_id"], f"S-{after[-1]}")
            ):
                raise PlanError(message)
        if "lifecycle_status" in changes:
            requested = changes["lifecycle_status"]
            if requested == "cancelled":
                if state["lifecycle_status"] in {"shipped", "cancelled"}:
                    raise PlanError("terminal lifecycle state cannot be cancelled")
                if not args.confirm_cancel:
                    raise PlanError("cancelled requires --confirm-cancel after exact user decision")
                if "next_action" not in changes:
                    raise PlanError("cancelled requires next_action recording the exact decision")
                changes["active_slice"] = "none"
            elif requested not in TRANSITIONS[state["lifecycle_status"]]:
                raise PlanError(f"illegal lifecycle transition: {state['lifecycle_status']} -> {requested}")
            if state["lifecycle_status"] == "building" and requested == "green":
                if message := receipt_checkpoint_error(repo, path, state["plan_id"], "full"):
                    raise PlanError(message)
                changes["green_artifact"] = repository_artifact(repo)
            elif state["lifecycle_status"] == "green" and requested == "shipped":
                delivered_head_artifact(repo, state["green_artifact"])
            elif requested in {"building", "cancelled"}:
                changes["green_artifact"] = "none"
        if state["approval_status"] == "approved":
            validate_execution(
                repo,
                path,
                state["approval_fingerprint"],
                session_id,
                request_digest,
                allow_repository_drift=recovering_drift,
                allow_head_drift=recovering_drift,
            )
        candidate = render_state(text, changes)
        updated = validate_text(candidate)
        replace_if_unchanged(repo, path.relative_to(repo), text.encode("utf-8"), mode, candidate.encode("utf-8"))
        if recovering_drift:
            refresh_execution_state(repo, path, state["approval_fingerprint"], session_id, request_digest)
        if updated["lifecycle_status"] in {"shipped", "cancelled"}:
            try:
                invalidate_direct_receipt(repo)
                exclude_terminal_artifacts(repo, path, updated["lifecycle_status"])
            except (EvidenceError, LifecycleExcludeError, SafePlanIOError) as error:
                relative = path.relative_to(repo)
                raise PlanError(
                    "terminal checkpoint saved but local status cleanup failed; "
                    "run `plan_state.py sync-excludes "
                    f"--repo {repo} --plan {relative}`: {error}"
                ) from error
    emit(path, candidate, updated)


def command_sync_excludes(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    session_id, request_digest = adapter_context(args)
    path, text, _, state = read_checked(repo, args.plan, session_id=session_id, request_digest=request_digest)
    if state["lifecycle_status"] not in {"shipped", "cancelled"}:
        raise PlanError("sync-excludes requires shipped or cancelled state")
    invalidate_direct_receipt(repo)
    exclude = exclude_terminal_artifacts(repo, path, state["lifecycle_status"])
    emit(path, text, state)
    print(f"lifecycle_exclude={exclude}")


def command_assert_green(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    session_id, request_digest = adapter_context(args)
    path, text, _, state = read_checked(
        repo,
        args.plan,
        validate_authorization=not args.artifact_only,
        session_id=session_id,
        request_digest=request_digest,
    )
    if state["lifecycle_status"] not in {"green", "shipped"}:
        raise PlanError("assert-green requires green or shipped state")
    actual = (
        delivered_head_artifact(repo, state["green_artifact"]) if args.delivered_head else repository_artifact(repo)
    )
    if actual != state["green_artifact"]:
        raise PlanError("green artifact drift; return to building")
    emit(path, text, state)
    print(f"green_artifact={actual}")


def parser() -> argparse.ArgumentParser:
    return build_parser(REPLAN_REASONS)


def main() -> int:
    args = parser().parse_args()
    actions = {
        "init": command_init,
        "inspect": command_inspect,
        "validate": command_validate,
        "approve": command_approve,
        "reopen": command_reopen,
        "checkpoint": command_checkpoint,
        "sync-excludes": command_sync_excludes,
        "assert-green": command_assert_green,
    }
    try:
        actions[args.command](args)
    except (
        OSError,
        UnicodeError,
        subprocess.SubprocessError,
        EvidenceError,
        PlanError,
        SafePlanIOError,
        LifecycleExcludeError,
    ) as error:
        print(f"result=invalid\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

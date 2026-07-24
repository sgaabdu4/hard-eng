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

from legacy_v4 import LegacyV4Error, migration_sections, parse as parse_legacy_v4
from safe_plan_io import SafePlanIOError, archive_then_replace, create_new
from safe_plan_io import delivered_head_artifact
from safe_plan_io import read_snapshot
from safe_plan_io import replace_if_unchanged, repository_artifact

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


def repo_root(value: str) -> Path:
    supplied = Path(value)
    if not supplied.exists() or not supplied.is_dir():
        raise PlanError("repository root must be an existing directory")
    resolved = supplied.resolve()
    try:
        result = subprocess.run(
            ["git", "-C", str(resolved), "rev-parse", "--show-toplevel"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise PlanError("repository root is not a readable Git worktree") from error
    if result.returncode != 0 or Path(result.stdout.strip()).resolve() != resolved:
        raise PlanError("repository root must be the Git worktree root")
    return resolved


def safe_plan_path(repo: Path, value: str | Path) -> Path:
    repo = repo.resolve()
    raw = Path(value)
    joined = raw if raw.is_absolute() else repo / raw
    lexical = Path(os.path.abspath(joined))
    try:
        lexical_relative = lexical.relative_to(repo)
    except ValueError as error:
        raise PlanError("PLAN lexical path must be inside the canonical repository") from error
    current = repo
    for part in lexical_relative.parts:
        current /= part
        if current.is_symlink():
            raise PlanError(f"PLAN path contains a symlink: {current}")
    resolved = lexical.resolve(strict=False)
    try:
        relative = resolved.relative_to(repo)
    except ValueError as error:
        raise PlanError("PLAN must be inside the repository") from error
    return resolved


@contextlib.contextmanager
def plan_lock(repo: Path, path: Path):
    identity = hashlib.sha256(f"{repo}\0{path}".encode("utf-8")).hexdigest()
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
    missing = [key for key in STATE_KEYS if key not in rows]
    extra = sorted(set(rows) - set(STATE_KEYS))
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
        sections[headings[index]] = text[match.end():end].strip()
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


def migrated_template(slug: str, legacy: dict[str, str], source: str, source_hash: str) -> str:
    text = template(slug, legacy["plan_id"])
    replacements, risk_level, overlay = migration_sections(source, legacy, source_hash)
    approved = legacy["plan_approved"] == "yes"
    text = text.replace("- risk_level = standard", f"- risk_level = {risk_level}")
    text = text.replace("- critical_overlay = none", f"- critical_overlay = {overlay}")
    changes = {
        "active_slice": "none" if legacy["active_slice"] == "final" else legacy["active_slice"],
        "completed_slices": (
            "none" if legacy["completed_slices"] == "none"
            else ",".join(part.strip() for part in legacy["completed_slices"].split(","))
        ),
        "next_action": legacy["next_action"],
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    if approved:
        changes.update({
            "lifecycle_status": legacy["lifecycle_status"],
            "approval_status": "approved",
            "approval_provenance": f"legacy-v4:{source_hash}",
        })
        provisional = render_state(text, changes)
        changes["approval_fingerprint"] = frozen_fingerprint(parse_sections(provisional))
    return render_state(text, changes)


def validate_text(text: str, *, ready: bool | None = None) -> dict[str, str]:
    state = parse_state(text)
    sections = parse_sections(text)
    if state["lifecycle_status"] not in STATUSES:
        raise PlanError("invalid lifecycle_status")
    if state["state_version"] != "1":
        raise PlanError("state_version must be 1")
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
    if state["approval_status"] == "approved" and not (
        provenance == "ready-to-build"
        or re.fullmatch(r"legacy-v4:sha256:[0-9a-f]{64}", provenance)
    ):
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
    if state["lifecycle_status"] in {"build-ready", "building", "green", "shipped"}:
        if state["approval_status"] != "approved":
            raise PlanError("post-planning state requires Ready-to-build approval")
    if state["replan_reason"] != "none" and state["replan_reason"] not in REPLAN_REASONS:
        raise PlanError("invalid replan_reason")
    return state


def render_state(text: str, changes: dict[str, str]) -> str:
    state = parse_state(text)
    state.update(changes)
    block = "\n" + "\n".join(f"- {key} = {state[key]}" for key in STATE_KEYS) + "\n"
    start, end = state_bounds(text)
    return text[:start] + block + text[end:]


def template(slug: str, plan_id: str) -> str:
    title = slug.replace("-", " ").title()
    return f"""# Feature Brief: {title}

{STATE_START}
- state_version = 1
- plan_id = {plan_id}
- lifecycle_status = planning
- approval_status = pending
- approval_fingerprint = none
- approval_provenance = none
- green_artifact = none
- active_slice = S-1
- completed_slices = none
- next_action = Complete the brief and request Ready-to-build approval.
- replan_reason = none
{STATE_END}

## Outcome
- TBD

## Non-goals
- TBD

## Material decisions
- TBD

## Acceptance examples
- TBD

## Affected canonical areas
- TBD

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = TBD

## First vertical slice
- S-1 = TBD
- proof = TBD
"""


def resolve_plan(repo: Path, value: str | None, *, require: bool = True) -> Path | None:
    repo = repo.resolve()
    if value:
        return safe_plan_path(repo, value)
    candidates: list[Path] = []
    for path in sorted((repo / "features").glob("*/PLAN.md")):
        try:
            safe = safe_plan_path(repo, path)
            data, _ = read_snapshot(repo, safe.relative_to(repo))
            text = data.decode("utf-8")
            if parse_state(text)["lifecycle_status"] in ACTIVE:
                candidates.append(safe)
        except (OSError, PlanError):
            try:
                safe = safe_plan_path(repo, path)
                data, _ = read_snapshot(repo, safe.relative_to(repo))
                legacy = parse_legacy_v4(data.decode("utf-8"), repo, safe)
                if legacy["lifecycle_status"] in {"shipped", "cancelled"}:
                    continue
            except (OSError, PlanError, UnicodeError):
                pass
            candidates.append(safe_plan_path(repo, path))
    if not candidates and not require:
        return None
    if not candidates:
        raise PlanError("no active Feature Brief")
    if len(candidates) > 1:
        relative = [str(path.relative_to(repo)) for path in candidates]
        raise PlanError(f"multiple active Feature Briefs; select --plan from {relative}")
    return candidates[0]


def read_checked(repo: Path, value: str | None) -> tuple[Path, str, int, dict[str, str]]:
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
    return path, text, mode, validate_text(text)


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
    print(f"route_target={ROUTES[state['lifecycle_status']]}")
    print(f"active_slice={state['active_slice']}")
    print(f"completed_slices={state['completed_slices']}")
    print(f"next_action={state['next_action']}")


def command_init(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    if not SLUG.fullmatch(args.feature_slug):
        raise PlanError("feature slug must be lowercase kebab-case")
    path = safe_plan_path(repo, repo / "features" / args.feature_slug / "PLAN.md")
    with plan_lock(repo, path):
        if path.exists() or path.is_symlink():
            raise PlanError(f"refusing to overwrite {path}")
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
    path, text, _, state = read_checked(repo, str(path))
    emit(path, text, state)


def command_validate(args: argparse.Namespace) -> None:
    path, text, _, state = read_checked(repo_root(args.repo), args.plan)
    emit(path, text, state)


def command_approve(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    with plan_lock(repo, path):
        path, text, mode, state = read_checked(repo, str(path))
        require_token(text, args.expect_token)
        if state["lifecycle_status"] != "planning":
            raise PlanError("only a planning brief can receive Ready-to-build approval")
        sections = parse_sections(text)
        candidate = render_state(text, {
            "lifecycle_status": "build-ready",
            "approval_status": "approved",
            "approval_fingerprint": frozen_fingerprint(sections),
            "approval_provenance": "ready-to-build",
            "next_action": "Build the first vertical slice.",
            "replan_reason": "none",
        })
        approved = validate_text(candidate, ready=True)
        replace_if_unchanged(
            repo, path.relative_to(repo), text.encode("utf-8"), mode,
            candidate.encode("utf-8"),
        )
    emit(path, candidate, approved)


def command_reopen(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    with plan_lock(repo, path):
        path, text, mode, state = read_checked(repo, str(path))
        require_token(text, args.expect_token)
        if state["approval_status"] != "approved":
            raise PlanError("only an approved brief can be reopened")
        if state["lifecycle_status"] in {"shipped", "cancelled"}:
            raise PlanError("terminal lifecycle state is immutable")
        candidate = render_state(text, {
            "lifecycle_status": "planning",
            "approval_status": "pending",
            "approval_fingerprint": "none",
            "approval_provenance": "none",
            "green_artifact": "none",
            "next_action": "Update changed frozen constraints and request Ready-to-build approval.",
            "replan_reason": args.reason,
        })
        reopened = validate_text(candidate, ready=False)
        replace_if_unchanged(
            repo, path.relative_to(repo), text.encode("utf-8"), mode,
            candidate.encode("utf-8"),
        )
    emit(path, candidate, reopened)


def command_checkpoint(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = resolve_plan(repo, args.plan)
    assert path is not None
    with plan_lock(repo, path):
        path, text, mode, state = read_checked(repo, str(path))
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
        if "completed_slices" in changes:
            before = completed_numbers(state["completed_slices"])
            after = completed_numbers(changes["completed_slices"])
            if after[:len(before)] != before or len(after) > len(before) + 1:
                raise PlanError("completed_slices progress cannot regress or skip")
            if len(after) == len(before) + 1 and (
                state["lifecycle_status"] != "building"
                or state["active_slice"] != f"S-{after[-1]}"
            ):
                raise PlanError("only the current building slice can be completed")
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
                raise PlanError(
                    f"illegal lifecycle transition: {state['lifecycle_status']} -> {requested}"
                )
            if state["lifecycle_status"] == "building" and requested == "green":
                changes["green_artifact"] = repository_artifact(repo)
            elif state["lifecycle_status"] == "green" and requested == "shipped":
                delivered_head_artifact(repo, state["green_artifact"])
            elif requested in {"building", "cancelled"}:
                changes["green_artifact"] = "none"
        candidate = render_state(text, changes)
        updated = validate_text(candidate)
        replace_if_unchanged(
            repo, path.relative_to(repo), text.encode("utf-8"), mode,
            candidate.encode("utf-8"),
        )
    emit(path, candidate, updated)


def command_migrate_v4(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path = safe_plan_path(repo, args.plan)
    relative = path.relative_to(repo)
    if (
        len(relative.parts) != 3
        or relative.parts[0] != "features"
        or not SLUG.fullmatch(relative.parts[1])
        or relative.parts[2] != "PLAN.md"
    ):
        raise PlanError("PLAN path must be features/<feature-slug>/PLAN.md")
    with plan_lock(repo, path):
        relative = path.relative_to(repo)
        data, mode = read_snapshot(repo, relative)
        source_hash = "sha256:" + hashlib.sha256(data).hexdigest()
        if args.expect_token != source_hash:
            raise PlanError(f"stale plan token; expected current token {source_hash}")
        source = data.decode("utf-8")
        legacy = parse_legacy_v4(source, repo, path)
        if legacy["lifecycle_status"] in {"shipped", "cancelled"}:
            raise PlanError("terminal legacy v4 PLAN is already inactive; migration is unsupported")
        archive = path.with_name(f"PLAN.legacy-v4.{source_hash.removeprefix('sha256:')}.md")
        if archive.is_symlink():
            raise PlanError("legacy v4 archive must not be a symlink")
        candidate = migrated_template(path.parent.name, legacy, source, source_hash)
        migrated = validate_text(candidate)
        archive_then_replace(
            repo, relative, data, mode, archive.name, candidate.encode("utf-8")
        )
    print("result=migrated")
    print(f"plan={path}")
    print(f"old_hash={source_hash}")
    print(f"new_hash={token_for(candidate)}")
    print(f"archive={archive}")
    print(f"archive_hash={source_hash}")
    print(f"token={token_for(candidate)}")
    print(f"lifecycle_status={migrated['lifecycle_status']}")
    print(f"approval_status={migrated['approval_status']}")
    print(f"route_target={ROUTES[migrated['lifecycle_status']]}")
    print(f"active_slice={migrated['active_slice']}")
    print(f"completed_slices={migrated['completed_slices']}")
    print(f"approval_provenance={migrated['approval_provenance']}")
    print(f"next_action={migrated['next_action']}")


def command_assert_green(args: argparse.Namespace) -> None:
    repo = repo_root(args.repo)
    path, text, _, state = read_checked(repo, args.plan)
    if state["lifecycle_status"] not in {"green", "shipped"}:
        raise PlanError("assert-green requires green or shipped state")
    actual = (
        delivered_head_artifact(repo, state["green_artifact"])
        if args.delivered_head else repository_artifact(repo)
    )
    if actual != state["green_artifact"]:
        raise PlanError("green artifact drift; return to building")
    emit(path, text, state)
    print(f"green_artifact={actual}")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("inspect", "validate", "approve", "reopen", "checkpoint", "assert-green"):
        command = commands.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--plan")
        if name in {"approve", "reopen", "checkpoint"}:
            command.add_argument("--expect-token", required=True)
    init = commands.add_parser("init")
    init.add_argument("--repo", required=True)
    init.add_argument("--feature-slug", required=True)
    init.add_argument("--plan-id")
    reopen = commands.choices["reopen"]
    reopen.add_argument("--reason", required=True, choices=sorted(REPLAN_REASONS))
    checkpoint = commands.choices["checkpoint"]
    checkpoint.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
    checkpoint.add_argument("--confirm-cancel", action="store_true")
    migrate = commands.add_parser("migrate-v4")
    migrate.add_argument("--repo", required=True)
    migrate.add_argument("--plan", required=True)
    migrate.add_argument("--expect-token", required=True)
    commands.choices["assert-green"].add_argument(
        "--delivered-head", action="store_true"
    )
    return root


def main() -> int:
    args = parser().parse_args()
    actions = {
        "init": command_init,
        "inspect": command_inspect,
        "validate": command_validate,
        "approve": command_approve,
        "reopen": command_reopen,
        "checkpoint": command_checkpoint,
        "migrate-v4": command_migrate_v4,
        "assert-green": command_assert_green,
    }
    try:
        actions[args.command](args)
    except (OSError, UnicodeError, subprocess.SubprocessError, PlanError, LegacyV4Error, SafePlanIOError) as error:
        print(f"result=invalid\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

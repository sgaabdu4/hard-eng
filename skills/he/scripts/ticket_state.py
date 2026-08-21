#!/usr/bin/env python3
"""CLI state machine for Hard Eng parallel tickets: claim, checkpoint, release, board, gate."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

import checkout_policy
import execution_evidence
import plan_paths
import plan_state
import safe_plan_io
import slice_gate
import ticket_decompose
import ticket_parser
import ticket_worktree
import tracker_github
from ticket_parser import TicketError

MUTABLE_FIELDS = {"status", "active_slice", "completed_slices", "next_action", "delivery"}
TICKET_PATH = re.compile(rf"features/{plan_state.SLUG.pattern}/{plan_state.TICKET_MD.pattern}")
COMMANDS = ("decompose", "claim", "checkpoint", "release", "board", "assert-ticket-green", "sync-tracker")


def safe_plan_path(repo: Path, value: str | Path) -> Path:
    try:
        return plan_paths.safe_plan_path(repo, value)
    except safe_plan_io.SafePlanIOError as error:
        raise TicketError(str(error)) from error


def epic_plan_from_ticket(ticket_path: Path) -> Path:
    return ticket_path.parents[1] / "PLAN.md"


def epic_plan_path(primary: Path, value: str | None) -> Path:
    resolved = plan_state.resolve_plan(primary, value)
    if resolved is None:
        raise TicketError("no feature plan found; pass --epic-plan")
    return resolved


def epic_slug(epic_plan: Path) -> str:
    return epic_plan.parent.name


def list_tickets(epic_plan: Path) -> tuple[Path, ...]:
    tickets_dir = epic_plan.parent / "tickets"
    if not tickets_dir.is_dir():
        return ()
    paths = [path for path in tickets_dir.glob("T-*.md") if path.is_file() and not path.is_symlink()]

    def sort_key(path: Path) -> tuple[bool, int]:
        number = ticket_parser.ticket_number(path.stem)
        return (number is None, number or 0)

    return tuple(sorted(paths, key=sort_key))


def read_ticket(repo: Path, ticket_path: Path) -> tuple[str, int, dict[str, str], dict[str, str]]:
    data, mode = safe_plan_io.read_snapshot(repo, ticket_path.relative_to(repo))
    text = data.decode("utf-8")
    state = ticket_parser.parse_state(text)
    sections = ticket_parser.parse_sections(text)
    return text, mode, state, sections


def read_epic_for_tickets(repo: Path, epic_plan: Path) -> tuple[str, dict[str, str], dict[str, str]]:
    data, _mode = safe_plan_io.read_snapshot(repo, epic_plan.relative_to(repo))
    text = data.decode("utf-8")
    state = plan_state.parse_state(text)
    sections = plan_state.parse_sections(text)
    if state.get("state_version") != "2" or state.get("execution_mode") != "tickets":
        raise TicketError("epic is not decomposed into tickets (run ticket_state.py decompose first)")
    return text, state, sections


def resolve_ticket(epic_plan: Path, ticket_id: str) -> Path:
    ticket_parser.ticket_number(ticket_id)
    ticket_path = epic_plan.parent / "tickets" / f"{ticket_id}.md"
    if not ticket_path.is_file() or ticket_path.is_symlink():
        raise TicketError(f"ticket not found: {ticket_id}")
    return ticket_path


def resolve_ticket_path(primary: Path, value: str) -> Path:
    resolved = safe_plan_path(primary, value)
    relative = resolved.relative_to(primary)
    if not TICKET_PATH.fullmatch(relative.as_posix()):
        raise TicketError(f"--ticket must be a features/<slug>/tickets/T-<id>.md path, got: {value}")
    if not resolved.is_file() or resolved.is_symlink():
        raise TicketError(f"ticket not found: {value}")
    return resolved


def resolve_worktree(state: dict[str, str]) -> Path | None:
    if state["worktree"] == "none":
        return None
    return Path(state["worktree"])


def _dependencies_shipped(repo: Path, epic_plan: Path, depends_on: tuple[str, ...]) -> list[str]:
    unmet = []
    for dependency_id in depends_on:
        dependency_path = epic_plan.parent / "tickets" / f"{dependency_id}.md"
        if not dependency_path.is_file() or dependency_path.is_symlink():
            unmet.append(dependency_id)
            continue
        _, _, dependency_state, _ = read_ticket(repo, dependency_path)
        if dependency_state["status"] != "shipped":
            unmet.append(dependency_id)
    return unmet


def _claimable(state: dict[str, str]) -> bool:
    return state["status"] == "todo"


def _next_claimable(repo: Path, epic_plan: Path) -> Path | None:
    for path in list_tickets(epic_plan):
        _, _, state, _ = read_ticket(repo, path)
        if not _claimable(state):
            continue
        if _dependencies_shipped(repo, epic_plan, ticket_parser.parse_list(state["depends_on"])):
            continue
        return path
    return None


def _refresh_claim(
    worktree: Path, mirrored_plan: Path, epic_fingerprint: str, session_id: str, request_digest: str
) -> None:
    execution_evidence.refresh_execution_state(worktree, mirrored_plan, epic_fingerprint, session_id, request_digest)


def command_claim(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = epic_plan_path(primary, args.epic_plan)
    session_id, request_digest = plan_state.adapter_context(args)
    _epic_text, epic_state, epic_sections = read_epic_for_tickets(primary, epic_plan)
    epic_fingerprint = plan_state.frozen_fingerprint(epic_sections)
    if epic_fingerprint != epic_state["approval_fingerprint"]:
        raise TicketError("epic frozen sections no longer match the approved fingerprint")

    if args.ticket and args.next:
        raise TicketError("pass either --ticket or --next, not both")
    if args.next:
        next_path = _next_claimable(primary, epic_plan)
        if next_path is None:
            for key, value in board_summary(primary, epic_plan).items():
                print(f"board_{key}={value}")
            print("result=none")
            return
        ticket_path = next_path
    elif args.ticket:
        ticket_path = resolve_ticket(epic_plan, args.ticket)
    else:
        raise TicketError("claim requires --ticket or --next")

    with plan_state.plan_lock(primary, ticket_path):
        text, mode, state, _sections = read_ticket(primary, ticket_path)
        if args.expect_token is not None:
            plan_state.require_token(text, args.expect_token)
        if state["epic_fingerprint"] != epic_fingerprint:
            raise TicketError(f"ticket {state['ticket_id']} is bound to a stale epic fingerprint; run reconcile first")

        if args.refresh:
            worktree = resolve_worktree(state)
            if worktree is None or not worktree.is_dir():
                raise TicketError("--refresh requires an existing ticket worktree")
            mirrored_plan = worktree / "features" / epic_slug(epic_plan) / "PLAN.md"
            _refresh_claim(worktree, mirrored_plan, epic_fingerprint, session_id, request_digest)
            print(f"result=refreshed ticket={state['ticket_id']} worktree={worktree}")
            return

        if not _claimable(state):
            raise TicketError(f"ticket {state['ticket_id']} is not claimable (status={state['status']})")
        unmet = _dependencies_shipped(primary, epic_plan, ticket_parser.parse_list(state["depends_on"]))
        if unmet:
            raise TicketError(f"ticket {state['ticket_id']} depends on unshipped ticket(s): {', '.join(unmet)}")

        result = ticket_worktree.materialize(
            primary,
            epic_plan,
            _epic_text,
            state["ticket_id"],
            epic_slug(epic_plan),
            epic_fingerprint=epic_fingerprint,
            session_id=session_id,
            request_digest=request_digest,
        )
        changes = {
            "status": "claimed",
            "claimed_by": session_id or "unknown",
            "claimed_at": execution_evidence.utc_text(execution_evidence.utc_now()),
            "worktree": result["worktree"],
            "branch": result["branch"],
        }
        new_text = ticket_parser.render_state(text, changes)
        ticket_parser.validate_ticket_text(new_text)
        safe_plan_io.replace_if_unchanged(
            primary, ticket_path.relative_to(primary), text.encode("utf-8"), mode, new_text.encode("utf-8")
        )
    new_state = ticket_parser.parse_state(new_text)
    post_transition_hook(primary, epic_plan, ticket_path, dict(new_state), event="checkpoint")
    print(
        f"result=claimed ticket={new_state['ticket_id']} worktree={new_state['worktree']} branch={new_state['branch']}"
    )


def _parse_set_flags(pairs: list[str]) -> dict[str, str]:
    changes: dict[str, str] = {}
    for pair in pairs:
        key, separator, value = pair.partition("=")
        if not separator:
            raise TicketError(f"--set must be FIELD=VALUE, got: {pair}")
        changes[key] = value
    return changes


def command_checkpoint(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    ticket_path = resolve_ticket_path(primary, args.ticket)
    session_id, request_digest = plan_state.adapter_context(args)
    epic_plan = epic_plan_from_ticket(ticket_path)

    with plan_state.plan_lock(primary, ticket_path):
        text, mode, state, _sections = read_ticket(primary, ticket_path)
        plan_state.require_token(text, args.expect_token)
        changes = _parse_set_flags(args.set)
        unknown = set(changes) - MUTABLE_FIELDS
        if unknown:
            raise TicketError(f"cannot set immutable ticket field(s): {', '.join(sorted(unknown))}")
        if changes.get("status") == "cancelled":
            if not args.confirm_cancel:
                raise TicketError("cancelling a ticket requires --confirm-cancel")
            if state["ticket_id"] == "T-int":
                raise TicketError("T-int cannot be cancelled; it closes with the epic")
            if state["status"] != "todo":
                raise TicketError(
                    "checkpoint cancels todo tickets only; use release --force-release for claimed or building work"
                )
        target_status = changes.get("status")
        if (
            target_status is not None
            and target_status != state["status"]
            and target_status not in ticket_parser.TRANSITIONS[state["status"]]
        ):
            raise TicketError(f"illegal ticket transition: {state['status']} -> {target_status}")

        _epic_text, epic_state, _epic_sections = read_epic_for_tickets(primary, epic_plan)
        if state["epic_fingerprint"] != epic_state["approval_fingerprint"]:
            raise TicketError(f"ticket {state['ticket_id']} is bound to a stale epic fingerprint; run reconcile first")

        if target_status == "green":
            worktree = resolve_worktree(state)
            if worktree is None or not worktree.is_dir():
                raise TicketError("ticket worktree is required to reach green")
            mirrored_plan = worktree / "features" / epic_slug(epic_plan) / "PLAN.md"
            execution_evidence.validate_execution(
                worktree, mirrored_plan, state["epic_fingerprint"], session_id, request_digest
            )
            plan_worktree_id = execution_evidence.plan_id(mirrored_plan)
            error = slice_gate.checkpoint_error(worktree, mirrored_plan, plan_worktree_id, "full")
            if error:
                raise TicketError(error)
            changes["green_artifact"] = safe_plan_io.repository_artifact(worktree)

        new_text = ticket_parser.render_state(text, changes)
        ticket_parser.validate_ticket_text(new_text)
        safe_plan_io.replace_if_unchanged(
            primary, ticket_path.relative_to(primary), text.encode("utf-8"), mode, new_text.encode("utf-8")
        )
    new_state = ticket_parser.parse_state(new_text)
    post_transition_hook(primary, epic_plan, ticket_path, dict(new_state), event="checkpoint")
    print(f"result=checkpointed ticket={new_state['ticket_id']} status={new_state['status']}")


def command_release(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = epic_plan_path(primary, args.epic_plan)
    ticket_path = resolve_ticket(epic_plan, args.ticket)
    session_id, _request_digest = plan_state.adapter_context(args)

    with plan_state.plan_lock(primary, ticket_path):
        text, mode, state, _sections = read_ticket(primary, ticket_path)
        plan_state.require_token(text, args.expect_token)
        if state["status"] == "claimed":
            target_status = "todo"
        elif state["status"] == "building":
            if not args.force_release:
                raise TicketError(
                    f"ticket {state['ticket_id']} is building; pass --force-release to cancel in-progress work"
                )
            target_status = "cancelled"
        else:
            raise TicketError(f"ticket {state['ticket_id']} is not claimed or building (status={state['status']})")
        if not args.force_release and state["claimed_by"] != (session_id or "unknown"):
            raise TicketError(
                f"ticket {state['ticket_id']} is claimed by another session; pass --force-release to release it"
            )
        if target_status not in ticket_parser.TRANSITIONS[state["status"]]:
            raise TicketError(f"illegal ticket transition: {state['status']} -> {target_status}")

        worktree = resolve_worktree(state)
        try:
            if worktree is not None and worktree.is_dir():
                force = args.force_release or ticket_worktree.scaffolding_only_changes(worktree)
                ticket_worktree.remove_worktree(primary, worktree, force=force)
            if state["branch"].startswith("ticket/"):
                ticket_worktree.delete_branch(primary, state["branch"], force=args.force_release)
        except ticket_worktree.TicketWorktreeError as error:
            if args.force_release:
                raise TicketError(str(error)) from error
            raise TicketError(f"{error}; pass --force-release to discard in-progress ticket work") from error

        if target_status == "todo":
            changes = {
                "status": "todo",
                "claimed_by": "none",
                "claimed_at": "none",
                "worktree": "none",
                "branch": "none",
            }
        else:
            changes = {"status": "cancelled", "worktree": "none", "branch": "none"}
        new_text = ticket_parser.render_state(text, changes)
        ticket_parser.validate_ticket_text(new_text)
        safe_plan_io.replace_if_unchanged(
            primary, ticket_path.relative_to(primary), text.encode("utf-8"), mode, new_text.encode("utf-8")
        )
    new_state = ticket_parser.parse_state(new_text)
    post_transition_hook(primary, epic_plan, ticket_path, dict(new_state), event="checkpoint")
    print(f"result=released ticket={new_state['ticket_id']} status={new_state['status']}")


def board_summary(repo: Path, epic_plan: Path) -> dict[str, object]:
    counts = {status: 0 for status in ticket_parser.STATUSES}
    errors: list[str] = []
    stale_worktrees = 0
    total = 0
    for path in list_tickets(epic_plan):
        try:
            _, _, state, _ = read_ticket(repo, path)
        except (TicketError, OSError, UnicodeError) as error:
            errors.append(f"{path.name}: {error}")
            continue
        counts[state["status"]] += 1
        total += 1
        if (
            state["status"] in {"claimed", "building"}
            and state["worktree"] != "none"
            and not Path(state["worktree"]).is_dir()
        ):
            stale_worktrees += 1
    summary: dict[str, object] = {"total": total}
    for status in ticket_parser.STATUSES:
        summary[f"count_{status}"] = counts[status]
    summary["stale_worktrees"] = stale_worktrees
    summary["errors"] = len(errors)
    summary["error_detail"] = "; ".join(errors) if errors else "none"
    return summary


def command_board(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = epic_plan_path(primary, args.epic_plan)
    for path in list_tickets(epic_plan):
        try:
            _, _, state, _ = read_ticket(primary, path)
        except (TicketError, OSError, UnicodeError) as error:
            print(f"ticket_error={path.name}: {error}")
            continue
        print(
            f"ticket={state['ticket_id']} status={state['status']} depends_on={state['depends_on']} "
            f"slices={state['slices']} worktree={state['worktree']} tracker_ref={state['tracker_ref']}"
        )
    for key, value in board_summary(primary, epic_plan).items():
        print(f"board_{key}={value}")


def epic_green_gate_error(repo: Path, path: Path, state: Mapping[str, str]) -> str | None:
    tickets = list_tickets(path)
    if not tickets:
        return "epic has no tickets; run skills/he/scripts/ticket_state.py decompose first"
    shipped_slices: list[str] = []
    covered: set[str] = set()
    integration: dict[str, str] | None = None
    blockers: list[str] = []
    for ticket_path in tickets:
        try:
            _, _, row, _ = read_ticket(repo, ticket_path)
        except (TicketError, OSError, UnicodeError) as error:
            return f"cannot verify ticket {ticket_path.name}: {error}"
        if row["ticket_id"] == "T-int":
            integration = row
            continue
        if row["status"] == "shipped":
            shipped_slices.extend(ticket_parser.parse_list(row["slices"]))
            covered.update(ticket_parser.parse_list(row["covers"]))
        elif row["status"] != "cancelled":
            blockers.append(row["ticket_id"])
    if blockers:
        return f"tickets not yet shipped or cancelled: {', '.join(blockers)}"
    if integration is None:
        return "integration ticket T-int is missing"
    if integration["status"] not in {"green", "shipped"}:
        return f"integration ticket T-int is not green (status={integration['status']})"
    covered.update(ticket_parser.parse_list(integration["covers"]))
    numbers = sorted(ticket_parser.slice_number(item) for item in shipped_slices)
    if numbers != list(range(1, len(numbers) + 1)):
        return (
            "shipped tickets do not cover the full slice partition; amend replacement tickets for the cancelled slices"
        )
    try:
        pending = plan_state.completed_numbers(state["completed_slices"])
    except plan_state.PlanError as error:
        return str(error)
    if list(pending) != numbers:
        return "completed_slices must equal the shipped ticket slice partition"
    try:
        epic_sections = plan_state.parse_sections(path.read_text(encoding="utf-8"))
        ordinals = ticket_decompose.acceptance_ordinals(epic_sections)
    except (OSError, UnicodeError, plan_state.PlanError, TicketError) as error:
        return f"cannot verify acceptance coverage: {error}"
    missing = [ordinal for ordinal in ordinals if ordinal not in covered]
    if missing:
        return f"acceptance ordinals not re-covered by shipped tickets or T-int: {', '.join(missing)}"
    return None


def command_assert_ticket_green(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    ticket_path = resolve_ticket_path(primary, args.ticket)
    _, _, state, _ = read_ticket(primary, ticket_path)
    if state["status"] != "green":
        raise TicketError(f"ticket {state['ticket_id']} is not green (status={state['status']})")
    epic_plan = epic_plan_from_ticket(ticket_path)
    worktree = resolve_worktree(state)
    verified = "no"
    if worktree is not None and worktree.is_dir():
        mirrored_plan = worktree / "features" / epic_slug(epic_plan) / "PLAN.md"
        plan_worktree_id = execution_evidence.plan_id(mirrored_plan)
        error = slice_gate.checkpoint_error(worktree, mirrored_plan, plan_worktree_id, "full")
        if error:
            raise TicketError(error)
        verified = "yes"
    print(f"result=green ticket={state['ticket_id']} green_artifact={state['green_artifact']} verified={verified}")


def read_tracker_config(repo: Path) -> tuple[str, str | None] | None:
    gates_path = repo / "hard-eng.gates.json"
    if not gates_path.is_file() or gates_path.is_symlink():
        return None
    try:
        data = json.loads(gates_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    tracker = data.get("tracker") if isinstance(data, dict) else None
    if not isinstance(tracker, dict) or tracker.get("adapter") != "github":
        return None
    repository = tracker.get("repository")
    if not isinstance(repository, str) or "/" not in repository:
        return None
    project = tracker.get("project")
    return repository, project if isinstance(project, str) else None


def _record_tracker_ref(repo: Path, ticket_path: Path, tracker_ref: str) -> None:
    try:
        with plan_state.plan_lock(repo, ticket_path):
            data, mode = safe_plan_io.read_snapshot(repo, ticket_path.relative_to(repo))
            new_text = ticket_parser.render_state(data.decode("utf-8"), {"tracker_ref": tracker_ref})
            ticket_parser.validate_ticket_text(new_text)
            safe_plan_io.replace_if_unchanged(repo, ticket_path.relative_to(repo), data, mode, new_text.encode("utf-8"))
    except (OSError, UnicodeError, TicketError, safe_plan_io.SafePlanIOError) as error:
        print(f"tracker: recording tracker_ref failed (best-effort, continuing): {error}", file=sys.stderr)


def post_transition_hook(
    repo: Path, epic_plan: Path, ticket_path: Path, ticket: Mapping[str, object], *, event: str
) -> None:
    config = read_tracker_config(repo)
    if config is None or not tracker_github.gh_available():
        return
    repository, project = config
    ticket_id = str(ticket["ticket_id"])
    title = f"{ticket_id}: {epic_slug(epic_plan)}"
    goal_text = str(ticket.get("goal_text", ""))
    tracker_ref = str(ticket.get("tracker_ref", "none"))

    if event == "created" or (event == "amended" and tracker_ref == "none"):
        ref = tracker_github.best_effort(
            lambda: tracker_github.create_ticket(repository, ticket_id, title, goal_text), label="create-ticket"
        )
        if isinstance(ref, str):
            tracker_github.best_effort(
                lambda: tracker_github.project_add(repository, project, ref), label="project-add"
            )
            _record_tracker_ref(repo, ticket_path, ref)
        return

    if tracker_ref == "none":
        return
    status = str(ticket.get("status", ""))
    if event == "checkpoint" and status:
        tracker_github.best_effort(
            lambda: tracker_github.update_status(repository, tracker_ref, status), label="update-status"
        )
        if status == "shipped":
            delivery = str(ticket.get("delivery", "none"))
            if delivery != "none":
                pr_url = delivery.split("@", 1)[0]
                tracker_github.best_effort(
                    lambda: tracker_github.link_pr(repository, tracker_ref, pr_url), label="link-pr"
                )
            tracker_github.best_effort(
                lambda: tracker_github.close_ticket(repository, tracker_ref, "shipped"), label="close-ticket"
            )
    elif event == "reconciled" and status == "cancelled":
        tracker_github.best_effort(
            lambda: tracker_github.close_ticket(repository, tracker_ref, "cancelled: superseded by replan"),
            label="close-cancelled-ticket",
        )


def command_sync_tracker(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = epic_plan_path(primary, args.epic_plan)
    config = read_tracker_config(primary)
    if config is None:
        print("result=synced trackers=not-configured")
        return
    repository, _project = config
    paths = list(list_tickets(epic_plan))
    rows = [read_ticket(primary, path) for path in paths]

    if args.pull:
        refs = tuple(row[2]["tracker_ref"] for row in rows if row[2]["tracker_ref"] != "none")
        for drift in tracker_github.pull_drift(repository, refs):
            local = next((row[2]["status"] for row in rows if row[2]["tracker_ref"] == drift["tracker_ref"]), "unknown")
            print(f"drift ticket_ref={drift['tracker_ref']} remote_state={drift['remote_state']} local_status={local}")
        return

    for path, (_text, _mode, state, _sections) in zip(paths, rows):
        event = "amended" if state["tracker_ref"] == "none" else "checkpoint"
        post_transition_hook(primary, epic_plan, path, dict(state), event=event)
    print("result=synced")


def _dispatch_decompose(args: argparse.Namespace) -> None:
    if args.amend and args.reconcile:
        raise TicketError("pass at most one of --amend/--reconcile")
    if args.reconcile:
        ticket_decompose.command_reconcile(args)
    elif args.amend:
        ticket_decompose.command_amend(args)
    else:
        ticket_decompose.command_decompose(args)


def main() -> int:
    args = ticket_parser.build(COMMANDS).parse_args()
    actions = {
        "decompose": _dispatch_decompose,
        "claim": command_claim,
        "checkpoint": command_checkpoint,
        "release": command_release,
        "board": command_board,
        "assert-ticket-green": command_assert_ticket_green,
        "sync-tracker": command_sync_tracker,
    }
    try:
        actions[args.command](args)
    except (
        OSError,
        UnicodeError,
        subprocess.SubprocessError,
        TicketError,
        ticket_worktree.TicketWorktreeError,
        tracker_github.TrackerError,
        safe_plan_io.SafePlanIOError,
        execution_evidence.EvidenceError,
        plan_state.PlanError,
        slice_gate.SliceGateError,
    ) as error:
        print(f"result=invalid\nerror={error}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

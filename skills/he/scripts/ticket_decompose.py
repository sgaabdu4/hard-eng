#!/usr/bin/env python3
"""Decompose/amend/reconcile validation and orchestration for Hard Eng parallel tickets.

Imported by ticket_state.py's main(); carries no CLI entry point of its own.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import TypedDict

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

import checkout_policy
import execution_evidence
import plan_state
import safe_plan_io
import ticket_parser
import ticket_state
import ticket_template
from ticket_parser import TicketError

TICKET_ID_PATTERN = re.compile(r"[A-Za-z0-9_/.:-]+")


class TicketSpec(TypedDict):
    ticket_id: str
    depends_on: tuple[str, ...]
    slices: tuple[str, ...]
    covers: tuple[str, ...]
    touches: tuple[str, ...]
    goal_text: str
    acceptance_text: str


def parse_stdin_tickets() -> list[TicketSpec]:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise TicketError(f"stdin is not valid JSON: {error}") from error
    entries = payload.get("tickets") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        raise TicketError("stdin must be a JSON object with a nonempty 'tickets' array")
    tickets = [_normalize_ticket_entry(entry) for entry in entries]
    ids = [ticket["ticket_id"] for ticket in tickets]
    if len(set(ids)) != len(ids):
        raise TicketError("stdin ticket ids must be unique")
    if "T-int" in ids:
        raise TicketError("T-int is synthesized by decompose and must not appear in stdin")
    return tickets


def _string_list(value: object, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise TicketError(f"{label} must be a list of nonempty strings")
    return tuple(item.strip() for item in value)


def _normalize_ticket_entry(entry: object) -> TicketSpec:
    if not isinstance(entry, dict):
        raise TicketError("each ticket entry must be a JSON object")
    ticket_id = entry.get("ticket_id")
    if not isinstance(ticket_id, str) or ticket_parser.ticket_number(ticket_id) is None:
        raise TicketError(f"invalid or missing ticket_id: {ticket_id!r}")
    goal_text = entry.get("goal_text")
    acceptance_text = entry.get("acceptance_text")
    if not isinstance(goal_text, str) or not goal_text.strip():
        raise TicketError(f"{ticket_id}: goal_text must be nonempty")
    if not isinstance(acceptance_text, str) or not acceptance_text.strip():
        raise TicketError(f"{ticket_id}: acceptance_text must be nonempty")
    slices = _string_list(entry.get("slices"), f"{ticket_id}.slices")
    covers = _string_list(entry.get("covers"), f"{ticket_id}.covers")
    depends_on = _string_list(entry.get("depends_on"), f"{ticket_id}.depends_on")
    for slice_id in slices:
        if not ticket_parser.SLICE.fullmatch(slice_id):
            raise TicketError(f"{ticket_id}: invalid slice id {slice_id!r}")
    for ordinal in covers:
        if not ticket_parser.ORDINAL.fullmatch(ordinal):
            raise TicketError(f"{ticket_id}: invalid acceptance ordinal {ordinal!r}")
    for dependency in depends_on:
        ticket_parser.ticket_number(dependency)
    return {
        "ticket_id": ticket_id,
        "depends_on": depends_on,
        "slices": slices,
        "covers": covers,
        "touches": _string_list(entry.get("touches"), f"{ticket_id}.touches"),
        "goal_text": goal_text.strip(),
        "acceptance_text": acceptance_text.strip(),
    }


def acceptance_ordinals(epic_sections: dict[str, str]) -> tuple[str, ...]:
    text = epic_sections.get("Acceptance examples", "")
    count = sum(1 for line in text.splitlines() if line.startswith("- "))
    if count == 0:
        raise TicketError("epic Acceptance examples section has no top-level list items")
    return tuple(f"A-{index}" for index in range(1, count + 1))


def _integration_acceptance_text(ordinals: tuple[str, ...], integration_only: tuple[str, ...]) -> str:
    lines = [
        f"- Given every constituent ticket has shipped, when acceptance ordinal {ordinal} is re-verified "
        "end to end on the integrated tree, then it holds."
        + (" (integration-only coverage)" if ordinal in integration_only else "")
        for ordinal in ordinals
    ]
    lines.append(
        "- Given every constituent ticket has shipped, when the full gate runs on the integrated tree, then it passes."
    )
    return "\n".join(lines)


def synthesize_integration_ticket(tickets: list[TicketSpec], ordinals: tuple[str, ...]) -> TicketSpec:
    covered: set[str] = set()
    for ticket in tickets:
        covered.update(ticket["covers"])
    integration_only = tuple(ordinal for ordinal in ordinals if ordinal not in covered)
    return {
        "ticket_id": "T-int",
        "depends_on": tuple(ticket["ticket_id"] for ticket in tickets),
        "slices": (),
        "covers": integration_only,
        "touches": (),
        "goal_text": (
            "Integrate the assembled epic once every constituent ticket has shipped; re-verify every "
            "epic acceptance ordinal on the integrated tree."
        ),
        "acceptance_text": _integration_acceptance_text(ordinals, integration_only),
    }


def validate_partition(tickets: list[TicketSpec]) -> tuple[str, ...]:
    owner: dict[str, str] = {}
    for ticket in tickets:
        for slice_id in ticket["slices"]:
            if slice_id in owner:
                raise TicketError(f"slice {slice_id} claimed by both {owner[slice_id]} and {ticket['ticket_id']}")
            owner[slice_id] = ticket["ticket_id"]
    if not owner:
        raise TicketError("no ticket declares any slice")
    numbers = sorted(ticket_parser.slice_number(slice_id) for slice_id in owner)
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        missing = sorted(set(expected) - set(numbers))
        raise TicketError("slice partition has gaps: " + ", ".join(f"S-{n}" for n in missing))
    return tuple(f"S-{n}" for n in expected)


def validate_acceptance_coverage(tickets: list[TicketSpec], ordinals: tuple[str, ...]) -> None:
    covered: set[str] = set()
    for ticket in tickets:
        covered.update(ticket["covers"])
    missing = [ordinal for ordinal in ordinals if ordinal not in covered]
    if missing:
        raise TicketError("acceptance ordinals not covered by any ticket: " + ", ".join(missing))


def validate_dag(tickets: list[TicketSpec]) -> None:
    known = {ticket["ticket_id"] for ticket in tickets}
    edges = {ticket["ticket_id"]: ticket["depends_on"] for ticket in tickets}
    for ticket_id, deps in edges.items():
        unknown = [dep for dep in deps if dep not in known]
        if unknown:
            raise TicketError(f"{ticket_id} depends on unknown ticket(s): {', '.join(unknown)}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ticket_id: str, path: tuple[str, ...]) -> None:
        if ticket_id in visiting:
            raise TicketError("depends_on cycle: " + " -> ".join((*path, ticket_id)))
        if ticket_id in visited:
            return
        visiting.add(ticket_id)
        for dependency in edges[ticket_id]:
            visit(dependency, (*path, ticket_id))
        visiting.discard(ticket_id)
        visited.add(ticket_id)

    for ticket_id in edges:
        visit(ticket_id, ())


def _reachable(ticket_id: str, edges: dict[str, tuple[str, ...]]) -> set[str]:
    seen: set[str] = set()
    stack = list(edges.get(ticket_id, ()))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(edges.get(current, ()))
    return seen


def _dependency_ordered(first: str, second: str, edges: dict[str, tuple[str, ...]]) -> bool:
    return second in _reachable(first, edges) or first in _reachable(second, edges)


def _touches_overlap(tickets: list[TicketSpec]) -> tuple[list[str], list[str]]:
    edges = {ticket["ticket_id"]: ticket["depends_on"] for ticket in tickets}
    hard_errors: list[str] = []
    soft_warnings: list[str] = []
    for index, first in enumerate(tickets):
        for second in tickets[index + 1 :]:
            if _dependency_ordered(first["ticket_id"], second["ticket_id"], edges):
                continue
            first_paths = {Path(item) for item in first["touches"]}
            second_paths = {Path(item) for item in second["touches"]}
            exact = sorted(str(item) for item in first_paths & second_paths)
            if exact:
                hard_errors.append(f"{first['ticket_id']} and {second['ticket_id']} both touch: {', '.join(exact)}")
                continue
            shared_dirs = sorted(
                str(item) for item in {p.parent for p in first_paths} & {p.parent for p in second_paths}
            )
            if shared_dirs:
                soft_warnings.append(
                    f"{first['ticket_id']} and {second['ticket_id']} touch the same directory: "
                    + ", ".join(shared_dirs)
                )
    return hard_errors, soft_warnings


def validate_touches(tickets: list[TicketSpec]) -> tuple[str, ...]:
    hard_errors, soft_warnings = _touches_overlap(tickets)
    if hard_errors:
        raise TicketError("; ".join(hard_errors))
    return tuple(soft_warnings)


def parallel_safe_count(tickets: list[TicketSpec], warnings: tuple[str, ...]) -> int:
    roots = [ticket for ticket in tickets if not ticket["depends_on"]]
    conflicts: dict[str, set[str]] = {ticket["ticket_id"]: set() for ticket in roots}
    for index, first in enumerate(roots):
        for second in roots[index + 1 :]:
            first_paths = set(first["touches"])
            second_paths = set(second["touches"])
            first_dirs = {str(Path(item).parent) for item in first_paths}
            second_dirs = {str(Path(item).parent) for item in second_paths}
            if (first_paths & second_paths) or (first_dirs & second_dirs):
                conflicts[first["ticket_id"]].add(second["ticket_id"])
                conflicts[second["ticket_id"]].add(first["ticket_id"])
    del warnings
    remaining = {ticket["ticket_id"] for ticket in roots}
    while True:
        degrees = {ticket_id: len(conflicts[ticket_id] & remaining) for ticket_id in remaining}
        worst = max(degrees, key=lambda ticket_id: degrees[ticket_id], default=None)
        if worst is None or degrees[worst] == 0:
            return len(remaining)
        remaining.discard(worst)


def _list_field(values: tuple[str, ...]) -> str:
    return ",".join(values) if values else "none"


def _touches_text(paths: tuple[str, ...]) -> str:
    if not paths:
        return "- (none)"
    return "\n".join(f"- `{path}`" for path in paths)


def _render_ticket(ticket: TicketSpec, epic_plan_id: str, epic_fingerprint: str) -> str:
    return ticket_template.render(
        ticket["ticket_id"],
        epic_plan_id,
        epic_fingerprint,
        _list_field(ticket["depends_on"]),
        _list_field(ticket["slices"]),
        _list_field(ticket["covers"]),
        ticket["goal_text"],
        ticket["acceptance_text"],
        _touches_text(ticket["touches"]),
        ticket_parser.TICKET_STATE_START,
        ticket_parser.TICKET_STATE_END,
    )


def _touches_from_section(section_text: str) -> tuple[str, ...]:
    paths = []
    for line in section_text.splitlines():
        match = re.match(r"-\s*`([^`]+)`", line.strip())
        if match:
            paths.append(match.group(1))
    return tuple(paths)


def _ticket_dict_from_state(state: dict[str, str], sections: dict[str, str]) -> TicketSpec:
    return {
        "ticket_id": state["ticket_id"],
        "depends_on": ticket_parser.parse_list(state["depends_on"]),
        "slices": ticket_parser.parse_list(state["slices"]),
        "covers": ticket_parser.parse_list(state["covers"]),
        "touches": _touches_from_section(sections.get("Touches", "")),
        "goal_text": sections.get("Goal", ""),
        "acceptance_text": sections.get("Acceptance", ""),
    }


def _update_ticket_fields(primary: Path, ticket_path: Path, changes: dict[str, str]) -> dict[str, str]:
    data, mode = safe_plan_io.read_snapshot(primary, ticket_path.relative_to(primary))
    ticket_text = data.decode("utf-8")
    new_text = ticket_parser.render_state(ticket_text, changes)
    ticket_parser.validate_ticket_text(new_text)
    safe_plan_io.replace_if_unchanged(primary, ticket_path.relative_to(primary), data, mode, new_text.encode("utf-8"))
    return ticket_parser.parse_state(new_text)


def command_decompose(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = ticket_state.epic_plan_path(primary, args.epic_plan)
    with plan_state.plan_lock(primary, epic_plan):
        relative = epic_plan.relative_to(primary)
        data, mode = safe_plan_io.read_snapshot(primary, relative)
        text = data.decode("utf-8")
        plan_state.require_token(text, args.expect_token)
        state = plan_state.parse_state(text)
        sections = plan_state.parse_sections(text)
        if state["lifecycle_status"] != "build-ready":
            raise TicketError("decompose requires a build-ready epic PLAN")
        if state["approval_status"] != "approved":
            raise TicketError("decompose requires an approved epic PLAN")
        fingerprint = plan_state.frozen_fingerprint(sections)
        if fingerprint != state["approval_fingerprint"]:
            raise TicketError("approved frozen bytes changed; resolve via plan_state.py first")
        execution_evidence.validate_execution(primary, epic_plan, fingerprint)
        if checkout_policy.checkout_policy(primary) != "selectable":
            raise TicketError("decompose requires checkout_policy = selectable")

        tickets_dir = epic_plan.parent / "tickets"
        if tickets_dir.exists() or tickets_dir.is_symlink():
            raise TicketError("tickets directory already exists; use --amend or --reconcile instead")

        work_tickets = parse_stdin_tickets()
        ordinals = acceptance_ordinals(sections)
        integration_ticket = synthesize_integration_ticket(work_tickets, ordinals)
        all_tickets = [*work_tickets, integration_ticket]

        validate_partition(all_tickets)
        validate_acceptance_coverage(all_tickets, ordinals)
        validate_dag(all_tickets)
        warnings = validate_touches(all_tickets)
        safe_count = parallel_safe_count(all_tickets, warnings)

        if args.dry_run:
            print(f"result=dry-run tickets={len(work_tickets)} parallel_safe={safe_count}")
            for warning in warnings:
                print(f"warning={warning}")
            return

        rendered = {
            ticket["ticket_id"]: _render_ticket(ticket, state["plan_id"], fingerprint) for ticket in all_tickets
        }
        new_epic_text = plan_state.render_state(
            text,
            {
                "state_version": "2",
                "execution_mode": "tickets",
                "lifecycle_status": "building",
                "next_action": f"run skills/he/scripts/ticket_state.py board --epic-plan {relative}",
            },
        )
        plan_state.validate_text(new_epic_text)

        nonce = uuid.uuid4().hex[:8]
        staging = epic_plan.parent / f".tickets-staging-{nonce}"
        staging.mkdir(parents=True)
        try:
            for ticket_id, markdown in rendered.items():
                ticket_file = staging / f"{ticket_id}.md"
                ticket_file.write_bytes(markdown.encode("utf-8"))
                ticket_file.chmod(0o644)
            safe_plan_io.replace_if_unchanged(primary, relative, data, mode, new_epic_text.encode("utf-8"))
            os.rename(staging, tickets_dir)
        except BaseException:
            if staging.is_dir():
                for child in staging.iterdir():
                    child.unlink()
                staging.rmdir()
            raise
    for ticket in all_tickets:
        ticket_path = tickets_dir / f"{ticket['ticket_id']}.md"
        ticket_state.post_transition_hook(primary, epic_plan, ticket_path, ticket, event="created")
    print(f"result=decomposed tickets={len(all_tickets)} parallel_safe={safe_count}")


def command_amend(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = ticket_state.epic_plan_path(primary, args.epic_plan)
    with plan_state.plan_lock(primary, epic_plan):
        relative = epic_plan.relative_to(primary)
        data, _mode = safe_plan_io.read_snapshot(primary, relative)
        text = data.decode("utf-8")
        plan_state.require_token(text, args.expect_token)
        state = plan_state.parse_state(text)
        sections = plan_state.parse_sections(text)
        if state.get("state_version") != "2" or state.get("execution_mode") != "tickets":
            raise TicketError("amend requires an epic already decomposed into tickets")
        fingerprint = plan_state.frozen_fingerprint(sections)
        if fingerprint != state["approval_fingerprint"]:
            raise TicketError("amend requires the epic's frozen sections to be currently approved")
        execution_evidence.validate_execution(primary, epic_plan, fingerprint)

        existing_paths = list(ticket_state.list_tickets(epic_plan))
        existing_rows = [ticket_state.read_ticket(primary, path) for path in existing_paths]
        existing_live = [row for row in existing_rows if row[2]["status"] != "cancelled"]
        existing_ids = {row[2]["ticket_id"] for row in existing_rows}
        integration_row = next((row for row in existing_live if row[2]["ticket_id"] == "T-int"), None)
        if integration_row is None:
            raise TicketError("integration ticket T-int is missing; reconcile the epic first")
        if integration_row[2]["status"] != "todo":
            raise TicketError("release T-int before amending")

        new_tickets = parse_stdin_tickets()
        for ticket in new_tickets:
            if ticket["ticket_id"] in existing_ids:
                raise TicketError(f"amend ticket id already exists: {ticket['ticket_id']}")

        live_specs = [
            _ticket_dict_from_state(row_state, row_sections) for _text, _mode2, row_state, row_sections in existing_live
        ]
        integration = next(spec for spec in live_specs if spec["ticket_id"] == "T-int")
        work_ids = tuple(spec["ticket_id"] for spec in live_specs if spec["ticket_id"] != "T-int")
        new_ids = tuple(ticket["ticket_id"] for ticket in new_tickets)
        integration["depends_on"] = (*work_ids, *new_ids)
        combined = live_specs + new_tickets
        ordinals = acceptance_ordinals(sections)
        validate_partition(combined)
        validate_acceptance_coverage(combined, ordinals)
        validate_dag(combined)
        validate_touches(combined)

        _update_ticket_fields(
            primary, epic_plan.parent / "tickets" / "T-int.md", {"depends_on": _list_field(integration["depends_on"])}
        )
        for ticket in new_tickets:
            markdown = _render_ticket(ticket, state["plan_id"], fingerprint)
            ticket_path = epic_plan.parent / "tickets" / f"{ticket['ticket_id']}.md"
            safe_plan_io.create_new(primary, ticket_path.relative_to(primary), markdown.encode("utf-8"), 0o644)
    for ticket in new_tickets:
        ticket_path = epic_plan.parent / "tickets" / f"{ticket['ticket_id']}.md"
        ticket_state.post_transition_hook(primary, epic_plan, ticket_path, ticket, event="amended")
    print(f"result=amended tickets={len(new_tickets)}")


def command_reconcile(args: argparse.Namespace) -> None:
    repo = safe_plan_io.repo_root(args.repo)
    primary = checkout_policy.primary_checkout(repo)
    epic_plan = ticket_state.epic_plan_path(primary, args.epic_plan)
    with plan_state.plan_lock(primary, epic_plan):
        data, _mode = safe_plan_io.read_snapshot(primary, epic_plan.relative_to(primary))
        text = data.decode("utf-8")
        plan_state.require_token(text, args.expect_token)
        state = plan_state.parse_state(text)
        sections = plan_state.parse_sections(text)
        if state.get("state_version") != "2" or state.get("execution_mode") != "tickets":
            raise TicketError("reconcile requires an epic already decomposed into tickets")
        if state["approval_status"] != "approved":
            raise TicketError("reconcile requires a currently approved epic PLAN")
        new_fingerprint = plan_state.frozen_fingerprint(sections)
        if new_fingerprint != state["approval_fingerprint"]:
            raise TicketError("reconcile requires the epic's frozen sections to be currently approved")
        execution_evidence.validate_execution(primary, epic_plan, new_fingerprint)
        new_ordinals = acceptance_ordinals(sections)

        paths = list(ticket_state.list_tickets(epic_plan))
        rows = [ticket_state.read_ticket(primary, path) for path in paths]
        if not any(row[2]["ticket_id"] == "T-int" for row in rows):
            raise TicketError("integration ticket T-int is missing")

        verdicts: dict[str, str] = {}
        for _ticket_text, _mode2, row_state, _row_sections in rows:
            ticket_id = row_state["ticket_id"]
            if ticket_id == "T-int":
                continue
            if row_state["status"] == "cancelled" or row_state["epic_fingerprint"] == new_fingerprint:
                verdicts[ticket_id] = "unaffected"
            elif row_state["status"] == "shipped":
                verdicts[ticket_id] = "survive"
            else:
                ticket_covers = ticket_parser.parse_list(row_state["covers"])
                verdicts[ticket_id] = "survive" if all(o in new_ordinals for o in ticket_covers) else "cancelled"
        verdicts["T-int"] = "survive"

        work_covered: set[str] = set()
        work_live_ids: list[str] = []
        cleanups: list[str] = []
        for _ticket_text, _mode2, row_state, _row_sections in rows:
            ticket_id = row_state["ticket_id"]
            if ticket_id == "T-int" or row_state["status"] == "cancelled" or verdicts[ticket_id] == "cancelled":
                continue
            work_live_ids.append(ticket_id)
            work_covered.update(ticket_parser.parse_list(row_state["covers"]))
        integration_covers = tuple(ordinal for ordinal in new_ordinals if ordinal not in work_covered)
        gaps = list(integration_covers)

        if args.dry_run:
            for ticket_id, verdict in verdicts.items():
                print(f"ticket={ticket_id} verdict={verdict}")
            for gap in gaps:
                print(f"gap={gap}")
            return

        hooks: list[tuple[Path, dict[str, str], str]] = []
        for (ticket_text, ticket_mode, row_state, _row_sections), path in zip(rows, paths):
            ticket_id = row_state["ticket_id"]
            if ticket_id == "T-int":
                continue
            verdict = verdicts[ticket_id]
            if verdict == "unaffected":
                continue
            if verdict == "cancelled":
                if row_state["worktree"] != "none":
                    cleanups.append(row_state["worktree"])
                changes = {"status": "cancelled", "worktree": "none", "branch": "none", "green_artifact": "none"}
            else:
                changes = {"epic_fingerprint": new_fingerprint}
            new_ticket_text = ticket_parser.render_state(ticket_text, changes)
            ticket_parser.validate_ticket_text(new_ticket_text)
            safe_plan_io.replace_if_unchanged(
                primary,
                path.relative_to(primary),
                ticket_text.encode("utf-8"),
                ticket_mode,
                new_ticket_text.encode("utf-8"),
            )
            hooks.append((path, ticket_parser.parse_state(new_ticket_text), "reconciled"))

        integration_path = epic_plan.parent / "tickets" / "T-int.md"
        integration_state = _update_ticket_fields(
            primary,
            integration_path,
            {
                "epic_fingerprint": new_fingerprint,
                "depends_on": _list_field(tuple(work_live_ids)),
                "covers": _list_field(integration_covers),
            },
        )
        hooks.append((integration_path, integration_state, "reconciled"))
    for path, row_state, event in hooks:
        ticket_state.post_transition_hook(primary, epic_plan, path, dict(row_state), event=event)
    for ticket_id, verdict in verdicts.items():
        print(f"ticket={ticket_id} verdict={verdict}")
    for worktree in cleanups:
        print(f"cleanup={worktree}")
    for gap in gaps:
        print(f"gap={gap}")
    print("result=reconciled")

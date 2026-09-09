#!/usr/bin/env python3
"""Ticket state parsing/validation and CLI parser construction for Hard Eng parallel tickets."""

from __future__ import annotations

import argparse
import re
from collections.abc import Collection


class TicketError(ValueError):
    """Invalid ticket or transition."""


TICKET_STATE_START = "<!-- hard-eng-ticket-state:v1 -->"
TICKET_STATE_END = "<!-- /hard-eng-ticket-state -->"
TICKET_KEYS = (
    "state_version",
    "ticket_id",
    "epic_plan_id",
    "epic_fingerprint",
    "status",
    "depends_on",
    "slices",
    "covers",
    "active_slice",
    "completed_slices",
    "claimed_by",
    "claimed_at",
    "worktree",
    "branch",
    "green_artifact",
    "delivery",
    "tracker_ref",
    "next_action",
)
TICKET_SECTIONS = ("Goal", "Acceptance", "Touches")
STATUSES = ("todo", "claimed", "building", "green", "shipped", "cancelled")
TRANSITIONS = {
    "todo": {"claimed", "cancelled"},
    "claimed": {"building", "todo", "cancelled"},
    "building": {"green", "cancelled"},
    "green": {"shipped"},
    "shipped": set(),
    "cancelled": set(),
}
TICKET_ID = re.compile(r"T-(int|[1-9][0-9]*)")
SLICE = re.compile(r"S-([1-9][0-9]*)")
ORDINAL = re.compile(r"A-([1-9][0-9]*)")
FINGERPRINT = re.compile(r"sha256:[0-9a-f]{64}")
TICKET_ROW = re.compile(r"^- ([a-z_]+) = (.*)$")


def ticket_number(ticket_id: str) -> int | None:
    match = TICKET_ID.fullmatch(ticket_id)
    if not match:
        raise TicketError(f"invalid ticket id: {ticket_id}")
    value = match.group(1)
    return None if value == "int" else int(value)


def slice_number(slice_id: str) -> int:
    match = SLICE.fullmatch(slice_id)
    if not match:
        raise TicketError(f"invalid slice id: {slice_id}")
    return int(match.group(1))


def state_bounds(text: str) -> tuple[int, int]:
    if text.count(TICKET_STATE_START) != 1 or text.count(TICKET_STATE_END) != 1:
        raise TicketError("requires exactly one v1 ticket state block")
    start = text.index(TICKET_STATE_START) + len(TICKET_STATE_START)
    end = text.index(TICKET_STATE_END, start)
    if end <= start:
        raise TicketError("ticket state block is malformed")
    return start, end


def parse_state(text: str) -> dict[str, str]:
    start, end = state_bounds(text)
    rows: dict[str, str] = {}
    for raw in text[start:end].strip().splitlines():
        match = TICKET_ROW.fullmatch(raw.strip())
        if not match:
            raise TicketError(f"invalid ticket state row: {raw[:80]}")
        key, value = match.groups()
        if key in rows:
            raise TicketError(f"duplicate ticket state key: {key}")
        rows[key] = value.strip()
    missing = [key for key in TICKET_KEYS if key not in rows]
    extra = sorted(set(rows) - set(TICKET_KEYS))
    if missing or extra:
        raise TicketError(f"ticket state keys mismatch; missing={missing}; extra={extra}")
    return rows


def parse_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\n", text))
    headings = [match.group(1).strip() for match in matches]
    if headings != list(TICKET_SECTIONS):
        raise TicketError(f"required section order is: {' -> '.join(TICKET_SECTIONS)}")
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[headings[index]] = text[match.end() : end].strip()
    return sections


def parse_list(value: str) -> tuple[str, ...]:
    if value == "none":
        return ()
    entries = tuple(item.strip() for item in value.split(","))
    if any(not entry for entry in entries):
        raise TicketError(f"list field must be none or comma-separated values: {value!r}")
    return entries


def render_state(text: str, changes: dict[str, str]) -> str:
    state = parse_state(text)
    state.update(changes)
    block = "\n" + "\n".join(f"- {key} = {state[key]}" for key in TICKET_KEYS) + "\n"
    start, end = state_bounds(text)
    return text[:start] + block + text[end:]


def completed_prefix(value: str, slices: tuple[str, ...]) -> tuple[str, ...]:
    entries = parse_list(value)
    unknown = [item for item in entries if item not in slices]
    if unknown:
        raise TicketError(f"completed_slices not in this ticket's slices: {', '.join(unknown)}")
    if entries != slices[: len(entries)]:
        raise TicketError("completed_slices must be an exact ordered prefix of this ticket's slices")
    return entries


def validate_ticket_text(text: str, *, epic_slices: tuple[str, ...] | None = None) -> dict[str, str]:
    state = parse_state(text)
    parse_sections(text)
    if state["state_version"] != "1":
        raise TicketError("state_version must be 1")
    if not state["ticket_id"] or any(c.isspace() for c in state["ticket_id"]):
        raise TicketError("ticket_id must be one nonempty token")
    if not state["epic_plan_id"] or any(c.isspace() for c in state["epic_plan_id"]):
        raise TicketError("epic_plan_id must be one nonempty token")
    if not FINGERPRINT.fullmatch(state["epic_fingerprint"]):
        raise TicketError("epic_fingerprint must be sha256")
    if state["status"] not in STATUSES:
        raise TicketError(f"invalid status: {state['status']!r}")
    parse_list(state["depends_on"])
    slices = parse_list(state["slices"])
    parse_list(state["covers"])
    if epic_slices is not None:
        outside = [item for item in slices if item not in epic_slices]
        if outside:
            raise TicketError(f"slices not part of the epic partition: {', '.join(outside)}")
    completed_prefix(state["completed_slices"], slices)
    if state["status"] == "todo":
        if state["claimed_by"] != "none" or state["claimed_at"] != "none":
            raise TicketError('claimed_by and claimed_at must be "none" while status is todo')
    elif state["status"] != "cancelled" and (state["claimed_by"] == "none" or state["claimed_at"] == "none"):
        raise TicketError("claimed_by and claimed_at are required once a ticket is claimed")
    if (state["worktree"] == "none") != (state["branch"] == "none"):
        raise TicketError("worktree and branch must be set or cleared together")
    if state["status"] in {"todo", "cancelled"} and state["worktree"] != "none":
        raise TicketError('worktree and branch must be "none" while status is todo or cancelled')
    if state["status"] in {"claimed", "building", "green"} and state["worktree"] == "none":
        raise TicketError(f"worktree and branch are required while status is {state['status']}")
    if state["status"] in {"green", "shipped"} and state["green_artifact"] == "none":
        raise TicketError(f"status {state['status']} requires a recorded green_artifact")
    if state["green_artifact"] != "none" and state["status"] not in {"green", "shipped"}:
        raise TicketError("green_artifact must be set only while status is green or shipped")
    if state["status"] == "shipped" and state["delivery"] == "none":
        raise TicketError("status shipped requires a recorded delivery")
    if state["delivery"] != "none" and state["status"] != "shipped":
        raise TicketError("delivery must be set only while status is shipped")
    if state["delivery"] != "none" and not re.fullmatch(r"\S+@[0-9a-f]{7,40}", state["delivery"]):
        raise TicketError("delivery must be formatted as <url>@<7-40 hex commit>")
    return state


def build(commands: Collection[str]) -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description="Small deterministic state owner for Hard Eng parallel tickets.")
    subparsers = root.add_subparsers(dest="command", required=True)
    for name in commands:
        command = subparsers.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--session-id", default=None)
        if name == "decompose":
            command.add_argument("--epic-plan")
            command.add_argument("--expect-token", required=True)
            command.add_argument("--dry-run", action="store_true")
            command.add_argument("--amend", action="store_true")
            command.add_argument("--reconcile", action="store_true")
        elif name == "claim":
            command.add_argument("--epic-plan")
            command.add_argument("--ticket")
            command.add_argument("--next", action="store_true")
            command.add_argument("--refresh", action="store_true")
            command.add_argument("--expect-token", default=None)
        elif name == "checkpoint":
            command.add_argument("--ticket", required=True)
            command.add_argument("--expect-token", required=True)
            command.add_argument("--set", action="append", default=[], metavar="FIELD=VALUE")
            command.add_argument("--confirm-cancel", action="store_true")
        elif name == "release":
            command.add_argument("--epic-plan")
            command.add_argument("--ticket", required=True)
            command.add_argument("--expect-token", required=True)
            command.add_argument("--force-release", action="store_true")
        elif name == "board":
            command.add_argument("--epic-plan")
        elif name == "assert-ticket-green":
            command.add_argument("--ticket", required=True)
        elif name == "sync-tracker":
            command.add_argument("--epic-plan")
            command.add_argument("--pull", action="store_true")
    return root

#!/usr/bin/env python3
"""Orchestrator write guard: the primary checkout never edits a path owned by a claimed ticket."""

from __future__ import annotations

import argparse
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR), str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts")]

from bounded_run import run_captured
from git_env import git_env

IN_FLIGHT = frozenset({"claimed", "building", "green"})
STATE_ROW = re.compile(r"(?m)^- (lifecycle_status|execution_mode|status|ticket_id) = (\S+)$")
TOUCH_ROW = re.compile(r"(?m)^-\s*`([^`]+)`")


class TicketGuardError(Exception):
    """The guard cannot read the repository or the epic tickets."""


def _rows(text: str) -> dict[str, str]:
    return {key: value for key, value in STATE_ROW.findall(text)}


def is_primary_checkout(repo: Path) -> bool:
    common = run_captured(["git", "rev-parse", "--git-common-dir"], 20, cwd=str(repo), env=git_env())
    own = run_captured(["git", "rev-parse", "--git-dir"], 20, cwd=str(repo), env=git_env())
    if common.returncode or own.returncode:
        raise TicketGuardError("cannot resolve the checkout kind")
    common_dir = (repo / os.fsdecode(common.stdout.strip())).resolve()
    own_dir = (repo / os.fsdecode(own.stdout.strip())).resolve()
    return common_dir == own_dir


def ticket_epics(repo: Path) -> list[Path]:
    features = repo / "features"
    if not features.is_dir():
        return []
    plans = []
    for plan in sorted(features.glob("*/PLAN.md")):
        rows = _rows(plan.read_text(encoding="utf-8", errors="replace"))
        if rows.get("lifecycle_status") == "building" and rows.get("execution_mode") == "tickets":
            plans.append(plan)
    return plans


def claimed_paths(epic_plan: Path) -> dict[str, str]:
    owners: dict[str, str] = {}
    tickets = epic_plan.parent / "tickets"
    if not tickets.is_dir():
        return owners
    for ticket in sorted(tickets.glob("T-*.md")):
        text = ticket.read_text(encoding="utf-8", errors="replace")
        rows = _rows(text)
        if rows.get("status") not in IN_FLIGHT:
            continue
        touches = text.split("## Touches", 1)[1] if "## Touches" in text else ""
        touches = touches.split("\n## ", 1)[0]
        for path in TOUCH_ROW.findall(touches):
            owners.setdefault(path.strip("/"), rows.get("ticket_id", ticket.stem))
    return owners


def _owned(path: str, owners: dict[str, str]) -> str | None:
    parts = Path(path).as_posix().strip("/")
    for owned, ticket_id in owners.items():
        if parts == owned or parts.startswith(owned + "/"):
            return ticket_id
    return None


def guard_error(repo: Path, changed: Iterable[str]) -> str | None:
    if not is_primary_checkout(repo):
        return None
    for epic_plan in ticket_epics(repo):
        owners = claimed_paths(epic_plan)
        for entry in changed:
            if ticket_id := _owned(entry, owners):
                return f"orchestrator changed a path owned by claimed ticket {ticket_id}: {entry}"
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--path", action="append", default=[], help="changed path; omit to read NUL-separated stdin")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    changed = args.path or [os.fsdecode(item) for item in sys.stdin.buffer.read().split(b"\0") if item]
    try:
        error = guard_error(repo, changed)
    except (TicketGuardError, OSError, UnicodeError) as failure:
        print(f"result=invalid\nerror={failure}")
        return 4
    if error:
        print(f"result=invalid\nerror={error}")
        return 4
    print("result=valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

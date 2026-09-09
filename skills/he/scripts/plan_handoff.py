#!/usr/bin/env python3
"""Ready-for-handoff block: where the approved plan lives and the exact prompt that resumes its build."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from evidence_lib import EvidenceError, git_value
from plan_sections import parse_sections, remaining_slice

HANDOFF_STATES = {"build-ready", "building", "green"}
SETUP_SCRIPT = SCRIPT_DIR / "setup_state.py"
STATE_SCRIPT = SCRIPT_DIR / "plan_state.py"
TICKET_SCRIPT = SCRIPT_DIR / "ticket_state.py"


def branch_name(repo: Path) -> str:
    try:
        return git_value(repo, "symbolic-ref", "--quiet", "--short", "HEAD")
    except EvidenceError:
        pass
    try:
        return "detached@" + git_value(repo, "rev-parse", "--short", "HEAD")
    except EvidenceError:
        return "unborn"


def build_prompt(repo: Path, relative_plan: Path, slice_id: str) -> str:
    work = (
        f"then run the final pre-ship gate for {relative_plan} with he-build; every slice is complete."
        if slice_id == "none"
        else f"then build slice {slice_id} from {relative_plan} with he-build, one Implement/Verify loop until green."
    )
    return (
        f"Resume Hard Eng feature {relative_plan.parent.name} in {repo}: "
        f"run `python3 {SETUP_SCRIPT} verify --repo {repo}` and "
        f"`python3 {STATE_SCRIPT} inspect --repo {repo} --plan {relative_plan}`, {work}"
    )


def ship_prompt(repo: Path, relative_plan: Path) -> str:
    return (
        f"Ship Hard Eng feature {relative_plan.parent.name} in {repo}: read {relative_plan} and "
        f"{relative_plan.parent / 'BUILD.md'}, then follow he-ship from assert-green to the shipped checkpoint."
    )


def ticket_prompt(repo: Path, relative_plan: Path, ticket_id: str) -> str:
    return (
        f"Claim ticket {ticket_id} of Hard Eng epic {relative_plan.parent.name} in {repo}: "
        f"run `python3 {TICKET_SCRIPT} claim --repo {repo} --epic-plan {relative_plan} "
        f"--ticket {ticket_id} --session-id <session>`, open the printed worktree, "
        f"and build only that ticket's slices with he-build until it ships."
    )


def claimable_tickets(repo: Path, plan: Path) -> list[str]:
    from ticket_state import list_tickets, read_ticket

    shipped: set[str] = set()
    states: list[dict[str, str]] = []
    for path in list_tickets(plan):
        _, _, state, _ = read_ticket(repo, path)
        states.append(state)
        if state["status"] == "shipped":
            shipped.add(state["ticket_id"])
    ready: list[str] = []
    for state in states:
        if state["status"] != "todo":
            continue
        dependencies = () if state["depends_on"] == "none" else tuple(state["depends_on"].split(","))
        if all(dependency.strip() in shipped for dependency in dependencies):
            ready.append(state["ticket_id"])
    return ready


def lines(repo: Path, plan: Path, state: dict[str, str]) -> list[str]:
    if state["lifecycle_status"] not in HANDOFF_STATES:
        return []
    relative_plan = plan.relative_to(repo)
    if state["lifecycle_status"] == "green":
        return [
            "handoff=ship",
            f"handoff_root={repo}",
            f"handoff_branch={branch_name(repo)}",
            f"handoff_plan={relative_plan}",
            f"handoff_report={relative_plan.parent / 'BUILD.md'}",
            f"handoff_prompt={ship_prompt(repo, relative_plan)}",
        ]
    output = [
        "handoff=ready",
        f"handoff_root={repo}",
        f"handoff_branch={branch_name(repo)}",
        f"handoff_plan={relative_plan}",
    ]
    if state.get("execution_mode") == "tickets":
        for index, ticket_id in enumerate(claimable_tickets(repo, plan), start=1):
            output.append(f"handoff_ticket_{index}={ticket_id}")
            output.append(f"handoff_ticket_{index}_prompt={ticket_prompt(repo, relative_plan, ticket_id)}")
        return output
    slice_id = state["active_slice"]
    if slice_id == "none":
        slice_id = remaining_slice(parse_sections(plan.read_text(encoding="utf-8")), state["completed_slices"])
    output.append(f"handoff_prompt={build_prompt(repo, relative_plan, slice_id)}")
    return output

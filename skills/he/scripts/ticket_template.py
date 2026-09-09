#!/usr/bin/env python3
"""Canonical ticket template."""

from __future__ import annotations


def render(
    ticket_id: str,
    epic_plan_id: str,
    epic_fingerprint: str,
    depends_on: str,
    slices: str,
    covers: str,
    goal_text: str,
    acceptance_text: str,
    touches_text: str,
    state_start: str,
    state_end: str,
) -> str:
    return f"""# Ticket: {ticket_id}

{state_start}
- state_version = 1
- ticket_id = {ticket_id}
- epic_plan_id = {epic_plan_id}
- epic_fingerprint = {epic_fingerprint}
- status = todo
- depends_on = {depends_on}
- slices = {slices}
- covers = {covers}
- active_slice = none
- completed_slices = none
- claimed_by = none
- claimed_at = none
- worktree = none
- branch = none
- green_artifact = none
- delivery = none
- tracker_ref = none
- next_action = Claim this ticket to begin work.
{state_end}

## Goal

{goal_text}

## Acceptance

{acceptance_text}

## Touches

{touches_text}
"""

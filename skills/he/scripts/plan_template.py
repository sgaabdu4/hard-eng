#!/usr/bin/env python3
"""Canonical Feature Brief template."""

from __future__ import annotations


def render(slug: str, plan_id: str, state_start: str, state_end: str) -> str:
    title = slug.replace("-", " ").title()
    return f"""# Feature Brief: {title}

{state_start}
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
{state_end}

## Outcome
- TBD

## Non-goals
- TBD

## Material decisions
- TBD
- ux_reference = TBD
- ux_reference_sources = TBD

## Acceptance examples
- TBD

## Affected canonical areas
- TBD

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = TBD
- deferred = none
- blocked_on = none

## First vertical slice
- S-1 = TBD
- proof = TBD
"""

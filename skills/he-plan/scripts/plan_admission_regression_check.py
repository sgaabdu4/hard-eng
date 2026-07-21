#!/usr/bin/env python3
"""Regression proof for Hard Eng semantic plan admission."""

from __future__ import annotations


def fixture(*, risk: str = "critical") -> str:
    perspectives = (
        "| owner-first | owners, callers, states | PASS | sha256:" + "a" * 64 + " |\n"
        "| boundary-first | failures, recovery, operations | PASS | sha256:" + "b" * 64 + " |"
        if risk == "critical"
        else "| complete | full standard-risk plan | PASS | sha256:" + "c" * 64 + " |"
    )
    failure = (
        "| FM-1 | C-1 enqueue transition | dependency rejects after durable commit | queued | "
        "reconciler | bounded retry after lease | T-1 durable-state assertion |"
        if risk == "critical"
        else "| FM-NA | no async or irreversible C-1 boundary | synchronous bounded operation | "
        "unchanged durable record | request owner | request timeout | T-1 contract assertion |"
    )
    return f"""# fixture

## Audit policy
- risk_tier = {risk}

## Feature
- R-1 = complete operation

## Flows
- F-1 = queued to terminal

## Contracts
- C-1 = operation owner

## Testing
- T-1 = behavior proof

## Traceability
| ID | Requirement | Flow/state | Contract/owner | Proof | Telemetry/rollout | Slice |
|---|---|---|---|---|---|---|
| TR-1 | R-1 complete operation | F-1 queued to terminal | C-1 operation owner | T-1 behavior proof | bounded status metric | S-1 |

## Failure Model
| ID | Boundary/transition | Failure/interrupt | Durable state | Recovery owner | Retry/timeout | Observable proof |
|---|---|---|---|---|---|---|
{failure}

## Plan challenge
| Perspective | Scope | Result | Evidence |
|---|---|---|---|
{perspectives}

## Slices
| ID | Outcome |
|---|---|
| S-1 | Complete R-1 |
"""


def check_plan_admission(module, fail) -> None:
    module.validate_plan_admission(fixture())
    module.validate_plan_admission(fixture(risk="standard"))

    cases = {
        "missing traceability": fixture().replace("## Traceability", "## Missing"),
        "placeholder recovery": fixture().replace("reconciler", "TBD"),
        "untraced proof": fixture().replace("T-1 durable-state assertion", "T-2 durable-state assertion"),
        "critical FM-NA": fixture().replace(
            "| FM-1 | C-1 enqueue transition | dependency rejects after durable commit | queued | reconciler | bounded retry after lease | T-1 durable-state assertion |",
            "| FM-NA | no boundary | no failure | unchanged | owner | timeout | T-1 proof |",
        ),
        "missing boundary challenge": fixture().replace(
            "| boundary-first | failures, recovery, operations | PASS | sha256:" + "b" * 64 + " |\n",
            "",
        ),
        "unbound slice": fixture().replace("| S-1 | Complete R-1 |", "| S-2 | Complete R-1 |"),
        "unowned contract": fixture().replace("- C-1 = operation owner", "- C-2 = operation owner"),
    }
    for label, text in cases.items():
        try:
            module.validate_plan_admission(text)
        except module.PlanStateError:
            continue
        fail(f"plan admission accepted {label}")

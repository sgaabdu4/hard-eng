#!/usr/bin/env python3
"""Deterministic contract checks for Hard Eng planning."""

from __future__ import annotations

from pathlib import Path

from plan_admission import validate_plan_admission
from plan_admission_regression_check import check_plan_admission


ROOT = Path(__file__).resolve().parents[3]


def fail(message: str) -> None:
    raise SystemExit(f"he-plan-check: {message}")


def main() -> int:
    check_plan_admission(__import__("plan_admission"), fail)
    skill = (ROOT / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    consistency = (ROOT / "skills/he-plan/references/consistency.md").read_text(encoding="utf-8")
    admission = (ROOT / "skills/he-plan/references/admission.md").read_text(encoding="utf-8")
    contracts = (ROOT / "skills/he-plan/references/contracts.md").read_text(encoding="utf-8")
    operations = (ROOT / "skills/he-plan/references/operations.md").read_text(encoding="utf-8")
    slices = (ROOT / "skills/he-plan/references/slices.md").read_text(encoding="utf-8")
    testing = (ROOT / "skills/he-plan/references/testing.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    state = (ROOT / "skills/he/scripts/plan_state.py").read_text(encoding="utf-8")
    required = (
        (skill, "[admission.md](references/admission.md)"),
        (consistency, "plan-admission"),
        (admission, "## Traceability"),
        (admission, "## Decision Model"),
        (operations, "profile + account + tenant"),
        (agents, "umbrella labels or generic approval ≠ decision evidence"),
        (agents, "never use/repeat/store it"),
        (admission, "## Failure Model"),
        (admission, "## Guarantee Model"),
        (admission, "## Plan challenge"),
        (admission, "proofs=T-#,T-#"),
        (contracts, "`trace:TR-#`"),
        (testing, "`owner:S-#:repository/relative/path`"),
        (slices, "`action:split:S-#:T-#:source->new-owner`"),
        (state, "validate_plan_admission(candidate)"),
    )
    if any(anchor not in source for source, anchor in required):
        fail("semantic admission wiring is incomplete")
    if not callable(validate_plan_admission):
        fail("plan admission owner is unavailable")
    print("he-plan-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

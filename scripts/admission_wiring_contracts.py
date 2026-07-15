#!/usr/bin/env python3
"""Audit-admission lifecycle wiring contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Callable


def check_admission_wiring_contract(root: Path, fail: Callable[[str], None]) -> None:
    estimate = "audit.py --admission --estimate-unit <S-ID> --repo <repo> --plan <PLAN.md>"
    candidate = "audit.py --admission --candidate-patch <patch> --unit <S-ID> --repo <repo> --plan <PLAN.md>"
    apply = "apply_admitted_patch.py --repo <repo> --plan <PLAN.md> --patch <patch> --unit <S-ID>"
    slices = (root / "skills/he-plan/references/slices.md").read_text(encoding="utf-8")
    skill = (root / "skills/he-build/SKILL.md").read_text(encoding="utf-8")
    workflow = (root / "skills/he-build/references/workflow.md").read_text(encoding="utf-8")
    if estimate not in slices or "planned_paths" not in slices or "before exact slice acceptance" not in slices:
        fail("Slices estimate gate missing")
    if "estimate PASS" not in slices or "re-cut" not in slices:
        fail("Slices overflow route missing")
    if any(anchor not in skill for anchor in (
        "Candidate admission + same-byte mutation",
        "[workflow.md](references/workflow.md) Enter + Resume",
        "no other delivery mutation route",
    )):
        fail("Build candidate/apply invariant missing")
    required_workflow = (
        candidate,
        apply,
        "Enter + Resume",
        "candidate PASS",
        "same-byte",
        "accumulated",
        "preimage",
        "rollback",
        "drift",
        "return to Slices",
        "does not replace final audit",
    )
    if any(anchor not in workflow for anchor in required_workflow):
        fail("Build Enter/Resume candidate/apply gate missing")

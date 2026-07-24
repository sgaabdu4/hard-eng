#!/usr/bin/env python3
"""Focused documentation and routing contracts for the Fast Feature Loop."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class Contract:
    scenario: str
    clauses: tuple[tuple[str, tuple[str, ...]], ...]


CONTRACTS = (
    Contract(
        "bounded fix routes Direct without PLAN",
        (
            ("AGENTS.md", ("| Direct | bounded clear outcome",)),
            ("PRODUCT.md", ("| Direct | bounded work reaches focused green proof without lifecycle state |",)),
            ("README.md", ("Fix the typo in the account menu.", "# Direct")),
        ),
    ),
    Contract(
        "standard feature uses one lean brief and one Ready-to-build approval",
        (
            (
                "AGENTS.md",
                (
                    "lean Feature Brief → one Ready-to-build approval",
                    "arbitrary question limit = none",
                ),
            ),
            (
                "README.md",
                (
                    "lean Feature Brief",
                    "one Ready-to-build approval",
                    "There is no arbitrary limit on material questions.",
                ),
            ),
            ("PRODUCT.md", ("one lean Feature Brief", "one Ready-to-build approval")),
            (
                "skills/he-plan/SKILL.md",
                ("Feature Brief", "Ready-to-build", "Outcome", "Non-goals", "Material decisions",
                 "Acceptance examples", "Affected canonical areas", "Risk and rollback",
                 "First vertical slice"),
            ),
        ),
    ),
    Contract(
        "critical overlay targets only the risky slice",
        (
            ("AGENTS.md", ("Critical overlay = slice-scoped; safe slices keep standard flow.",)),
            ("README.md", ("Critical overlay follows risk", "for that slice only")),
            ("PRODUCT.md", ("affected risky slice receives stronger contract + proof + review",)),
            ("DESIGN.md", ("risk marker on affected slice only",)),
        ),
    ),
    Contract(
        "bugs require root cause, blast radius, and regression proof",
        (
            (
                "AGENTS.md",
                ("bug + flake + failure + regression", "root cause + blast radius", "regression proof green"),
            ),
            ("README.md", ("Bugs are diagnosed before they are patched.", "root cause and blast radius")),
            ("skills/diagnosing-bugs/SKILL.md", ("root", "regression")),
        ),
    ),
    Contract(
        "material outcome or protected-risk changes pause and replan",
        (
            (
                "AGENTS.md",
                ("product outcome + UX behavior + default/policy + security/privacy + data loss + irreversible choice",
                 "Accepted outcome or material risk contract change", "show exact delta → confirm",
                 "Replan = accepted outcome change OR material risk contract change"),
            ),
            (
                "README.md",
                ("product outcome or user-visible behavior", "security or privacy", "data-loss exposure",
                 "an irreversible decision", "shows the exact delta and asks for confirmation"),
            ),
        ),
    ),
    Contract(
        "implementation discoveries continue without reapproval",
        (
            (
                "AGENTS.md",
                ("File/owner/caller/schema/key/test/route discovery with unchanged outcome/risk",
                 "reapproval forbidden", "unchanged outcome/risk continues automatically"),
            ),
            (
                "README.md",
                ("caller, file, owner, schema, route, test, or configuration",
                 "without reopening the brief"),
            ),
            ("PRODUCT.md", ("file/owner/test change ≠ replan",)),
        ),
    ),
    Contract(
        "destructive, external, Git, and publish actions retain exact approvals",
        (
            (
                "AGENTS.md",
                ("Destructive action/external write/commit/push/merge/publish = exact target + exact scoped approval.",
                 "Commit/push/merge/publish = separate exact approval boundary."),
            ),
            (
                "README.md",
                ("destructive actions, external writes, commits, pushes, merges, or publication",
                 "explicitly approved"),
            ),
            ("skills/he-ship/SKILL.md", ("exact", "approval")),
        ),
    ),
    Contract(
        "process learning blocks only credible protected-boundary risk",
        (
            (
                "AGENTS.md",
                ("Process learning =", "continue delivery",
                 "block only when continued work risks protected boundary"),
            ),
            (
                "README.md",
                ("Product delivery continues", "unless continuing would risk security, privacy, accessibility, data integrity"),
            ),
            ("skills/he-learn/SKILL.md", ("protected boundary", "continue")),
        ),
    ),
    Contract(
        "actual-diff review and relevant proof remain required",
        (
            (
                "AGENTS.md",
                ("Review = actual diff + affected behavior + risk-targeted proof",
                 "Tests/QA/TDD → `$test-quality`", "real UI proof → `$e2e`",
                 "Security → `$security-review`"),
            ),
            (
                "README.md",
                ("actual diff, affected behavior, blast radius, and risk-targeted evidence",
                 "Deterministic project gates", "browser or device evidence"),
            ),
            ("skills/he-build/SKILL.md", ("actual-diff review", "affected proof", "relevant E2E/security proof")),
        ),
    ),
)


ALIGNMENT_OWNERS = (
    ("AGENTS.md", ("Feature Brief", "Ready-to-build", "Implement ⇄ Verify")),
    ("README.md", ("Feature Brief", "Ready-to-build", "Implement ⇄ Verify")),
    ("PRODUCT.md", ("Feature Brief", "Ready-to-build", "Implement ⇄ Verify")),
    ("DESIGN.md", ("Feature Brief", "Ready-to-build", "Implement ⇄ Verify")),
    ("skills/he/SKILL.md", ("Feature Brief", "Ready-to-build", "lifecycle_status")),
    ("skills/he-plan/SKILL.md", ("Feature Brief", "Ready-to-build", "vertical slice")),
    ("skills/he-build/SKILL.md", ("Feature Brief", "Implement ⇄ Verify", "vertical slice")),
    ("skills/he-ship/SKILL.md", ("green", "artifact", "approval")),
)

REMOVED_FILES = (
    "scripts/admission_wiring_contracts.py",
    "scripts/plan_approval_contracts.py",
    "skills/he-plan/scripts/plan_admission.py",
    "skills/he-build/scripts/audit.py",
    "skills/he-build/scripts/audit_admission.py",
    "skills/he-build/scripts/audit_candidate.py",
    "skills/he-build/scripts/apply_admitted_patch.py",
)

ACTIVE_DOCS = (
    "AGENTS.md",
    "README.md",
    "PRODUCT.md",
    "DESIGN.md",
    "skills/he/SKILL.md",
    "skills/he-plan/SKILL.md",
    "skills/he-build/SKILL.md",
    "skills/he-ship/SKILL.md",
    "skills/he-learn/SKILL.md",
)

REMOVED_DEPENDENCIES = (
    "planned_paths",
    "--candidate-patch",
    "candidate patch admission",
    "D/R/F/C/FM/G/T/TR",
)
SCRIPT_OWNERS = {
    "skills/he/scripts": {"legacy_v4.py", "plan_state.py", "safe_plan_io.py"},
    "skills/he-plan/scripts": {"check.py", "safe_plan_io_regression.py"},
    "skills/he-build/scripts": {"check.py"},
    "skills/he-ship/scripts": {"check.py"},
}


def check_fast_feature_loop_contract(root: Path, fail: Callable[[str], None]) -> None:
    cache: dict[str, str] = {}

    def read(relative: str) -> str:
        if relative not in cache:
            path = root / relative
            if not path.is_file():
                fail(f"required Fast Feature Loop owner missing: {relative}")
            cache[relative] = path.read_text(encoding="utf-8")
        return cache[relative]

    for contract in CONTRACTS:
        for relative, anchors in contract.clauses:
            text = read(relative)
            missing = tuple(anchor for anchor in anchors if anchor not in text)
            if missing:
                fail(f"{contract.scenario}: {relative} missing {missing!r}")
        print(f"fast-loop-proof: PASS | {contract.scenario}")

    for relative, terms in ALIGNMENT_OWNERS:
        text = read(relative)
        missing = tuple(term for term in terms if term not in text)
        if missing:
            fail(f"terminology drift in {relative}: missing {missing!r}")

    for relative in REMOVED_FILES:
        if (root / relative).exists():
            fail(f"removed lifecycle dependency remains active: {relative}")

    for relative, expected in SCRIPT_OWNERS.items():
        actual = {
            path.name for path in (root / relative).glob("*.py") if path.is_file()
        }
        if actual != expected:
            fail(
                f"lifecycle script ownership drift in {relative}: "
                f"expected={sorted(expected)!r}; actual={sorted(actual)!r}"
            )

    for relative in ACTIVE_DOCS:
        lowered = read(relative).lower()
        for dependency in REMOVED_DEPENDENCIES:
            if dependency.lower() in lowered:
                fail(f"removed lifecycle dependency referenced by {relative}: {dependency}")

    checker = (root / "scripts/check-skill-contracts.py").read_text(encoding="utf-8")
    for dependency in ("admission_wiring_contracts", "plan_approval_contracts", "skill_route_contracts"):
        if dependency in checker:
            fail(f"contract checker imports removed dependency: {dependency}")

    print("fast-loop-proof: terminology and legacy-dependency checks -> PASS")


if __name__ == "__main__":
    def standalone_fail(message: str) -> None:
        raise SystemExit(f"fast-loop-contracts: FAIL: {message}")

    check_fast_feature_loop_contract(Path(__file__).resolve().parents[1], standalone_fail)
    print("fast-loop-contracts: PASS")

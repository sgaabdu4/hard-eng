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
                    "Feature alignment = `$question-me` until aligned",
                    "arbitrary question limit = none",
                ),
            ),
            (
                "README.md",
                (
                    "lean Feature Brief",
                    "one Ready-to-build approval",
                    "Questions are asked one at a time.",
                    "Before each one, Codex researches the available evidence",
                    "There is no arbitrary limit on material questions.",
                    "Ready-to-build approval rounds before standard build",
                    "Material question cadence",
                ),
            ),
            (
                "PRODUCT.md",
                ("one lean Feature Brief", "one Ready-to-build approval",
                 "one evidence-backed question per turn"),
            ),
            (
                "skills/question-me/SKILL.md",
                (
                    "Before every question = refresh",
                    "evidence-settled item → record + never ask",
                    "exactly one material user decision per turn",
                    "next question branches from accepted answers",
                    "Unlimited material questions",
                ),
            ),
            (
                "skills/question-me/references/direct.md",
                ("Select next material user decision by dependency + impact",),
            ),
            (
                "skills/question-me/references/feature-brief.md",
                ("Select next material `user-decision` by dependency + impact",),
            ),
            (
                "skills/he-plan/SKILL.md",
                ("Feature Brief", "Ready-to-build", "Outcome", "Non-goals", "Material decisions",
                 "Acceptance examples", "Affected canonical areas", "Risk and rollback",
                 "First vertical slice"),
            ),
        ),
    ),
    Contract(
        "post-flow audit gaps stay prevented without another lifecycle",
        (
            (
                "AGENTS.md",
                (
                    "Approval answer = immediately preceding exact boundary only",
                    "delivery form/lifetime when it changes observable operation",
                    "Terminal PLAN cleanup = prove terminal state + exact path/hash",
                    "active/nonterminal PLAN deletion forbidden",
                    "Terminal handoff + unrelated request = recommend fresh task",
                    "Shared session/preferences/account CLI = sequential",
                    "Commentary = material state change + blocker + approval boundary + proof",
                ),
            ),
            (
                "README.md",
                (
                    "A decision answer or generic acknowledgement cannot be reused",
                    "original reported examples at the boundary where users observed them",
                    "remove only the exact terminal PLAN paths the user approves",
                    "Unrelated work starts a fresh task after a long delivery",
                    "Routine tool narration and unchanged polling are omitted",
                ),
            ),
            (
                "skills/he/SKILL.md",
                ("exact user-authorized terminal PLAN file cleanup",),
            ),
            (
                "skills/he-plan/references/feature-brief.md",
                ("ready_to_build_reply", "Copy the user's exact immediately following reply"),
            ),
            (
                "skills/question-me/SKILL.md",
                ("Delivery form/lifetime = material only when",),
            ),
            (
                "skills/diagnosing-bugs/references/diagnose.md",
                ("Reporter-provided examples = immutable reproduction inventory",),
            ),
            (
                "skills/diagnosing-bugs/references/fix.md",
                ("observed public/package/release boundary",),
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
                (
                    "Destructive action/external write/commit/push/merge/publish = exact target + exact scoped approval.",
                    "Exact approval may cover one named target + bounded actions + exclusions",
                    "Commit/push/merge/publish = separate exact approval boundary.",
                ),
            ),
            (
                "README.md",
                ("destructive actions, external writes, commits, pushes, merges, or publication",
                 "explicitly approved", "One exact external approval may cover"),
            ),
            ("skills/he-ship/SKILL.md", ("exact", "approval")),
        ),
    ),
    Contract(
        "process learning blocks only credible protected-boundary risk",
        (
            (
                "AGENTS.md",
                (
                    "Process learning =",
                    "continue delivery",
                    "block only when continued work risks protected boundary",
                    "Subagents = current user prompt explicitly requests",
                ),
            ),
            (
                "README.md",
                ("Product delivery continues", "unless continuing would risk security, privacy, accessibility, data integrity"),
            ),
            (
                "skills/he-learn/SKILL.md",
                ("protected boundary", "continue", "execution follows global Subagents contract"),
            ),
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
    "scripts/legacy-v4-migration-contracts.py",
    "scripts/plan_approval_contracts.py",
    "skills/he-plan/scripts/plan_admission.py",
    "skills/he-build/scripts/audit.py",
    "skills/he-build/scripts/audit_admission.py",
    "skills/he-build/scripts/audit_candidate.py",
    "skills/he-build/scripts/apply_admitted_patch.py",
    "skills/he/references/legacy-v4.md",
    "skills/he/scripts/legacy_v4.py",
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
    "skills/he/scripts": {"plan_state.py", "safe_plan_io.py"},
    "skills/he-plan/scripts": {"check.py", "safe_plan_io_regression.py"},
    "skills/he-build/scripts": {"check.py"},
    "skills/he-ship/scripts": {"check.py"},
}
RETIRED_STATE_TOKENS = (
    "migrate-v4",
    "legacy-v4",
    "legacy_v4",
    "archive_then_replace",
)
STATE_OWNERS = (
    "skills/he/scripts/plan_state.py",
    "skills/he/scripts/safe_plan_io.py",
    "skills/he-plan/scripts/check.py",
    "skills/he-plan/scripts/safe_plan_io_regression.py",
    "scripts/check-skill-contracts.py",
    "scripts/route_resource_contracts.py",
)
REPOSITORY_POLICY_ANCHORS = (
    "`AGENTS.md` = cross-repository behavior only.",
    "`AGENTS.override.md` = Hard Eng repository facts + maintenance + delivery rules.",
    "Global admission = applies unchanged to unrelated repositories; otherwise keep it here.",
    "Hard Eng owner replacement = one canonical path + superseded alias/compatibility/dual-path deletion.",
)
HUMAN_OWNERSHIP_ANCHOR = (
    "A repository-specific rule must not be promoted into the global file"
)
QUESTION_CADENCE_OWNERS = (
    "AGENTS.md",
    "PRODUCT.md",
    "README.md",
    "skills/he-plan/references/feature-brief.md",
    "skills/question-me/SKILL.md",
    "skills/question-me/references/direct.md",
    "skills/question-me/references/feature-brief.md",
)
FORBIDDEN_QUESTION_BATCHING = (
    "batch questions",
    "questions are batched",
    "questions in one batch",
    "batch independent",
    "independent choices are batched",
    "bounded batch",
)
PROCESS_LEARNING_OWNERS = (
    "skills/he-build/SKILL.md",
    "skills/he-build/references/workflow.md",
    "skills/he-learn/SKILL.md",
    "skills/he-learn/agents/openai.yaml",
    "skills/he-learn/references/workflow.md",
    "skills/he-ship/SKILL.md",
    "skills/he-ship/references/workflow.md",
)


def directive_keys(policy: str) -> frozenset[str]:
    return frozenset(
        line[2:].split(" = ", 1)[0].strip("` ").casefold()
        for raw in policy.splitlines()
        if (line := raw.strip()).startswith("- ") and " = " in line
    )


def instruction_ownership_error(
    global_policy: str, repository_policy: str, human_policy: str
) -> str | None:
    missing = tuple(
        anchor for anchor in REPOSITORY_POLICY_ANCHORS
        if anchor not in repository_policy
    )
    if missing:
        return f"repository instruction ownership contract missing: {missing!r}"
    if "# Hard Eng Repository" not in repository_policy:
        return "Hard Eng repository policy heading missing"
    if "# Hard Eng Repository" in global_policy:
        return "Hard Eng repository heading leaked globally"
    global_keys = directive_keys(global_policy)
    repository_keys = directive_keys(repository_policy)
    overlap = tuple(sorted(global_keys & repository_keys))
    if overlap:
        return f"Hard Eng repository directive keys leaked globally: {overlap!r}"
    replacements = tuple(sorted(key for key in global_keys if "replacement" in key))
    if replacements:
        return f"repository replacement directive leaked globally: {replacements!r}"
    if HUMAN_OWNERSHIP_ANCHOR not in human_policy:
        return "human instruction-ownership guidance missing"
    return None


def question_batching_error(text: str) -> str | None:
    lowered = text.casefold()
    return next((term for term in FORBIDDEN_QUESTION_BATCHING if term in lowered), None)


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

    if question_batching_error("batch independent questions") is None:
        fail("question-cadence guard accepted batching fixture")
    if question_batching_error("ask one material question then wait") is not None:
        fail("question-cadence guard rejected one-at-a-time fixture")
    for relative in QUESTION_CADENCE_OWNERS:
        if term := question_batching_error(read(relative)):
            fail(f"question batching remains in {relative}: {term}")
    for relative in PROCESS_LEARNING_OWNERS:
        lowered = read(relative).casefold()
        if "asynchronous" in lowered or "asynchronously" in lowered:
            fail(f"process learning implies background execution in {relative}")

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
        for dependency in (*REMOVED_DEPENDENCIES, *RETIRED_STATE_TOKENS):
            if dependency.lower() in lowered:
                fail(f"removed lifecycle dependency referenced by {relative}: {dependency}")

    for relative in STATE_OWNERS:
        lowered = read(relative).lower()
        for token in RETIRED_STATE_TOKENS:
            if token in lowered:
                fail(f"retired state path referenced by {relative}: {token}")

    global_policy = read("AGENTS.md")
    repository_policy = read("AGENTS.override.md")
    human_policy = read("README.md")
    ownership_error = instruction_ownership_error(
        global_policy, repository_policy, human_policy
    )
    if ownership_error:
        fail(ownership_error)
    rejected_fixtures = (
        "- Replacement = full migration + compatibility-path deletion.",
        "- Owner replacement = finish migrations and delete superseded dual routing.",
        "- Product = Hard Eng",
        "- checkout_policy = primary-only",
        "- Daily CI = direct default-branch commit when changed.",
    )
    for fixture in rejected_fixtures:
        if instruction_ownership_error(
            f"{global_policy}\n{fixture}\n", repository_policy, human_policy
        ) is None:
            fail(f"instruction-ownership guard accepted leak fixture: {fixture}")
    for key in directive_keys(repository_policy):
        fixture = f"- {key} = injected repository policy."
        if instruction_ownership_error(
            f"{global_policy}\n{fixture}\n", repository_policy, human_policy
        ) is None:
            fail(f"instruction-ownership guard accepted owner key: {key}")
    valid_fixture = "- Terminology = ordinary replacement text remains contextual."
    if instruction_ownership_error(
        f"{global_policy}\n{valid_fixture}\n", repository_policy, human_policy
    ):
        fail("instruction-ownership guard rejected ordinary global wording")

    checker = (root / "scripts/check-skill-contracts.py").read_text(encoding="utf-8")
    for dependency in ("admission_wiring_contracts", "plan_approval_contracts", "skill_route_contracts"):
        if dependency in checker:
            fail(f"contract checker imports removed dependency: {dependency}")

    print("fast-loop-proof: terminology and retired-dependency checks -> PASS")


if __name__ == "__main__":
    def standalone_fail(message: str) -> None:
        raise SystemExit(f"fast-loop-contracts: FAIL: {message}")

    check_fast_feature_loop_contract(Path(__file__).resolve().parents[1], standalone_fail)
    print("fast-loop-contracts: PASS")

#!/usr/bin/env python3
"""Behavioral guards for the Fast Feature Loop; prose anchors live in doc_contracts.py."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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

REMOVED_DEPENDENCIES = ("planned_paths", "--candidate-patch", "candidate patch admission", "D/R/F/C/FM/G/T/TR")
SCRIPT_OWNERS = {
    "skills/he/scripts": {
        "authorization_recovery.py",
        "evidence_lib.py",
        "execution_direct.py",
        "execution_evidence.py",
        "execution_evidence_regression.py",
        "lifecycle_excludes.py",
        "lifecycle_excludes_regression.py",
        "plan_cleanup.py",
        "plan_cleanup_regression.py",
        "plan_parser.py",
        "plan_paths.py",
        "plan_sections.py",
        "plan_state.py",
        "plan_template.py",
        "protected_direct_regression.py",
        "safe_plan_io.py",
        "setup_state.py",
        "setup_state_regression.py",
        "skill_source_policy.py",
        "skill_source_policy_regression.py",
        "ticket_decompose.py",
        "ticket_parser.py",
        "ticket_state.py",
        "ticket_state_regression.py",
        "ticket_template.py",
        "ticket_worktree.py",
        "tracker_github.py",
        "ux_reference.py",
    },
    "skills/he-plan/scripts": {
        "authorization_recovery_regression.py",
        "check.py",
        "safe_plan_io_regression.py",
        "ux_reference_regression.py",
    },
    "skills/he-build/scripts": set(),
    "skills/he-ship/scripts": {"check.py"},
}
RETIRED_STATE_TOKENS = ("migrate-v4", "legacy-v4", "legacy_v4", "archive_then_replace")
STATE_OWNERS = (
    "skills/he/scripts/plan_state.py",
    "skills/he/scripts/authorization_recovery.py",
    "skills/he/scripts/safe_plan_io.py",
    "skills/he/scripts/ux_reference.py",
    "skills/he-plan/scripts/check.py",
    "skills/he-plan/scripts/authorization_recovery_regression.py",
    "skills/he-plan/scripts/safe_plan_io_regression.py",
    "skills/he-plan/scripts/ux_reference_regression.py",
    "scripts/check-skill-contracts.py",
    "scripts/route_resource_contracts.py",
)
REPOSITORY_POLICY_ANCHORS = (
    "`AGENTS.md` = cross-repository behavior only.",
    "`AGENTS.override.md` = Hard Eng repository facts + maintenance + delivery rules.",
    "Global admission = applies unchanged to unrelated repositories; otherwise keep it here.",
    "Hard Eng owner replacement = one canonical path + superseded alias/compatibility/dual-path deletion.",
)
HUMAN_OWNERSHIP_ANCHOR = "Global admission = applies unchanged to unrelated repositories; otherwise keep it here."
QUESTION_CADENCE_ANCHORS = {
    "AGENTS.md": ("Alignment latency = one dependency frontier per turn",),
    "PRODUCT.md": ("Decision latency", "independent dependency frontier"),
    "skills/he-plan/references/feature-brief.md": ("batch independent decisions",),
    "skills/question-me/SKILL.md": (
        "Question cadence = one dependency frontier per turn",
        "batch every mutually independent material decision",
    ),
    "skills/question-me/references/direct.md": ("batch every independent material decision",),
    "skills/question-me/references/feature-brief.md": ("batch independent decisions",),
}
FORBIDDEN_SERIAL_QUESTIONING = ("exactly one material user decision per turn", "questions are asked one at a time")
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


def instruction_ownership_error(global_policy: str, repository_policy: str) -> str | None:
    missing = tuple(anchor for anchor in REPOSITORY_POLICY_ANCHORS if anchor not in repository_policy)
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
    if HUMAN_OWNERSHIP_ANCHOR not in repository_policy:
        return "repository instruction-ownership guidance missing"
    return None


def serial_questioning_error(text: str) -> str | None:
    lowered = text.casefold()
    return next((term for term in FORBIDDEN_SERIAL_QUESTIONING if term in lowered), None)


def check_fast_feature_loop_contract(root: Path, fail: Callable[[str], None]) -> None:
    cache: dict[str, str] = {}

    def read(relative: str) -> str:
        if relative not in cache:
            path = root / relative
            if not path.is_file():
                fail(f"required Fast Feature Loop owner missing: {relative}")
            cache[relative] = path.read_text(encoding="utf-8")
        return cache[relative]

    if serial_questioning_error("questions are asked one at a time") is None:
        fail("question-cadence guard accepted serialized fixture")
    if serial_questioning_error("batch independent decisions by dependency frontier") is not None:
        fail("question-cadence guard rejected dependency-frontier fixture")
    for relative, anchors in QUESTION_CADENCE_ANCHORS.items():
        text = read(relative)
        for anchor in anchors:
            if anchor not in text:
                fail(f"question cadence missing in {relative}: {anchor}")
        if term := serial_questioning_error(text):
            fail(f"serialized question cadence remains in {relative}: {term}")
    for relative in PROCESS_LEARNING_OWNERS:
        lowered = read(relative).casefold()
        if "asynchronous" in lowered or "asynchronously" in lowered:
            fail(f"process learning implies background execution in {relative}")

    for relative in REMOVED_FILES:
        if (root / relative).exists():
            fail(f"removed lifecycle dependency remains active: {relative}")

    for relative, expected in SCRIPT_OWNERS.items():
        actual = {path.name for path in (root / relative).glob("*.py") if path.is_file()}
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
    ownership_error = instruction_ownership_error(global_policy, repository_policy)
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
        if instruction_ownership_error(f"{global_policy}\n{fixture}\n", repository_policy) is None:
            fail(f"instruction-ownership guard accepted leak fixture: {fixture}")
    for key in directive_keys(repository_policy):
        fixture = f"- {key} = injected repository policy."
        if instruction_ownership_error(f"{global_policy}\n{fixture}\n", repository_policy) is None:
            fail(f"instruction-ownership guard accepted owner key: {key}")
    valid_fixture = "- Terminology = ordinary replacement text remains contextual."
    if instruction_ownership_error(f"{global_policy}\n{valid_fixture}\n", repository_policy):
        fail("instruction-ownership guard rejected ordinary global wording")

    checker = (root / "scripts/check-skill-contracts.py").read_text(encoding="utf-8")
    for dependency in ("admission_wiring_contracts", "plan_approval_contracts", "skill_route_contracts"):
        if dependency in checker:
            fail(f"contract checker imports removed dependency: {dependency}")

    print("fast-loop-proof: behavioral and retired-dependency checks -> PASS")


if __name__ == "__main__":

    def standalone_fail(message: str) -> None:
        raise SystemExit(f"fast-loop-contracts: FAIL: {message}")

    check_fast_feature_loop_contract(Path(__file__).resolve().parents[1], standalone_fail)
    print("fast-loop-contracts: PASS")

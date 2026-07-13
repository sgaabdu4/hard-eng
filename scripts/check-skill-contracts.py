#!/usr/bin/env python3
"""Check Hard Eng state/doc parity and representative skill routes."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PLAN_STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"


def fail(message: str) -> None:
    print(f"skill-contracts: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_plan_state():
    spec = importlib.util.spec_from_file_location("hard_eng_plan_state", PLAN_STATE_PATH)
    if spec is None or spec.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def state(module, **changes: str) -> dict[str, str]:
    values = {
        "state_version": "2",
        "plan_id": "fixture",
        "feature_slug": "fixture",
        "repository_root": str(ROOT),
        "branch": "main",
        "base_sha": "0" * 40,
        "head_sha": "0" * 40,
        "updated_at_utc": "2026-01-01T00:00:00Z",
        "lifecycle_status": "planning",
        "current_stage": "plan",
        "plan_stage": module.PLAN_STAGES[0],
        "approved_plan_stages": "none",
        "skipped_plan_stages": "none",
        "stage_status": "in-progress",
        "next_action": "fixture",
        "waiting_for": "agent",
        "plan_approved": "no",
        "open_blockers": "none",
        "open_issues": "none",
        "open_unknowns": "none",
    }
    values.update(changes)
    return values


def expect_invalid(module, values: dict[str, str], label: str) -> None:
    try:
        module.validate_values(values)
        module.validate_transition(values)
    except module.PlanStateError:
        return
    fail(f"invalid state accepted: {label}")


def check_state_contract(module) -> None:
    expected_targets = {
        "planning": "$he-plan",
        "build-ready": "$he-build",
        "building": "$he-build",
        "green": "$he-ship",
        "shipping": "$he-ship",
        "learning": "$he-learn",
        "shipped": "none",
        "cancelled": "none",
    }
    if module.ROUTE_TARGETS != expected_targets or set(module.LIFECYCLE) != set(expected_targets):
        fail("lifecycle route targets are incomplete or changed")

    for index, stage in enumerate(module.PLAN_STAGES):
        prefix = module.PLAN_STAGES[:index]
        values = state(
            module,
            plan_stage=stage,
            approved_plan_stages=",".join(prefix) or "none",
        )
        module.validate_values(values)
        module.validate_transition(values)

    invalid_prefix = state(
        module,
        plan_stage="feature",
        approved_plan_stages="repository",
    )
    expect_invalid(module, invalid_prefix, "planning prefix gap")

    complete = ",".join(module.PLAN_STAGES)
    ready = state(
        module,
        lifecycle_status="build-ready",
        current_stage="build",
        plan_stage="none",
        approved_plan_stages=complete,
        stage_status="pending",
        plan_approved="yes",
    )
    module.validate_values(ready)
    module.validate_transition(ready)
    expect_invalid(module, {**ready, "open_issues": "I-1"}, "build-ready open item")

    cancelled = state(
        module,
        lifecycle_status="cancelled",
        plan_stage="none",
        stage_status="complete",
        waiting_for="none",
    )
    module.validate_values(cancelled)
    module.validate_transition(cancelled)


def check_plan_stage_parity(module) -> None:
    text = (ROOT / "skills/he-plan/SKILL.md").read_text(encoding="utf-8")
    if "$he-validated" in text or "validated by $he" not in text:
        fail("he-plan description does not identify $he as validator")

    order_match = re.search(r"^Order = `([^`]+)`\.$", text, re.MULTILINE)
    if order_match is None:
        fail("he-plan order declaration missing")
    declared_order = tuple(part.strip() for part in order_match.group(1).split("→"))
    table_order = tuple(
        match.group(1)
        for match in re.finditer(r"^\| `([a-z][a-z-]+)` \|", text, re.MULTILINE)
    )
    if declared_order != module.PLAN_STAGES:
        fail("he-plan order differs from plan_state.PLAN_STAGES")
    if table_order != module.PLAN_STAGES:
        fail("he-plan stage table differs from plan_state.PLAN_STAGES")

    he_text = (ROOT / "skills/he/SKILL.md").read_text(encoding="utf-8")
    pointer = "Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`"
    if pointer not in he_text:
        fail("he does not point state invariants to plan_state.py")
    if "Use script-emitted `route_target`" not in he_text:
        fail("he does not consume script-owned lifecycle routing")

    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    owners_match = re.search(r"^- Stage owners = (.+)$", agents_text, re.MULTILINE)
    if owners_match is None:
        fail("AGENTS stage-owner route missing")
    declared_targets = tuple(
        dict.fromkeys(re.findall(r"\$(he(?:-[a-z]+)?)", owners_match.group(1)))
    )
    expected_targets = tuple(dict.fromkeys(module.ROUTE_TARGETS.values()))
    expected_targets = tuple(target.removeprefix("$") for target in expected_targets if target != "none")
    if declared_targets != expected_targets:
        fail("AGENTS stage owners differ from plan_state.ROUTE_TARGETS")


ROUTE_FIXTURES = (
    {
        "skill": "codebase-design",
        "prompt": "Review this pass-through wrapper, module boundary, and ownership.",
        "anchors": ("module", "ownership", "wrapper"),
        "resources": ("references/workflow.md", "references/alternatives.md"),
    },
    {
        "skill": "atomic-ui",
        "prompt": "Consolidate duplicated UI tokens and component ownership in this existing interface.",
        "anchors": ("ui", "tokens", "component"),
        "resources": ("references/system.md",),
    },
    {
        "skill": "security-review",
        "prompt": "Review this dependency and LLM tool path for exploitable security risk.",
        "anchors": ("dependency", "llm", "security"),
        "resources": ("references/broad.md", "references/dependencies.md"),
    },
)


def check_route_fixtures() -> None:
    for fixture in ROUTE_FIXTURES:
        skill = fixture["skill"]
        directory = ROOT / "skills" / skill
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1].lower()
        prompt = fixture["prompt"].lower()
        uncovered = [anchor for anchor in fixture["anchors"] if anchor not in prompt]
        if uncovered:
            fail(f"{skill} route fixture lacks prompt anchors: {','.join(uncovered)}")
        missing = [anchor for anchor in fixture["anchors"] if anchor not in frontmatter]
        if missing:
            fail(f"{skill} prompt route lacks description anchors: {','.join(missing)}")
        for resource in fixture["resources"]:
            if resource not in text or not (directory / resource).is_file():
                fail(f"{skill} route resource missing: {resource}")
        print(f"route-proof: {skill} -> PASS | {fixture['prompt']}")


def main() -> int:
    module = load_plan_state()
    check_state_contract(module)
    check_plan_stage_parity(module)
    check_route_fixtures()
    print("skill-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

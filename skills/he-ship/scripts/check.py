#!/usr/bin/env python3
"""Check the lean Hard Eng ship contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/he-ship"


def require(text: str, anchors: tuple[str, ...], label: str) -> None:
    missing = tuple(anchor for anchor in anchors if anchor not in text)
    if missing:
        raise SystemExit(f"he-ship-contracts: {label} missing: {', '.join(missing)}")


def main() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    workflow = (SKILL / "references/workflow.md").read_text(encoding="utf-8")
    metadata = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    require(skill, (
        "exact green snapshot",
        "exact target + remote + branch + scope approval",
        "Generic workflow/build approval ≠ delivery approval",
        "`$deterministic-checks` `publish` PASS",
        "later local lifecycle-state bytes are not part of that artifact",
        "Force push + bypassed hook/check",
        "protected-boundary evidence",
    ), "skill contract")
    require(workflow, (
        "git push --dry-run",
        "After commit hooks complete + before dry-run/push",
        "CI ⇄ Build",
        "`$he-build` root fix",
        "canonical `$e2e` receipt validator PASS",
        "do not amend/create/push another commit",
        "--set lifecycle_status=shipped",
        "assert-green --delivered-head",
    ), "workflow contract")
    first = 'plan_state.py" assert-green --repo <repo> --plan <PLAN>'
    delivered = 'plan_state.py" assert-green --delivered-head --repo <repo> --plan <PLAN>'
    if workflow.count(first) != 1 or workflow.count(delivered) != 1:
        raise SystemExit("he-ship-contracts: working and delivered assertions must each run once")
    first_assertion = workflow.find(first)
    commit = workflow.find("Commit only reviewed green product artifact")
    second_assertion = workflow.find(delivered)
    push = workflow.find("`git push --dry-run`")
    if not (first_assertion < commit < second_assertion < push):
        raise SystemExit("he-ship-contracts: assert-green boundary ordering is invalid")
    require(metadata, ("allow_implicit_invocation: true",), "route metadata")
    print("he-ship-contracts: PASS")


if __name__ == "__main__":
    main()

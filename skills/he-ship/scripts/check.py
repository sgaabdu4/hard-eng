#!/usr/bin/env python3
"""Check he-ship workflow ordering; prose anchors live in scripts/doc_contracts.py."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/he-ship"


def main() -> None:
    workflow = (SKILL / "references/workflow.md").read_text(encoding="utf-8")
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
    failed_external_mutation = workflow.find("Failure after external mutation")
    release_recovery = workflow.find("apply global Release recovery")
    finish = workflow.find("## Finish")
    if not (failed_external_mutation < release_recovery < finish):
        raise SystemExit("he-ship-contracts: failed-release recovery ordering is invalid")
    print("he-ship-contracts: PASS")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Check the lean Hard Eng build contract."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills/he-build"


def require(text: str, anchors: tuple[str, ...], label: str) -> None:
    missing = tuple(anchor for anchor in anchors if anchor not in text)
    if missing:
        raise SystemExit(f"he-build-contracts: {label} missing: {', '.join(missing)}")


def main() -> None:
    skill = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    workflow = (SKILL / "references/workflow.md").read_text(encoding="utf-8")
    metadata = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
    require(skill, (
        "one active independently demonstrable vertical slice",
        "actual-diff review",
        "targeted independent review by every applicable protected-boundary owner",
        "Planning reopens only",
        "Candidate patches + path manifests + patch/hash admission + repeated final LLM audits = forbidden",
        "one successful full pre-ship gate",
        "Learning = asynchronous non-blocking",
    ), "skill contract")
    require(workflow, (
        "reproduce first",
        "canonical owner + every connected caller/schema/key/route/config/test/doc",
        "Review actual diff once",
        "finding-scoped re-review",
        "completed_slices",
        "preserve inspected `completed_slices` exactly",
        "first remaining planned `S-ID`",
        "`building + active_slice=none + completed_slices!=none`",
        "resetting/omitting completed progress = forbidden",
        "one unchanged corrected snapshot with full gate PASS",
        "data-loss/irreversible/schema/recovery",
        "no routine cross-repository source pause",
        "Final Pre-ship Gate",
        "canonical `$e2e` receipt PASS",
    ), "workflow contract")
    if "--set completed_slices=none" in workflow:
        raise SystemExit("he-build-contracts: build-ready transition resets completed progress")
    require(metadata, ("allow_implicit_invocation: true",), "route metadata")
    print("he-build-contracts: PASS")


if __name__ == "__main__":
    main()

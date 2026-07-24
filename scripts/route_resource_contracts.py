#!/usr/bin/env python3
"""Focused route/resource and router-child exposure contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTES = (
    ("research", ("current", "vendor", "api"), ("references/external.md",)),
    ("codebase-design", ("module", "ownership", "wrapper"), ("references/workflow.md", "references/alternatives.md")),
    ("atomic-ui", ("design.md", "ui", "tokens", "component"), ("references/design-md.md", "references/system.md")),
    ("deterministic-checks", ("deterministic", "gates"), ("references/context-docs.md", "references/worktree.md")),
    ("security-review", ("security",), ("references/broad.md", "references/dependencies.md")),
)
LIFECYCLE_ROUTES = (
    ("he", ("lifecycle", "feature brief"), ("references/legacy-v4.md",)),
    ("he-plan", ("feature brief", "approve"), ("references/feature-brief.md",)),
    ("he-build", ("approved plan", "vertical slice"), ("references/workflow.md",)),
    ("he-ship", ("green", "publish"), ("references/workflow.md",)),
    ("he-learn", ("process failure", "prevention"), ("references/workflow.md",)),
)


def fail(message: str) -> None:
    raise SystemExit(f"route-resource-contracts: FAIL: {message}")


def main() -> int:
    for skill, anchors, resources in ROUTES + LIFECYCLE_ROUTES:
        directory = ROOT / "skills" / skill
        text = (directory / "SKILL.md").read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1].lower()
        missing = tuple(anchor for anchor in anchors if anchor not in frontmatter)
        if missing:
            fail(f"{skill} description missing route anchors: {missing!r}")
        for resource in resources:
            if resource not in text or not (directory / resource).is_file():
                fail(f"{skill} resource missing: {resource}")
    for skill in ("he", "he-plan", "he-build", "he-ship", "he-learn", "question-me"):
        metadata = (ROOT / "skills" / skill / "agents/openai.yaml").read_text(encoding="utf-8")
        if "allow_implicit_invocation: true" not in metadata:
            fail(f"router child is not exposed: {skill}")
    feature_brief = (
        ROOT / "skills/he-plan/references/feature-brief.md"
    ).read_text(encoding="utf-8")
    if "migrate-v4" in feature_brief or "legacy v4" in feature_brief.lower():
        fail("normal Feature Brief workflow duplicates the conditional legacy-v4 owner")
    print("route-resource-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

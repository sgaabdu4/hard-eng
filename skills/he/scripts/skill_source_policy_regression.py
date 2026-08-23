"""Regression proof for the skill-content primary-source rule."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from skill_source_policy import skill_content_needs_primary_source  # noqa: E402

FAILURES: list[str] = []


def require(condition: bool, detail: str) -> None:
    if not condition:
        FAILURES.append(detail)


def main() -> int:
    skill = ["skills/demo/references/vendor.md"]
    entry = ["skills/demo/SKILL.md"]
    other = ["scripts/enforcement_policy.pl", "skills/demo/scripts/tool.py"]
    primary = ["https://vendor.example/docs/config"]
    local = ["hard-eng.gates.json"]

    require(
        skill_content_needs_primary_source(skill, "local", local) is not None,
        "a remembered vendor claim was admitted into skill content",
    )
    require(
        skill_content_needs_primary_source(entry, "external", local) is not None,
        "a non-HTTPS source was admitted into skill content",
    )
    require(
        skill_content_needs_primary_source(skill, "external", primary) is None,
        "a primary source was rejected for skill content",
    )
    require(
        skill_content_needs_primary_source(other, "local", local) is None,
        "the rule reached beyond skill content",
    )
    reason = skill_content_needs_primary_source(skill + entry, "local", local)
    require(
        reason is not None and "SKILL.md" in reason and "vendor.md" in reason,
        "the rejection did not name every covered path",
    )

    if FAILURES:
        for failure in FAILURES:
            print(f"skill-source-policy regression: FAIL: {failure}", file=sys.stderr)
        return 1
    print("skill-source-policy regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

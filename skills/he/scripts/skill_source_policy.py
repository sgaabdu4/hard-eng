"""Skill prose becomes canon for every repository that loads it, so a claim about
an external tool inside it cannot rest on memory. Only an HTTPS primary source
proves one."""

from __future__ import annotations

import re

SKILL_CONTENT = re.compile(r"\Askills/[^/]+/(?:SKILL\.md|references/.+\.md)\z")


def skill_content_needs_primary_source(paths: list[str], scope: str, sources: list[str]) -> str | None:
    covered = sorted(path for path in paths if SKILL_CONTENT.match(path))
    if not covered:
        return None
    if scope == "external" and any(item.startswith("https://") for item in sources):
        return None
    return "skill content requires an external HTTPS primary source: " + ", ".join(covered)

#!/usr/bin/env python3
"""Review-pass expansion and rule scope for Hard Eng final audits."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path


def inventory_review_scopes(scopes):
    return tuple(
        replace(
            scope,
            coverage_paths=scope.coverage_paths if review_pass == "owner-first" else (),
            review_pass=review_pass,
        )
        for review_pass in ("owner-first", "boundary-first")
        for scope in scopes
    )


def applicable_rule_paths(tracked: tuple[str, ...], scoped: tuple[str, ...]) -> tuple[str, ...]:
    rules = []
    for relative in tracked:
        path = Path(relative)
        if path.name not in {"AGENTS.md", "AGENTS.override.md"}:
            continue
        parent = path.parent.as_posix()
        if parent == "." or any(item == parent or item.startswith(parent + "/") for item in scoped):
            rules.append(relative)
    return tuple(sorted(rules, key=lambda value: (len(Path(value).parts), value)))

#!/usr/bin/env python3
"""Risk-tier review-pass expansion and rule scope for Hard Eng final audits."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from audit_contract import AuditError


RISK_TIERS = {"standard", "critical"}


def risk_review_scopes(scopes, risk_tier: str, *, re_audit: bool = False):
    if risk_tier not in RISK_TIERS:
        raise AuditError("invalid audit risk tier")
    if risk_tier == "standard":
        review_passes = ("re-audit" if re_audit else "standard",)
    elif re_audit:
        review_passes = ("re-audit-owner-first", "re-audit-boundary-first")
    else:
        review_passes = ("owner-first", "boundary-first")
    return tuple(
        replace(
            scope,
            coverage_paths=scope.coverage_paths if index == 0 else (),
            review_pass=review_pass,
        )
        for index, review_pass in enumerate(review_passes)
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

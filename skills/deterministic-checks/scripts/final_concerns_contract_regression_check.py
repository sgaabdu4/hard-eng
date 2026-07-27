#!/usr/bin/env python3
"""Guard actionable CONCERNS and solution-first capacity handling."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
RULES = ROOT / "AGENTS.md"
REQUIRED = (
    "`CONCERNS` = proven gap + impact + attempts + next executable action + owner/authority",
    "missing next action = incomplete",
    "Speculation/capacity hypothesis → measure + research + optimize/preflight/redesign + verify",
    "unknown bound ≠ blocker",
)


def validate(content: str) -> None:
    missing = tuple(fragment for fragment in REQUIRED if fragment not in content)
    if missing:
        raise AssertionError(f"missing final CONCERNS contract: {missing}")


def main() -> int:
    canonical = RULES.read_text(encoding="utf-8")
    validate(canonical)
    for fragment in REQUIRED:
        mutated = canonical.replace(fragment, "", 1)
        try:
            validate(mutated)
        except AssertionError:
            continue
        raise AssertionError(f"mutation survived: {fragment}")
    print("final-concerns-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

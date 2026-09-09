#!/usr/bin/env python3
"""Regression checks for cross-runtime skill-reference syntax."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, NoReturn

CHECKER = Path(__file__).with_name("check-agent-agnostic-content.py")


def fail(message: str) -> NoReturn:
    raise SystemExit(f"agent-agnostic-content-regressions: FAIL | {message}")


def load_checker() -> Any:
    specification = importlib.util.spec_from_file_location("check_agent_agnostic_content", CHECKER)
    if specification is None or specification.loader is None:
        fail("checker could not be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def main() -> int:
    module = load_checker()
    matcher = module.skill_reference_matcher(("he", "he-build", "test-quality"))
    sigil = chr(36)
    cases = (
        (f"Use {sigil}he-build now.", "he-build"),
        (f"Use {sigil}he now.", "he"),
        ("Use he-build now.", None),
        (f"Keep {sigil}HOME intact.", None),
        (f"Do not confuse {sigil}he-build-extra.", None),
    )
    for value, expected in cases:
        match = matcher.search(value)
        actual = match.group("name") if match else None
        if actual != expected:
            fail(f"expected {expected!r}, got {actual!r}")
    print("agent-agnostic-content-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

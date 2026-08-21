#!/usr/bin/env python3
"""Prove setup CLIs keep unexpected failures behind one stable boundary."""

from __future__ import annotations

import ast
import contextlib
import io
import os
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts/setup"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.setup.cli_errors import run_cli


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-cli-error-contract: FAIL: {message}")


def raises_unexpected() -> int:
    raise KeyError("fixture\nsecret-free detail")


def check_boundary() -> None:
    output = io.StringIO()
    with contextlib.redirect_stderr(output):
        result = run_cli("fixture", raises_unexpected)
    rendered = output.getvalue()
    if result != 1 or "KeyError" not in rendered or "Traceback" in rendered:
        fail("unexpected setup error escaped as a traceback")
    if len(rendered.splitlines()) != 1:
        fail("setup error boundary emitted unstable multiline output")
    previous = os.environ.get("HARD_ENG_DEBUG")
    os.environ["HARD_ENG_DEBUG"] = "1"
    try:
        try:
            run_cli("fixture", raises_unexpected)
        except KeyError:
            pass
        else:
            fail("explicit debug mode did not restore the original exception")
    finally:
        if previous is None:
            os.environ.pop("HARD_ENG_DEBUG", None)
        else:
            os.environ["HARD_ENG_DEBUG"] = previous


def check_entrypoints() -> None:
    owners = []
    for path in sorted(SETUP.glob("*.py")):
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        has_entrypoint = any(
            isinstance(node, ast.If) and isinstance(node.test, ast.Compare) and "__main__" in ast.unparse(node.test)
            for node in tree.body
        )
        if not has_entrypoint:
            continue
        owners.append(path.name)
        if "run_cli(" not in source:
            fail(f"setup CLI lacks the shared error boundary: {path.name}")
    if len(owners) < 10:
        fail("setup CLI entrypoint inventory is incomplete")


def main() -> int:
    check_boundary()
    check_entrypoints()
    print("setup-cli-error-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

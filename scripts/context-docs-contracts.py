#!/usr/bin/env python3
"""Structural regressions for deterministic PRODUCT.md and DESIGN.md inspection."""

from __future__ import annotations

import importlib.util
import io
import re
import subprocess
import tempfile
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"context-docs-contracts: FAIL: {message}")


def load():
    path = ROOT / "skills/deterministic-checks/scripts/context-docs.py"
    spec = importlib.util.spec_from_file_location("context_docs", path)
    if spec is None or spec.loader is None:
        fail("context-docs.py unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(module, root: Path) -> int:
    output = io.StringIO()
    with redirect_stdout(output):
        return module.inspect(str(root))


def fixture(module) -> tuple[str, str]:
    product = "# Product — Fixture\n\n" + "\n".join(
        f"## {section}\n- Value = fixture\n" for section in module.PRODUCT_SECTIONS
    )
    reference = (ROOT / "skills/atomic-ui/references/design-md.md").read_text(encoding="utf-8")
    match = re.search(r"^## Visual Surface = none\s+```md\n(.*?)\n```", reference, re.MULTILINE | re.DOTALL)
    if match is None:
        fail("DESIGN.md no-visual fixture missing")
    return product, match.group(1).replace("<product>", "Fixture") + "\n"


def main() -> int:
    module = load()
    with tempfile.TemporaryDirectory(prefix="hard-eng-context-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        if inspect(module, root) != 4:
            fail("missing root context documents accepted")
        product, design = fixture(module)
        (root / "PRODUCT.md").write_text(product, encoding="utf-8")
        (root / "DESIGN.md").write_text(design, encoding="utf-8")
        if inspect(module, root) != 0:
            fail("valid root context documents rejected")
        nested = root / "nested"
        nested.mkdir()
        (nested / "PRODUCT.md").write_text(product, encoding="utf-8")
        if inspect(module, root) != 4:
            fail("nested PRODUCT.md owner accepted")
        (nested / "PRODUCT.md").unlink()
        nested.rmdir()
        (root / "PRODUCT.md").write_text(product + "\n## Identity\n- Value = duplicate\n", encoding="utf-8")
        if inspect(module, root) != 4:
            fail("duplicate PRODUCT.md section accepted")
    script = (
        "const {reportExitCode}=require('./skills/deterministic-checks/scripts/check-design-md.js');"
        "process.exit(reportExitCode(JSON.parse(process.argv[1])));"
    )
    clean = '{"summary":{"errors":0,"warnings":0}}'
    warning = '{"summary":{"errors":0,"warnings":1}}'
    if subprocess.run(["node", "-e", script, clean], cwd=ROOT).returncode != 0:
        fail("clean DESIGN.md report rejected")
    if subprocess.run(["node", "-e", script, warning], cwd=ROOT).returncode == 0:
        fail("warning-only DESIGN.md report accepted")
    print("context-docs-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

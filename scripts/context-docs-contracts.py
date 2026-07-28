#!/usr/bin/env python3
"""Structural regressions for deterministic PRODUCT.md and DESIGN.md inspection."""

from __future__ import annotations

import importlib.util
import io
import re
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import scrub_environ

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> NoReturn:
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


def block(reference: Path, heading: str, language: str) -> str:
    text = reference.read_text(encoding="utf-8")
    match = re.search(
        rf"^## {re.escape(heading)}\s+```{language}\n(.*?)\n```",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if match is None:
        fail(f"{reference.name} {heading} fixture missing")
    return match.group(1).replace("<product>", "Fixture") + "\n"


def fixture() -> tuple[str, str]:
    product = block(ROOT / "skills/he-plan/references/product-md.md", "Template", "md")
    design = block(ROOT / "skills/atomic-ui/references/design-md.md", "Visual Surface = none", "md")
    return product, design


def reorder(product: str) -> str:
    parts = re.split(r"(?m)^(?=## )", product)
    return parts[0] + "".join(reversed(parts[1:]))


def main() -> int:
    module = load()
    product, design = fixture()
    with tempfile.TemporaryDirectory(prefix="hard-eng-context-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        if inspect(module, root) != 4:
            fail("missing root context documents accepted")
        (root / "PRODUCT.md").write_text(product, encoding="utf-8")
        (root / "DESIGN.md").write_text(design, encoding="utf-8")
        if inspect(module, root) != 0:
            fail("valid root context documents rejected")

        (root / "PRODUCT.md").write_text(reorder(product), encoding="utf-8")
        if inspect(module, root) != 0:
            fail("order-free PRODUCT.md sections rejected")
        (root / "PRODUCT.md").write_text(product, encoding="utf-8")

        nested = root / "nested"
        nested.mkdir()
        (nested / "PRODUCT.md").write_text(product, encoding="utf-8")
        if inspect(module, root) != 4:
            fail("nested PRODUCT.md owner accepted")
        (nested / "PRODUCT.md").unlink()
        nested.rmdir()

        cases = {
            "duplicate PRODUCT.md section": product + "\n## Users\n- Value = duplicate\n",
            "second PRODUCT.md H1": product + "\n# Second\n",
            "missing PRODUCT.md required section": product.replace("## Unknowns", "## Notes"),
            "invalid PRODUCT.md machine island": product
            + '\n## Offer\n\n```json product.md#pricing\n{ "price": }\n```\n',
        }
        for label, text in cases.items():
            (root / "PRODUCT.md").write_text(text, encoding="utf-8")
            if inspect(module, root) != 4:
                fail(f"{label} accepted")
        accepted = {
            "valid PRODUCT.md machine island": product
            + '\n## Offer\n\n```json product.md#pricing\n{ "price": 0 }\n```\n',
            "fenced shell comment read as a second H1": product
            + "\n## Install\n\n```sh\n# install the CLI\nnpm i widget\n```\n",
            "fenced example heading read as a duplicate section": product
            + "\n## Example\n\n```md\n## Users\n<who>\n```\n",
        }
        for label, text in accepted.items():
            (root / "PRODUCT.md").write_text(text, encoding="utf-8")
            if inspect(module, root) != 0:
                fail(f"{label}")

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

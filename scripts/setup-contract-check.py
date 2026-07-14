#!/usr/bin/env python3
"""Deterministic setup supply-chain regressions."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/he/scripts"))


def fail(message: str) -> None:
    raise SystemExit(f"setup-contract: FAIL: {message}")


def load_digest():
    path = ROOT / "scripts/runtime-tree-digest.py"
    spec = importlib.util.spec_from_file_location("runtime_tree_digest", path)
    if spec is None or spec.loader is None:
        fail("runtime digest module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.tree_digest


def check_lock() -> None:
    sys.path.insert(0, str(ROOT / "skills/he-build/scripts"))
    from generated_evidence import generated_file
    lock = json.loads((ROOT / "runtime/npm/package-lock.json").read_text(encoding="utf-8"))
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not packages:
        fail("npm lock package closure missing")
    for name, metadata in packages.items():
        if not name:
            continue
        if not isinstance(metadata, dict) or not metadata.get("resolved") or not metadata.get("integrity"):
            fail(f"unpinned npm dependency: {name}")
    summary = generated_file(ROOT / "runtime/npm/package-lock.json", "runtime/npm/package-lock.json")
    if summary is None or "missing-resolved-or-integrity=0" not in summary or "sha256=" not in summary:
        fail("generated npm lock evidence is incomplete")


def check_tree_digest() -> None:
    digest = load_digest()
    with tempfile.TemporaryDirectory(prefix="hard-eng-runtime-digest-") as temporary:
        root = Path(temporary)
        nested = root / "node_modules/dependency"
        nested.mkdir(parents=True)
        target = nested / "index.js"
        target.write_text("one\n", encoding="utf-8")
        baseline = digest(root)
        target.write_text("two\n", encoding="utf-8")
        if digest(root) == baseline:
            fail("nested dependency mutation escaped runtime digest")
        target.write_text("one\n", encoding="utf-8")
        target.chmod(0o755)
        if digest(root) == baseline:
            fail("runtime mode mutation escaped digest")
        target.chmod(0o644)
        link = root / "command"
        os.symlink("node_modules/dependency/index.js", link)
        linked = digest(root)
        link.unlink()
        os.symlink("wrong-target", link)
        if digest(root) == linked:
            fail("runtime symlink mutation escaped digest")


def check_safe_repo_io() -> None:
    from safe_repo_io import atomic_write, snapshot
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-io-") as temporary:
        root = Path(temporary) / "repo"; external = Path(temporary) / "external"
        (root / "nested").mkdir(parents=True); external.mkdir()
        relative = Path("nested/value.txt")
        (root / relative).write_text("inside\n", encoding="utf-8")
        (external / "value.txt").write_text("outside\n", encoding="utf-8")
        snapshot(root, relative, "fixture")
        (root / "nested").rename(root / "original")
        (root / "nested").symlink_to(external, target_is_directory=True)
        try:
            atomic_write(root, relative, b"mutated\n", 0o644)
        except (OSError, RuntimeError):
            pass
        else:
            fail("ancestor symlink swap reached repository write")
        if (external / "value.txt").read_text(encoding="utf-8") != "outside\n":
            fail("ancestor symlink swap mutated external file")


def main() -> int:
    result = subprocess.run(["bash", "-n", str(ROOT / "setup.sh")], check=False)
    if result.returncode:
        fail("setup.sh syntax")
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")
    required = ("npm ci --ignore-scripts --no-audit --no-fund", "check_npm_runtime", "runtime_tree_digest")
    if any(item not in setup for item in required):
        fail("locked script-free runtime contract missing")
    check_lock()
    check_tree_digest()
    check_safe_repo_io()
    print("setup-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

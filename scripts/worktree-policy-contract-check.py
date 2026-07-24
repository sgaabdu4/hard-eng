#!/usr/bin/env python3
"""Synthetic primary-only checkout and no-follow policy regressions."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module():
    path = ROOT / "skills/deterministic-checks/scripts/worktree.py"
    spec = importlib.util.spec_from_file_location("hard_eng_worktree", path)
    if spec is None or spec.loader is None:
        raise AssertionError("worktree policy module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(module, path: Path) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = module.inspect(str(path), "write")
    return result, output.getvalue()


def main() -> int:
    module = load_module()
    with tempfile.TemporaryDirectory(prefix="hard-eng-primary-policy-") as temporary:
        root = Path(temporary) / "source"
        linked = Path(temporary) / "linked"
        external = Path(temporary) / "external.override"
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "fixture@example.com"], check=True)
        override = root / "AGENTS.override.md"
        override.write_text("- checkout_policy = primary-only\n", encoding="utf-8")
        (root / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "fixture"], check=True)
        subprocess.run(["git", "-C", str(root), "worktree", "add", "-q", "--detach", str(linked)], check=True)
        result, output = inspect(module, linked)
        if result != 4 or "repository policy forbids linked worktrees" not in output:
            raise AssertionError("primary-only repository accepted linked worktree")
        linked_override = linked / "AGENTS.override.md"
        for linked_policy in ("- checkout_policy = primary-only\n", "- checkout_policy = selectable\n", None):
            if linked_policy is None:
                linked_override.unlink(missing_ok=True)
            else:
                linked_override.write_text(linked_policy, encoding="utf-8")
            result, output = inspect(module, linked)
            if result != 4 or "repository policy forbids linked worktrees" not in output:
                raise AssertionError("linked override bypassed primary checkout policy")
        override.write_text("# checkout_policy = primary-only\n", encoding="utf-8")
        result, output = inspect(module, root)
        if result != 3 or "checkout_policy=selectable" not in output:
            raise AssertionError("comment activated primary-only checkout policy")
        override.write_text("- checkout_policy = primary-only\n- checkout_policy = selectable\n", encoding="utf-8")
        if inspect(module, root)[0] != 4:
            raise AssertionError("duplicate checkout policy was accepted")
        external.write_text("- checkout_policy = primary-only\n", encoding="utf-8")
        override.unlink()
        override.symlink_to(external)
        result, output = inspect(module, root)
        if result != 4 or "repository preflight failed" not in output:
            raise AssertionError("tracked escaping override symlink was followed")
    print("worktree-policy-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

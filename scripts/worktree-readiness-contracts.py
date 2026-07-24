#!/usr/bin/env python3
"""Focused `.worktreeinclude` and read/write readiness regressions."""

from __future__ import annotations

import importlib.util
import io
import subprocess
import tempfile
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    raise SystemExit(f"worktree-readiness-contracts: FAIL: {message}")


def load():
    path = ROOT / "skills/deterministic-checks/scripts/worktree.py"
    spec = importlib.util.spec_from_file_location("worktree_ready", path)
    if spec is None or spec.loader is None:
        fail("worktree.py unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def inspect(module, root: Path, intent: str, choice: str | None = None) -> tuple[int, str]:
    output = io.StringIO()
    with redirect_stdout(output):
        result = module.inspect(str(root), intent, choice)
    return result, output.getvalue()


def main() -> int:
    module = load()
    with tempfile.TemporaryDirectory(prefix="hard-eng-worktree-") as temporary:
        source = Path(temporary) / "source"
        linked = Path(temporary) / "linked"
        if inspect(module, source, "read")[0] != 4:
            fail("non-Git checkout accepted")
        subprocess.run(["git", "init", "-q", "-b", "main", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.name", "Fixture"], check=True)
        subprocess.run(["git", "-C", str(source), "config", "user.email", "fixture@example.com"], check=True)
        (source / ".gitignore").write_text(".env\n", encoding="utf-8")
        (source / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        (source / ".env").write_text("fixture=true\n", encoding="utf-8")
        (source / "README.md").write_text("fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(source), "add", ".gitignore", ".worktreeinclude", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "commit", "-q", "-m", "fixture"], check=True)
        if inspect(module, source, "read")[0] != 0 or inspect(module, source, "write")[0] != 0:
            fail("clean primary checkout rejected")
        (source / "README.md").write_text("dirty\n", encoding="utf-8")
        result, output = inspect(module, source, "write")
        if result != 3 or "choice-required" not in output or inspect(module, source, "write", "current")[0] != 0:
            fail("dirty primary choice contract broken")
        subprocess.run(["git", "-C", str(source), "restore", "README.md"], check=True)
        subprocess.run(["git", "-C", str(source), "-c", "core.hooksPath=/dev/null", "worktree", "add", "-q", "--detach", str(linked)], check=True)
        if inspect(module, linked, "read")[0] != 4:
            fail("linked checkout missing included input accepted")
        (linked / ".env").write_text("fixture=true\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 0 or inspect(module, linked, "write")[0] != 0:
            fail("ready linked checkout rejected")
        (linked / ".worktreeinclude").write_text("*\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("universal include pattern accepted")
        (linked / ".worktreeinclude").write_text("README.md\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("tracked include entry accepted")
        subprocess.run(["git", "-C", str(linked), "rm", "-q", "--cached", "-f", ".worktreeinclude"], check=True)
        (linked / ".worktreeinclude").write_text(".env\n", encoding="utf-8")
        if inspect(module, linked, "read")[0] != 4:
            fail("untracked include owner accepted")
    print("worktree-readiness-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

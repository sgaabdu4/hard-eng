#!/usr/bin/env python3
"""Focused regressions for repository-owned project gate commands."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from git_env import git_env, scrub_environ

SCRIPT_DIR = Path(__file__).resolve().parent
GATE = SCRIPT_DIR / "project_gate.py"
ROOT = SCRIPT_DIR.parents[2]

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> None:
    raise SystemExit(f"project-gate-check: FAIL: {message}")


def write_manifest(repo: Path, command: list[str]) -> None:
    (repo / "hard-eng.gates.json").write_text(
        json.dumps({"schema_version": 1, "families": {"targeted": command}}),
        encoding="utf-8",
    )


def run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GATE),
            "run",
            "--repo",
            str(repo),
            "--timeout",
            "30",
            "--family",
            "targeted",
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def check_migration_contract() -> None:
    required = {
        "AGENTS.md": "`gate-migration` before first product mutation",
        "skills/deterministic-checks/SKILL.md": "[Gate migration](references/gate-migration.md)",
        "skills/deterministic-checks/references/gate-migration.md": "migration scope never absorbs source cleanup",
        "skills/he-build/SKILL.md": "`gate-migration` pauses the slice without resetting PLAN state",
        "skills/he-ship/SKILL.md": "Ship never wires it",
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"gate migration contract missing from {relative}")


def main() -> int:
    check_migration_contract()
    with tempfile.TemporaryDirectory(prefix="hard-eng-project-gate-") as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
        script = repo / "targeted-check.py"
        script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        write_manifest(repo, [sys.executable, "targeted-check.py"])
        if run(repo).returncode != 0:
            fail("valid repository-owned argv failed")

        write_manifest(repo, ["echo", "targeted"])
        rejected = run(repo)
        if rejected.returncode == 0 or "forbidden no-op/shell" not in rejected.stderr:
            fail("echo no-op proof was accepted")

        write_manifest(
            repo,
            ["npx", "--yes", "--package", "react-doctor", "react-doctor", "targeted"],
        )
        rejected = run(repo)
        if rejected.returncode == 0 or "exact semver" not in rejected.stderr:
            fail("unpinned npx package was accepted")
        write_manifest(
            repo,
            ["npx", "--yes", "--package", "react-doctor@0.9.2", "sh", "-c", "true"],
        )
        rejected = run(repo)
        if rejected.returncode == 0 or "forbidden package binary" not in rejected.stderr:
            fail("pinned npx decoy wrapped a shell command")

        (repo / ".gitignore").write_text(".secret\n", encoding="utf-8")
        (repo / ".worktreeinclude").write_text(".secret\n", encoding="utf-8")
        (repo / ".secret").write_text("preserve\n", encoding="utf-8")
        script.write_text(
            "from pathlib import Path\nPath('.secret').write_text('changed')\n",
            encoding="utf-8",
        )
        write_manifest(repo, [sys.executable, "targeted-check.py"])
        rejected = run(repo)
        if rejected.returncode == 0 or "mutated the repository tree" not in rejected.stderr:
            fail("check that mutated a required ignored input was accepted")
    print("project-gate-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

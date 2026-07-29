#!/usr/bin/env python3
"""Focused regressions for repository-owned project gate commands."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from git_env import git_env, scrub_environ
from project_gate import ProjectGateError, load_manifest, validate_quality_report

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
        "skills/deterministic-checks/references/gate-migration.md": "baseline + wiring + feature diff mixing = forbidden",
        "skills/he-build/SKILL.md": "`gate-migration` pauses the slice without resetting PLAN state",
        "skills/he-ship/SKILL.md": "Ship never wires it",
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"gate migration contract missing from {relative}")


def main() -> int:
    check_migration_contract()
    clean_fallow = {
        "kind": "combined",
        "check": {"total_issues": 0},
        "dupes": {"clone_groups": [], "clone_families": []},
        "health": {"findings": []},
    }
    validate_quality_report("fallow", json.dumps(clean_fallow))
    hidden_health_finding = {
        **clean_fallow,
        "health": {
            "findings": [
                {
                    "path": "src/owner.ts",
                    "line": 7,
                    "name": "owner",
                    "severity": "critical",
                }
            ]
        },
    }
    try:
        validate_quality_report("fallow", json.dumps(hidden_health_finding))
    except ProjectGateError as error:
        if "health=1" not in str(error) or "src/owner.ts:7" not in str(error):
            fail("Fallow health finding failure lost its compact evidence")
    else:
        fail("Fallow exit-zero health findings were accepted")
    for malformed in ("", "{}", json.dumps({**clean_fallow, "kind": "audit"})):
        try:
            validate_quality_report("fallow", malformed)
        except ProjectGateError:
            pass
        else:
            fail("malformed or scoped Fallow report was accepted")
    with tempfile.TemporaryDirectory(prefix="hard-eng-project-gate-") as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
        script = repo / "targeted-check.py"
        script.write_text("raise SystemExit(0)\n", encoding="utf-8")
        write_manifest(repo, [sys.executable, "targeted-check.py"])
        if run(repo).returncode != 0:
            fail("valid repository-owned argv failed")
        deleted = repo / "deleted-owner.txt"
        deleted.write_text("tracked\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "deleted-owner.txt"], check=True)
        deleted.unlink()
        if run(repo).returncode != 0:
            fail("gate could not snapshot an intentional tracked deletion")

        write_manifest(repo, ["echo", "targeted"])
        rejected = run(repo)
        if rejected.returncode == 0 or "forbidden no-op/shell" not in rejected.stderr:
            fail("echo no-op proof was accepted")

        write_manifest(
            repo,
            ["npx", "--yes", "--package", "react-doctor", "react-doctor", "targeted"],
        )
        rejected = run(repo)
        if rejected.returncode == 0 or "exact semver or @latest" not in rejected.stderr:
            fail("unpinned npx package was accepted")
        write_manifest(
            repo,
            ["npx", "--yes", "--package", "react-doctor@0.9.2", "sh", "-c", "true"],
        )
        rejected = run(repo)
        if rejected.returncode == 0 or "forbidden package binary" not in rejected.stderr:
            fail("pinned npx decoy wrapped a shell command")
        (repo / "hard-eng.gates.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "families": {
                        "fallow": [
                            "npx",
                            "--yes",
                            "fallow@3.10.0",
                            "audit",
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )
        rejected = subprocess.run(
            [
                sys.executable,
                str(GATE),
                "run",
                "--repo",
                str(repo),
                "--timeout",
                "30",
                "--family",
                "fallow",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if rejected.returncode == 0 or "requires fallow@latest" not in rejected.stderr:
            fail("version-pinned Fallow bypassed latest enforcement")
        latest_commands = {
            "fallow": [
                "npx",
                "--yes",
                "fallow@latest",
                "--fail-on-issues",
                "--format",
                "json",
                "--quiet",
            ],
            "react-doctor": [
                "npx",
                "--yes",
                "react-doctor@latest",
                ".",
                "--scope",
                "full",
                "--blocking",
                "warning",
                "--no-respect-inline-disables",
            ],
            "dart-decimate": ["npx", "--yes", "dart-decimate@latest", "json", "."],
        }
        (repo / "hard-eng.gates.json").write_text(
            json.dumps({"schema_version": 1, "families": latest_commands}),
            encoding="utf-8",
        )
        try:
            loaded = load_manifest(repo)
        except ProjectGateError as error:
            fail(f"canonical latest commands were rejected: {error}")
        if any(list(loaded[family]) != command for family, command in latest_commands.items()):
            fail("canonical latest commands changed during validation")
        scoped_commands = {
            "fallow": [
                "npx",
                "--yes",
                "fallow@latest",
                "audit",
                "--changed-since",
                "main",
            ],
            "react-doctor": [
                "npx",
                "--yes",
                "react-doctor@latest",
                ".",
                "--scope",
                "changed",
                "--blocking",
                "warning",
            ],
            "dart-decimate": [
                "npx",
                "--yes",
                "dart-decimate@latest",
                "audit",
                ".",
                "--base",
                "main",
            ],
        }
        for family, command in scoped_commands.items():
            (repo / "hard-eng.gates.json").write_text(
                json.dumps(
                    {"schema_version": 1, "families": {family: command}}
                ),
                encoding="utf-8",
            )
            try:
                load_manifest(repo)
            except ProjectGateError:
                pass
            else:
                fail(f"{family} accepted a changed/baseline-only quality gate")

        unsafe = repo / "scripts/unsafe.mjs"
        unsafe.parent.mkdir()
        unsafe.write_text(
            "import { spawnSync } from 'node:child_process';\n"
            "spawnSync('git', ['status']);\n",
            encoding="utf-8",
        )
        write_manifest(repo, [sys.executable, "targeted-check.py"])
        rejected = run(repo)
        if rejected.returncode == 0 or "Git child process" not in rejected.stderr:
            fail("project gate skipped Git environment hygiene")
        unsafe.unlink()

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

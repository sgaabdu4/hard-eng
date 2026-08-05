#!/usr/bin/env python3
"""Focused regressions for repository-owned project gate commands."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from git_env import git_env, scrub_environ
from project_gate import ProjectGateError, load_manifest, validate_quality_report

SCRIPT_DIR = Path(__file__).resolve().parent
GATE = SCRIPT_DIR / "project_gate.py"
ROOT = SCRIPT_DIR.parents[2]

# The overrun proof bounds elapsed time against the killed command's own sleep,
# never a host wall-clock constant: spawn cost scales with load, the sleep does not.
OVERRUN_SLEEP = 5.0

scrub_environ(ceiling=tempfile.gettempdir())


def fail(message: str) -> None:
    raise SystemExit(f"project-gate-check: FAIL: {message}")


def write_families(repo: Path, families: dict[str, list[str]]) -> None:
    (repo / "hard-eng.gates.json").write_text(
        json.dumps({"schema_version": 1, "families": families}),
        encoding="utf-8",
    )


def gate_command(repo: Path, family: str, timeout: str = "30") -> list[str]:
    return [
        sys.executable,
        str(GATE),
        "run",
        "--repo",
        str(repo),
        "--timeout",
        timeout,
        "--family",
        family,
    ]


def invoke(
    repo: Path,
    family: str = "targeted",
    timeout: str = "30",
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        gate_command(repo, family, timeout),
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )


def check_migration_contract() -> None:
    required = {
        "AGENTS.md": "`gate-migration` before first product mutation",
        "skills/deterministic-checks/SKILL.md": (
            "[Gate migration](references/gate-migration.md)"
        ),
        "skills/deterministic-checks/references/gate-migration.md": (
            "baseline + wiring + feature diff mixing = forbidden"
        ),
        "skills/he-build/SKILL.md": (
            "`gate-migration` pauses the slice without resetting PLAN state"
        ),
        "skills/he-ship/SKILL.md": "Ship never wires it",
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            fail(f"gate migration contract missing from {relative}")


def check_quality_report() -> None:
    clean = {
        "kind": "combined",
        "check": {"total_issues": 0},
        "dupes": {"clone_groups": [], "clone_families": []},
        "health": {"findings": []},
    }
    validate_quality_report("fallow", json.dumps(clean))
    finding = {
        **clean,
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
        validate_quality_report("fallow", json.dumps(finding))
    except ProjectGateError as error:
        if "health=1" not in str(error) or "src/owner.ts:7" not in str(error):
            fail("Fallow finding failure lost compact evidence")
    else:
        fail("Fallow exit-zero findings were accepted")
    for malformed in ("", "{}", json.dumps({**clean, "kind": "audit"})):
        try:
            validate_quality_report("fallow", malformed)
        except ProjectGateError:
            continue
        fail("malformed or scoped Fallow report was accepted")


def latest_commands() -> dict[str, list[str]]:
    return {
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
        "dart-decimate": [
            "npx",
            "--yes",
            "dart-decimate@latest",
            "json",
            ".",
            "--workspace",
            "functions/example",
        ],
    }


def check_npx_contract(repo: Path) -> None:
    write_families(
        repo,
        {
            "fallow": [
                "npx",
                "--yes",
                "fallow@3.10.0",
                "audit",
            ]
        },
    )
    rejected = invoke(repo, "fallow")
    if rejected.returncode == 0 or "requires fallow@latest" not in rejected.stderr:
        fail("version-pinned Fallow bypassed latest enforcement")

    commands = latest_commands()
    write_families(repo, commands)
    try:
        loaded = load_manifest(repo)
    except ProjectGateError as error:
        fail(f"canonical latest commands were rejected: {error}")
    if any(list(loaded[name]) != command for name, command in commands.items()):
        fail("canonical latest commands changed during validation")

    wrapper = repo / "tools/npx"
    wrapper.parent.mkdir()
    wrapper.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    wrapper.chmod(0o755)
    write_families(repo, {"fallow": [str(wrapper), *commands["fallow"][1:]]})
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "literal npx" not in str(error):
            fail("repo-local npx wrapper failed for the wrong reason")
    else:
        fail("repo-local npx wrapper path was accepted")

    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = f"{wrapper.parent}{os.pathsep}{previous_path}"
    try:
        write_families(repo, {"fallow": commands["fallow"]})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if "outside" not in str(error):
                fail("repo-local npx resolution failed for the wrong reason")
        else:
            fail("literal npx resolved to a repo-local wrapper")
    finally:
        os.environ["PATH"] = previous_path

    runtime = repo / "node_modules/fallow"
    runtime.mkdir(parents=True)
    write_families(repo, {"fallow": commands["fallow"]})
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "scanner runtime" not in str(error):
            fail("extraneous scanner runtime failed for the wrong reason")
    else:
        fail("extraneous project-local scanner runtime was accepted")
    shutil.rmtree(repo / "node_modules")

    binary_root = repo / "node_modules/.bin"
    binary_root.mkdir(parents=True)
    binary = binary_root / "react-doctor"
    binary.symlink_to(repo / "missing-react-doctor")
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "scanner binary" not in str(error):
            fail("scanner binary symlink failed for the wrong reason")
    else:
        fail("project-local scanner binary symlink was accepted")
    shutil.rmtree(repo / "node_modules")

    package = repo / "package.json"
    for scanner in ("dart-decimate", "fallow", "react-doctor"):
        package.write_text(
            json.dumps({"devDependencies": {scanner: "latest"}}),
            encoding="utf-8",
        )
        write_families(repo, {"fallow": commands["fallow"]})
        try:
            load_manifest(repo)
        except ProjectGateError as error:
            if "dependencies" not in str(error):
                fail(f"local {scanner} dependency failed for the wrong reason")
        else:
            fail(f"local {scanner} dependency was accepted")
    package.unlink()

    (repo / ".gitignore").write_text("package.json\n", encoding="utf-8")
    package.write_text(
        json.dumps({"dependencies": {"fallow": "latest"}}),
        encoding="utf-8",
    )
    try:
        load_manifest(repo)
    except ProjectGateError as error:
        if "dependencies" not in str(error):
            fail("ignored root package.json failed for the wrong reason")
    else:
        fail("ignored root package.json scanner dependency was accepted")
    package.unlink()
    (repo / ".gitignore").unlink()

    wrapper.unlink()
    wrapper.parent.rmdir()

    scoped = {
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
    for family, command in scoped.items():
        write_families(repo, {family: command})
        try:
            load_manifest(repo)
        except ProjectGateError:
            continue
        fail(f"{family} accepted a changed/baseline-only quality gate")


def check_execution(repo: Path) -> None:
    script = repo / "targeted-check.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    write_families(repo, {"targeted": [sys.executable, script.name]})
    if invoke(repo).returncode:
        fail("valid repository-owned argv failed")

    for invalid in ("0", "-1", "nan", "inf"):
        rejected = invoke(repo, timeout=invalid)
        if (
            rejected.returncode == 0
            or "timeout must be finite and positive" not in rejected.stderr
            or "Traceback" in rejected.stderr
        ):
            fail(f"invalid whole-run timeout was accepted: {invalid}")

    overrun = repo / "overrun.txt"
    script.write_text(
        "import time\n"
        "from pathlib import Path\n"
        f"time.sleep({OVERRUN_SLEEP})\n"
        "Path('overrun.txt').write_text('ran\\n', encoding='utf-8')\n",
        encoding="utf-8",
    )
    started = time.monotonic()
    rejected = invoke(repo, timeout="0.1")
    elapsed = time.monotonic() - started
    if (
        rejected.returncode == 0
        or elapsed > OVERRUN_SLEEP / 2
        or overrun.exists()
    ):
        fail("whole-run timeout allowed an internal command to overrun")

    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    deleted = repo / "deleted-owner.txt"
    deleted.write_text("tracked\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "add", deleted.name],
        check=True,
        env=git_env(),
    )
    deleted.unlink()
    if invoke(repo).returncode:
        fail("gate could not snapshot an intentional tracked deletion")

    write_families(repo, {"targeted": ["echo", "targeted"]})
    rejected = invoke(repo)
    if rejected.returncode == 0 or "forbidden no-op/shell" not in rejected.stderr:
        fail("echo no-op proof was accepted")

    write_families(
        repo,
        {
            "targeted": [
                "npx",
                "--yes",
                "--package",
                "react-doctor",
                "react-doctor",
                "targeted",
            ]
        },
    )
    rejected = invoke(repo)
    if rejected.returncode == 0 or "exact semver or @latest" not in rejected.stderr:
        fail("unpinned npx package was accepted")

    unsafe = repo / "scripts/unsafe.mjs"
    unsafe.parent.mkdir()
    unsafe.write_text(
        "import { spawnSync } from 'node:child_process';\n"
        "spawnSync('git', ['status']);\n",
        encoding="utf-8",
    )
    write_families(repo, {"targeted": [sys.executable, script.name]})
    rejected = invoke(repo)
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
    rejected = invoke(repo)
    if rejected.returncode == 0 or "mutated the repository tree" not in rejected.stderr:
        fail("mutation of a required ignored input was accepted")


def main() -> int:
    check_migration_contract()
    check_quality_report()
    with tempfile.TemporaryDirectory(prefix="hard-eng-project-gate-") as temporary:
        repo = Path(temporary)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
        check_execution(repo)
        check_npx_contract(repo)
    print("project-gate-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""A repository whose only active briefs are still planning takes the direct protected receipt."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_hook_contract_lib import FAILURES, ROOT, authorize_protected_direct, check, denial, manifest, plan, run_hook

sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env

KIND = "data-deletion-or-destructive-schema"


def planning_repository(root: Path) -> Path:
    repo = root / "protected-planning"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    plan(repo, "one", "planning")
    plan(repo, "two", "planning")
    return repo


def check_shell_action(repo: Path, env: dict[str, str]) -> None:
    payload = {
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": "git stash drop stash@{0}", "description": "release entry"},
    }
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=env)
    check(
        "planning-only protected shell denies without authorization", bool(denial(response, "claude")), repr(response)
    )
    approved = authorize_protected_direct(repo, payload, KIND, "fixture stash entry")
    check("planning-only repository records a direct protected receipt", approved.returncode == 0, approved.stderr)
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=env)
    check("approved shell action runs once beside planning briefs", response is None, repr(response))
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=env)
    check("direct approval beside planning briefs is one-use", bool(denial(response, "claude")), repr(response))


def check_external_action(repo: Path, env: dict[str, str]) -> None:
    external = {"cwd": str(repo), "tool_name": "mcp__appwrite__deleteRows", "tool_input": {"table": "users"}}
    response, _ = run_hook("claude", "pretooluse", dict(external), env=env)
    check("planning-only external destructive tool denies", bool(denial(response, "claude")), repr(response))
    approved = authorize_protected_direct(repo, external, KIND, "users table")
    check("planning-only external authorization records", approved.returncode == 0, approved.stderr)
    response, _ = run_hook("claude", "pretooluse", dict(external), env=env)
    check("approved external destructive tool runs once beside planning briefs", response is None, repr(response))


def main() -> int:
    env = {key: value for key, value in os.environ.items() if not key.startswith("HARD_ENG_")}
    with tempfile.TemporaryDirectory(prefix="hard-eng-protected-planning-") as temporary:
        repo = planning_repository(Path(temporary).resolve())
        check_shell_action(repo, env)
        check_external_action(repo, env)
    if FAILURES:
        for failure in FAILURES:
            print(f"protected-planning-contract: FAIL: {failure}", file=sys.stderr)
        return 1
    print("protected-planning-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

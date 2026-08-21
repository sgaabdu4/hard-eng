#!/usr/bin/env python3
"""Regression proof for recovering an approved brief with lost authorization."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[3]
STATE_PATH = ROOT / "skills/he/scripts/plan_state.py"
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import git_env

AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
APPROVAL_CONTEXT = (
    "--session-id",
    "he-plan-contract",
    "--request-digest",
    "sha256:" + "d" * 64,
    "--allowed-action",
    "build-and-verify",
)


def fail(message: str) -> NoReturn:
    raise SystemExit(f"authorization-recovery-regression: {message}")


def filled(text: str) -> str:
    replacements = {
        "## Outcome\n- TBD": "## Outcome\n- A user receives one observable result.",
        "## Non-goals\n- TBD": "## Non-goals\n- Adjacent workflow changes are excluded.",
        "## Material decisions\n- TBD": "## Material decisions\n- Existing policy remains canonical.",
        "- ux_reference = TBD": "- ux_reference = n/a",
        "- ux_reference_sources = TBD": "- ux_reference_sources = n/a",
        "## Acceptance examples\n- TBD": (
            "## Acceptance examples\n- Given an eligible user, when they act, then the result is visible."
        ),
        "## Affected canonical areas\n- TBD": ("## Affected canonical areas\n- Existing command owner and route."),
        "- rollback = TBD": "- rollback = disable the route and preserve stored state.",
        "## First vertical slice\n- S-1 = TBD\n- proof = TBD": (
            "## First vertical slice\n"
            "- S-1 = command to stored result to visible response.\n"
            "- proof = focused behavior test."
        ),
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def git_repo(path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(path)], check=True, env=git_env(ceiling=tempfile.gettempdir()))


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(STATE_PATH), *args], cwd=repo, check=False, capture_output=True, text=True
    )


def check(state) -> None:
    with tempfile.TemporaryDirectory() as directory:
        repo = Path(directory).resolve()
        git_repo(repo)
        plan = repo / "features/lean-loop/PLAN.md"
        plan.parent.mkdir(parents=True)
        approved, _ = state.approval_candidate(filled(state.template("lean-loop", "lean-loop-test")))
        plan.write_text(approved, encoding="utf-8")
        context = ("--session-id", "he-plan-contract", "--request-digest", "sha256:" + "d" * 64)
        missing = run(repo, "inspect", "--repo", str(repo), "--plan", str(plan))
        if missing.returncode == 0 or "authorization.json" not in missing.stderr:
            fail("missing authorization receipt passed inspection")
        token = state.token_for(approved)
        rejected = run(
            repo,
            "reopen",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            token,
            "--reason",
            "changed-outcome",
            *context,
        )
        if rejected.returncode == 0 or plan.read_text(encoding="utf-8") != approved:
            fail("ordinary reopen bypassed a missing authorization receipt")
        recovered = run(
            repo,
            "reopen",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            token,
            "--reason",
            "changed-outcome",
            "--recover-invalid-authorization",
            *context,
        )
        if recovered.returncode != 0:
            fail(f"missing authorization recovery failed: {recovered.stderr}")
        reopened = plan.read_text(encoding="utf-8")
        reopened_state = state.validate_text(reopened)
        if (reopened_state["lifecycle_status"], reopened_state["approval_status"]) != ("planning", "pending"):
            fail("authorization recovery did not return the brief to planning")
        reapproved = run(
            repo,
            "approve",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            state.token_for(reopened),
            "--approval-reply",
            AUTONOMOUS_DIRECTIVE,
            *APPROVAL_CONTEXT,
        )
        if reapproved.returncode != 0:
            fail(f"reapproval after recovery failed: {reapproved.stderr}")
        valid = plan.read_text(encoding="utf-8")
        normal = run(
            repo,
            "reopen",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            state.token_for(valid),
            "--reason",
            "changed-outcome",
            *context,
        )
        if normal.returncode != 0:
            fail(f"valid authorization receipt could not reopen: {normal.stderr}")
        pending = plan.read_text(encoding="utf-8")
        reapproved = run(
            repo,
            "approve",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            state.token_for(pending),
            "--approval-reply",
            AUTONOMOUS_DIRECTIVE,
            *APPROVAL_CONTEXT,
        )
        if reapproved.returncode != 0:
            fail(f"reapproval for stale-receipt fixture failed: {reapproved.stderr}")
        auth_path = plan.parent / "receipts" / "authorization.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        auth["expires_at_epoch"] = 0
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        stale = plan.read_text(encoding="utf-8")
        stale_rejected = run(
            repo,
            "reopen",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            state.token_for(stale),
            "--reason",
            "changed-outcome",
            *context,
        )
        if stale_rejected.returncode == 0 or plan.read_text(encoding="utf-8") != stale:
            fail("ordinary reopen bypassed an expired authorization receipt")
        stale_recovered = run(
            repo,
            "reopen",
            "--repo",
            str(repo),
            "--plan",
            str(plan),
            "--expect-token",
            state.token_for(stale),
            "--reason",
            "changed-outcome",
            "--recover-invalid-authorization",
            *context,
        )
        if stale_recovered.returncode != 0:
            fail(f"expired authorization recovery failed: {stale_recovered.stderr}")
        stale_state = state.validate_text(plan.read_text(encoding="utf-8"))
        if (stale_state["lifecycle_status"], stale_state["approval_status"]) != ("planning", "pending"):
            fail("expired authorization recovery did not return the brief to planning")


if __name__ == "__main__":
    raise SystemExit("state module is supplied by the he-plan contract runner")

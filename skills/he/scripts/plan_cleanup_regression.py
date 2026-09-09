#!/usr/bin/env python3
"""Regression checks for exact-inventory PLAN cleanup."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STATE = SCRIPTS / "plan_state.py"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS.parents[1] / "deterministic-checks/scripts"))
import plan_state
from git_env import git_env
from script_runner import ScriptResult, run_script


def fail(message: str) -> None:
    raise SystemExit(f"plan-cleanup-regression: {message}")


def run(*args: str) -> ScriptResult:
    return run_script(STATE, args)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def cancelled(slug: str) -> str:
    text = plan_state.template(slug, f"{slug}-fixture")
    text = plan_state.render_state(
        text,
        {
            "lifecycle_status": "cancelled",
            "approval_status": "pending",
            "approval_fingerprint": "none",
            "approval_provenance": "none",
            "green_artifact": "none",
            "active_slice": "none",
            "completed_slices": "none",
            "next_action": "Cancelled by fixture decision.",
            "replan_reason": "none",
        },
    )
    plan_state.validate_text(text)
    return text


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-plan-cleanup-") as temporary:
        repo = Path(temporary) / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
        malformed = repo / "features/legacy/PLAN.md"
        terminal = repo / "features/terminal/PLAN.md"
        active = repo / "features/active/PLAN.md"
        draft_plan = repo / "features/draft/PLAN.md"
        receipt = repo / "features/legacy/receipts/keep.json"
        ticket = repo / "features/legacy/tickets/T-1.md"
        write(malformed, "# legacy\n- lifecycle_status = building\n")
        write(terminal, cancelled("terminal"))
        write(active, plan_state.template("active", "active-fixture"))
        write(draft_plan, plan_state.template("draft", "draft-fixture"))
        write(receipt, "{}\n")
        write(ticket, "# keep\n")
        subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=git_env())
        subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
            ],
            check=True,
            env=git_env(),
        )
        malformed_hash, terminal_hash, active_hash = digest(malformed), digest(terminal), digest(active)
        private = repo / "features/private/PLAN.md"
        write(private, cancelled("private"))
        private_hash = digest(private)
        draft_token = plan_state.token_for(draft_plan.read_text(encoding="utf-8"))
        candidate = Path(temporary) / "draft-candidate.md"
        candidate_text = draft_plan.read_text(encoding="utf-8").replace(
            "## Outcome\n- TBD", "## Outcome\n- Draft command works.", 1
        )
        write(candidate, candidate_text)
        stale = run(
            "draft",
            "--repo",
            str(repo),
            "--plan",
            "features/draft/PLAN.md",
            "--expect-token",
            "sha256:" + "0" * 64,
            "--candidate",
            str(candidate),
        )
        if stale.returncode == 0 or draft_plan.read_text(encoding="utf-8") == candidate_text:
            fail("stale draft token must not mutate")
        tampered = Path(temporary) / "draft-tampered.md"
        write(tampered, candidate_text.replace("- active_slice = S-1", "- active_slice = none", 1))
        rejected = run(
            "draft",
            "--repo",
            str(repo),
            "--plan",
            "features/draft/PLAN.md",
            "--expect-token",
            draft_token,
            "--candidate",
            str(tampered),
        )
        if rejected.returncode == 0 or "preserve the exact title and State block" not in rejected.stderr:
            fail("draft State mutation must fail")
        drafted = run(
            "draft",
            "--repo",
            str(repo),
            "--plan",
            "features/draft/PLAN.md",
            "--expect-token",
            draft_token,
            "--candidate",
            str(candidate),
        )
        if drafted.returncode != 0 or draft_plan.read_text(encoding="utf-8") != candidate_text:
            fail(f"valid draft failed: {drafted.stderr}")
        common = ["--repo", str(repo), "--decision", "Delete the obsolete legacy plans."]
        wrong = run("cleanup", *common, "--item", f"features/legacy/PLAN.md={'0' * 64}")
        if wrong.returncode == 0 or malformed_hash != digest(malformed):
            fail("wrong hash must fail without mutation")
        preview = run(
            "cleanup",
            *common,
            "--item",
            f"features/legacy/PLAN.md={malformed_hash}",
            "--item",
            f"features/terminal/PLAN.md=sha256:{terminal_hash}",
        )
        if preview.returncode != 0 or "result=preview" not in preview.stdout:
            fail(f"preview failed: {preview.stderr}")
        for marker in ("invalid->cancelled->removed", "terminal->removed", "requires_confirm_cancel=yes"):
            if marker not in preview.stdout:
                fail(f"preview omitted {marker}")
        exclude = Path(
            subprocess.run(
                ["git", "-C", str(repo), "rev-parse", "--git-path", "info/exclude"],
                check=True,
                capture_output=True,
                text=True,
                env=git_env(),
            ).stdout.strip()
        )
        if not exclude.is_absolute():
            exclude = repo / exclude
        if exclude.exists() and "Hard Eng" in exclude.read_text(encoding="utf-8"):
            fail("preview changed Git exclude")
        active_result = run(
            "cleanup", *common, "--item", f"features/active/PLAN.md={active_hash}", "--apply", "--confirm-delete"
        )
        if active_result.returncode == 0 or "--confirm-cancel" not in active_result.stderr or not active.exists():
            fail("valid active PLAN requires cancellation confirmation")
        applied = run(
            "cleanup",
            *common,
            "--item",
            f"features/legacy/PLAN.md={malformed_hash}",
            "--item",
            f"features/terminal/PLAN.md={terminal_hash}",
            "--item",
            f"features/active/PLAN.md={active_hash}",
            "--apply",
            "--confirm-cancel",
            "--confirm-delete",
        )
        if applied.returncode != 0 or "result=removed" not in applied.stdout:
            fail(f"apply failed: {applied.stderr}")
        if malformed.exists() or terminal.exists() or active.exists() or not receipt.exists() or not ticket.exists():
            fail("cleanup removed the wrong paths")
        untracked = run(
            "cleanup", *common, "--item", f"features/private/PLAN.md={private_hash}", "--apply", "--confirm-delete"
        )
        if untracked.returncode != 0 or "result=removed" not in untracked.stdout or private.exists():
            fail(f"git-private terminal PLAN cleanup failed: {untracked.stderr}")
        note_rows = [
            line.removeprefix("recovery_note=")
            for line in applied.stdout.splitlines()
            if line.startswith("recovery_note=")
        ]
        if len(note_rows) != 1:
            fail("apply omitted recovery note")
        note_path = Path(note_rows[0])
        metadata = os.lstat(note_path)
        if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
            fail("recovery note must be a private regular file")
        note = json.loads(note_path.read_text(encoding="utf-8"))
        if note.get("status") != "completed" or len(note.get("completed", [])) != 3:
            fail("recovery note did not complete all entries")
        entries = note.get("entries", [])
        if len(entries) != 3 or any("restore_command" not in row for row in entries):
            fail("recovery note lacks restore commands")
        legacy = next(row for row in entries if row["path"] == "features/legacy/PLAN.md")
        if legacy["terminal_status"] != "cancelled" or not legacy["terminal_hash"].startswith("sha256:"):
            fail("invalid legacy route lacks terminal evidence")
        exclude_text = exclude.read_text(encoding="utf-8")
        active_entry = next(row for row in entries if row["path"] == "features/active/PLAN.md")
        if active_entry["route"] != "nonterminal->cancelled->removed":
            fail("valid active route did not pass through cancelled")
        for slug in ("legacy", "terminal", "active"):
            if f"/features/{slug}/PLAN.md" not in exclude_text:
                fail(f"missing exact exclude for {slug}")
        repeated = run("cleanup", *common, "--item", f"features/legacy/PLAN.md={malformed_hash}")
        if repeated.returncode == 0:
            fail("removed preimage must not be reusable")
    print("plan-cleanup-regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

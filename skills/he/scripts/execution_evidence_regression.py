#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))
import plan_state
from git_env import git_env

OWNER = Path(__file__).with_name("execution_evidence.py")
PLAN_STATE = Path(__file__).with_name("plan_state.py")
AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."
STOP_BEFORE = [
    "data-deletion-or-destructive-schema",
    "force-or-history-rewrite",
    "machine-scope-write",
    "secret-exposure",
]
AUTHORIZATION_FIELDS = {
    "allowed",
    "approval_digest",
    "approved_at",
    "effect",
    "mode",
    "plan_fingerprint",
    "plan_id",
    "schema_version",
    "stop_before",
    "target",
}
DIRECT_FIELDS = {
    "allowed",
    "created_at",
    "decision",
    "external_actions",
    "fresh_until",
    "intended_paths",
    "question",
    "repository_context",
    "route",
    "schema_version",
    "scope",
    "source_versions",
    "sources",
    "stop_before",
    "unknown",
    "verified",
    "write_nonce",
}
BRIEF_SECTIONS = """
## Outcome
- A complete behavior is delivered.

## Non-goals
- Unrelated work is excluded.

## Material decisions
- Existing owners remain canonical.
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given valid input, when the action runs, then the result is visible.

## Affected canonical areas
- Existing owner + test.

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = revert the change.
- deferred = none
- blocked_on = none

## First vertical slice
- S-1 = complete the behavior.
- proof = focused test + full gate.
"""


def brief_fp(plan: Path) -> str:
    text = plan.read_text(encoding="utf-8")
    return plan_state.frozen_fingerprint(plan_state.parse_sections(text))


def protected_digest(value: str) -> str:
    payload = json.dumps(
        {"tool_input": {"table": "events", "value": value}, "tool_name": "mcp__appwrite__createrow"},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(payload.encode("ascii")).hexdigest()


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(OWNER), *args], cwd=repo, text=True, capture_output=True, check=False)


def run_plan(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(PLAN_STATE), *args], cwd=repo, text=True, capture_output=True, check=False
    )


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"execution-evidence regression: FAIL: {message}")


def commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True, env=git_env())
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Hard Eng Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            message,
        ],
        check=True,
        env=git_env(),
    )


def fixture(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    plan = repo / "features" / "proof" / "PLAN.md"
    plan.parent.mkdir(parents=True)
    (repo / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
    plan.write_text(
        "# Feature Brief: Proof\n\n"
        "<!-- hard-eng-state:v1 -->\n"
        "- state_version = 1\n"
        "- plan_id = proof-12345678\n"
        "- lifecycle_status = planning\n"
        "- approval_status = pending\n"
        "- approval_fingerprint = none\n"
        "<!-- /hard-eng-state -->\n" + BRIEF_SECTIONS,
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    return repo, plan


def approval_fixture(root: Path) -> tuple[Path, Path, str]:
    repo = root / "approval"
    plan = repo / "features" / "approval" / "PLAN.md"
    plan.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    (repo / "hard-eng.gates.json").write_text(
        json.dumps({"schema_version": 1, "enforcement": {"schema_version": 1}}), encoding="utf-8"
    )
    text = """# Feature Brief: Approval

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = approval-12345678
- lifecycle_status = planning
- approval_status = pending
- approval_fingerprint = none
- approval_provenance = none
- green_artifact = none
- active_slice = S-1
- completed_slices = none
- next_action = Request approval.
- replan_reason = none
<!-- /hard-eng-state -->

## Outcome
- A complete behavior is delivered.

## Non-goals
- Unrelated work is excluded.

## Material decisions
- Existing owners remain canonical.
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given valid input, when the action runs, then the result is visible.

## Affected canonical areas
- Existing owner + test.

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = revert the change.
- deferred = none
- blocked_on = none

## First vertical slice
- S-1 = complete the behavior.
- proof = focused test + full gate.
"""
    plan.write_text(text, encoding="utf-8")
    digest = "sha256:" + __import__("hashlib").sha256(text.encode()).hexdigest()
    return repo, plan, digest


def record_approval_research(repo: Path, plan: Path) -> subprocess.CompletedProcess[str]:
    return run(
        repo,
        "record-research",
        "--repo",
        str(repo),
        "--plan",
        str(plan),
        "--scope",
        "local",
        "--question",
        "Which gate applies?",
        "--decision",
        "Use hard-eng.gates.json.",
        "--source",
        "hard-eng.gates.json",
        "--verified",
        "The manifest enables enforcement.",
        "--fresh-until",
        "2099-12-31",
        "--unknown",
        "none",
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-evidence-") as temporary:
        root = Path(temporary).resolve()
        repo, plan = fixture(root)
        relative = str(plan.relative_to(repo))
        FINGERPRINT = brief_fp(plan)

        missing = run(repo, "check", "--repo", str(repo), "--plan", relative)
        require(missing.returncode != 0, "missing evidence passed")

        bad_external = run(
            repo,
            "record-research",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--scope",
            "external",
            "--question",
            "What is current?",
            "--decision",
            "Use the current contract.",
            "--source",
            "AGENTS.md",
            "--source-version",
            "retrieved-2026-08-14",
            "--verified",
            "The rule exists.",
            "--fresh-until",
            "2099-12-31",
            "--unknown",
            "none",
        )
        require(bad_external.returncode != 0, "external research accepted no HTTPS source")

        recorded = run(
            repo,
            "record-research",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--scope",
            "local",
            "--question",
            "Which local owner applies?",
            "--decision",
            "Use AGENTS.md.",
            "--source",
            "AGENTS.md",
            "--verified",
            "AGENTS.md owns the rule.",
            "--fresh-until",
            "2099-12-31",
            "--unknown",
            "none",
        )
        require(recorded.returncode == 0, recorded.stderr)

        empty_reply = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            "",
        )
        require(empty_reply.returncode != 0, "empty reply authorized execution")

        standard = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            "yes, ship it",
        )
        require(standard.returncode == 0, standard.stderr)
        auth_path = plan.parent / "receipts" / "authorization.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(auth["mode"] == "standard", "a plain reply produced the wrong mode")
        require(auth["allowed"] == ["approved-build"], "standard authorization recorded extra actions")
        require(set(auth) == AUTHORIZATION_FIELDS, f"authorization receipt carries stale fields: {sorted(auth)}")
        require("expires_at" not in auth, "authorization receipt still carries an expiry")
        require("session_digest" not in auth, "authorization receipt still carries a session digest")
        require("request_digest" not in auth, "authorization receipt still carries a request digest")
        require("repository_context" not in auth, "authorization receipt still carries repository context")

        with_extra = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            "yes, and use subagents",
            "--allowed-action",
            "parallel-subagents",
        )
        require(with_extra.returncode == 0, with_extra.stderr)
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(
            set(auth["allowed"]) == {"approved-build", "parallel-subagents"},
            "standard authorization lost the requested action",
        )

        bad_action = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            "yes",
            "--allowed-action",
            "named-deployment",
        )
        require(bad_action.returncode != 0, "standard authorization accepted an autonomous-only action")

        auth["allowed"] = [*auth["allowed"], "named-deployment"]
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        overbroad = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(overbroad.returncode != 0, "an authorization with an out-of-scope action passed check")

        autonomous = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            AUTONOMOUS_DIRECTIVE,
            "--allowed-action",
            "build-and-verify",
            "--allowed-action",
            "parallel-subagents",
        )
        require(autonomous.returncode == 0, autonomous.stderr)
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(auth["mode"] == "autonomous", "the exact autonomous directive was not recorded as autonomous mode")
        require(auth["stop_before"] == STOP_BEFORE, "autonomous stop boundary drifted")
        require(
            set(auth["allowed"]) == {"build-and-verify", "parallel-subagents"},
            "autonomous authorization did not record its requested actions",
        )

        checked = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(checked.returncode == 0, checked.stderr)

        (repo / "unrelated.py").write_text("changed = True\n", encoding="utf-8")
        edited_tree = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(
            edited_tree.returncode == 0, f"an uncommitted tree edit invalidated authorization: {edited_tree.stderr}"
        )

        commit_all(repo, "fixture identity")
        committed = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(committed.returncode == 0, f"a commit invalidated authorization: {committed.stderr}")

        auth["plan_fingerprint"] = "sha256:" + "b" * 64
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        tampered = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(tampered.returncode != 0, "a tampered plan_fingerprint passed check")

        fixed = run(
            repo,
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--fingerprint",
            FINGERPRINT,
            "--approval-reply",
            "yes, restore it",
        )
        require(fixed.returncode == 0, fixed.stderr)
        refixed = run(repo, "check", "--repo", str(repo), "--plan", relative, "--fingerprint", FINGERPRINT)
        require(refixed.returncode == 0, refixed.stderr)

        plan.write_text(
            plan.read_text(encoding="utf-8")
            .replace("lifecycle_status = planning", "lifecycle_status = building")
            .replace("approval_status = pending", "approval_status = approved")
            .replace("approval_fingerprint = none", f"approval_fingerprint = {FINGERPRINT}"),
            encoding="utf-8",
        )
        protected = [
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--kind",
            "data-deletion-or-destructive-schema",
            "--target",
            "events row",
            "--effect",
            "permanently delete one events row",
            "--tool-name",
            "mcp__appwrite__deleteRow",
            "--action-digest",
            protected_digest("one"),
        ]
        protected_consume = [
            "--repo",
            str(repo),
            "--plan",
            relative,
            "--kind",
            "data-deletion-or-destructive-schema",
            "--tool-name",
            "mcp__appwrite__deleteRow",
            "--action-digest",
            protected_digest("one"),
        ]
        blank_reply = run(repo, "authorize-protected", *protected, "--approval-reply", "   ")
        require(blank_reply.returncode != 0, "a blank protected approval reply was authorized")
        action_authorized = run(repo, "authorize-protected", *protected, "--approval-reply", "yes, delete it")
        require(action_authorized.returncode == 0, action_authorized.stderr)

        wrong_kind = list(protected_consume)
        wrong_kind[wrong_kind.index("data-deletion-or-destructive-schema")] = "force-or-history-rewrite"
        wrong_kind_result = run(repo, "consume-protected", *wrong_kind)
        require(wrong_kind_result.returncode != 0, "consume with a mismatched kind passed")
        wrong_tool = list(protected_consume)
        wrong_tool[wrong_tool.index("mcp__appwrite__deleteRow")] = "mcp__appwrite__updateRow"
        wrong_tool_result = run(repo, "consume-protected", *wrong_tool)
        require(wrong_tool_result.returncode != 0, "consume with a mismatched tool name passed")
        wrong_digest = list(protected_consume)
        wrong_digest[-1] = protected_digest("two")
        wrong_digest_result = run(repo, "consume-protected", *wrong_digest)
        require(wrong_digest_result.returncode != 0, "consume with a mismatched action digest passed")

        consumed_action = run(repo, "consume-protected", *protected_consume)
        require(consumed_action.returncode == 0, consumed_action.stderr)
        duplicate_action = run(repo, "consume-protected", *protected_consume)
        require(duplicate_action.returncode != 0, "a consumed protected action was reused")

        reauthorized = run(repo, "authorize-protected", *protected, "--approval-reply", "yes, delete it again")
        require(reauthorized.returncode == 0, reauthorized.stderr)
        reconsumed = run(repo, "consume-protected", *protected_consume)
        require(reconsumed.returncode == 0, reconsumed.stderr)

        (repo / "notes.txt").write_text("local notes\n", encoding="utf-8")
        started = run(
            repo,
            "start-direct",
            "--repo",
            str(repo),
            "--intended-path",
            "notes.txt",
            "--scope",
            "local",
            "--question",
            "Where do notes live?",
            "--decision",
            "Use notes.txt.",
            "--source",
            "notes.txt",
            "--verified",
            "notes.txt exists.",
            "--fresh-until",
            "2099-12-31",
            "--unknown",
            "none",
        )
        require(started.returncode == 0, started.stderr)
        direct_path = repo / ".git" / "hard-eng" / "current-direct.json"
        direct_value = json.loads(direct_path.read_text(encoding="utf-8"))
        require(set(direct_value) == DIRECT_FIELDS, f"direct receipt carries stale fields: {sorted(direct_value)}")
        require(direct_value["allowed"] == ["reversible-local-work"], "a plain direct route recorded extra actions")

        check_started = run(repo, "check-direct", "--repo", str(repo))
        require(check_started.returncode == 0, check_started.stderr)

        commit_all(repo, "direct checkpoint")
        check_committed = run(repo, "check-direct", "--repo", str(repo))
        require(check_committed.returncode == 0, f"a commit invalidated the direct receipt: {check_committed.stderr}")

        original_notes = (repo / "notes.txt").read_text(encoding="utf-8")
        (repo / "notes.txt").write_text("edited notes\n", encoding="utf-8")
        check_edited = run(repo, "check-direct", "--repo", str(repo))
        require(
            check_edited.returncode != 0 and "local direct research source changed" in check_edited.stderr,
            f"editing the local direct research source did not invalidate the receipt: {check_edited.stderr}",
        )
        (repo / "notes.txt").write_text(original_notes, encoding="utf-8")

        (repo / "extra.txt").write_text("more notes\n", encoding="utf-8")
        widened = run(
            repo,
            "start-direct",
            "--repo",
            str(repo),
            "--intended-path",
            "notes.txt",
            "--intended-path",
            "extra.txt",
            "--scope",
            "local",
            "--question",
            "Where do notes live?",
            "--decision",
            "Use notes.txt and extra.txt.",
            "--source",
            "notes.txt",
            "--source",
            "extra.txt",
            "--verified",
            "Both files exist.",
            "--fresh-until",
            "2099-12-31",
            "--unknown",
            "none",
        )
        require(widened.returncode == 0, widened.stderr)
        widened_value = json.loads(direct_path.read_text(encoding="utf-8"))
        require(
            {entry["path"] for entry in widened_value["intended_paths"]} == {"notes.txt", "extra.txt"},
            "re-running start-direct did not replace the receipt with the wider scope",
        )
        require(
            widened_value["write_nonce"] != direct_value["write_nonce"],
            "re-running start-direct reused the write nonce",
        )

        nonce = widened_value["write_nonce"]
        first_consume = run(repo, "consume-direct", "--repo", str(repo), "--write-nonce", nonce)
        require(first_consume.returncode == 0, "direct receipt write nonce failed to consume once")
        second_consume = run(repo, "consume-direct", "--repo", str(repo), "--write-nonce", nonce)
        require(second_consume.returncode != 0, "direct receipt write nonce was consumed a second time")

        approval_repo, approval_plan, token = approval_fixture(root)
        approve = [
            sys.executable,
            str(PLAN_STATE),
            "approve",
            "--repo",
            str(approval_repo),
            "--plan",
            str(approval_plan),
            "--expect-token",
            token,
            "--approval-reply",
            AUTONOMOUS_DIRECTIVE,
            "--allowed-action",
            "parallel-subagents",
        ]
        missing_research = subprocess.run(approve, text=True, capture_output=True, check=False)
        require(missing_research.returncode != 0, "configured approval skipped research")
        recorded = record_approval_research(approval_repo, approval_plan)
        require(recorded.returncode == 0, recorded.stderr)
        approved = subprocess.run(approve, text=True, capture_output=True, check=False)
        require(approved.returncode == 0, approved.stderr)
        integrated = json.loads((approval_plan.parent / "receipts" / "authorization.json").read_text())
        require(integrated["mode"] == "autonomous", "plan approval lost the explicit autonomous directive")
        require("parallel-subagents" in integrated["allowed"], "plan approval lost the requested action")

        approved_fp = brief_fp(approval_plan)
        validated = run_plan(approval_repo, "validate", "--repo", str(approval_repo), "--plan", str(approval_plan))
        require(validated.returncode == 0, validated.stderr)

        commit_all(approval_repo, "approval fixture baseline")
        (approval_repo / "README.md").write_text("# Approval fixture\n", encoding="utf-8")
        commit_all(approval_repo, "add readme")

        (approval_repo / "README.md").write_text("# Approval fixture\n\nUpdated.\n", encoding="utf-8")
        checked_edit = run(
            approval_repo,
            "check",
            "--repo",
            str(approval_repo),
            "--plan",
            str(approval_plan),
            "--fingerprint",
            approved_fp,
        )
        require(checked_edit.returncode == 0, f"an edit to a tracked file broke check: {checked_edit.stderr}")
        validated_edit = run_plan(approval_repo, "validate", "--repo", str(approval_repo), "--plan", str(approval_plan))
        require(validated_edit.returncode == 0, f"an edit to a tracked file broke validate: {validated_edit.stderr}")

        commit_all(approval_repo, "edit readme")
        checked_commit = run(
            approval_repo,
            "check",
            "--repo",
            str(approval_repo),
            "--plan",
            str(approval_plan),
            "--fingerprint",
            approved_fp,
        )
        require(checked_commit.returncode == 0, f"a commit broke check: {checked_commit.stderr}")
        validated_commit = run_plan(
            approval_repo, "validate", "--repo", str(approval_repo), "--plan", str(approval_plan)
        )
        require(validated_commit.returncode == 0, f"a commit broke validate: {validated_commit.stderr}")

    print("execution-evidence regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

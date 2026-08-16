#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"))
from git_env import git_env


OWNER = Path(__file__).with_name("execution_evidence.py")
PLAN_STATE = Path(__file__).with_name("plan_state.py")
FINGERPRINT = "sha256:" + "a" * 64
REQUEST_DIGEST = "sha256:" + "d" * 64
SESSION_ID = "session-one"
AUTONOMOUS_DIRECTIVE = "YES — use Hard Eng autonomous mode for this task."


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OWNER), *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


def run_current(
    repo: Path, command: str, *args: str, session_id: str = SESSION_ID,
    request_digest: str = REQUEST_DIGEST,
) -> subprocess.CompletedProcess[str]:
    return run(
        repo,
        command,
        "--session-id", session_id,
        "--request-digest", request_digest,
        *args,
    )


def challenge_response(result: subprocess.CompletedProcess[str]) -> str:
    require(result.returncode == 0, result.stderr)
    matches = [line.removeprefix("response=") for line in result.stdout.splitlines()
               if line.startswith("response=")]
    require(len(matches) == 1, f"challenge response missing: {result.stdout}")
    return matches[0]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"execution-evidence regression: FAIL: {message}")


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
        "<!-- /hard-eng-state -->\n",
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
        json.dumps({"schema_version": 1, "enforcement": {"schema_version": 1}}),
        encoding="utf-8",
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-evidence-") as temporary:
        root = Path(temporary).resolve()
        repo, plan = fixture(root)
        relative = str(plan.relative_to(repo))

        missing = run(repo, "check", "--repo", str(repo), "--plan", relative)
        require(missing.returncode != 0, "missing evidence passed")

        bad_external = run(
            repo,
            "record-research",
            "--repo", str(repo),
            "--plan", relative,
            "--scope", "external",
            "--question", "What is current?",
            "--decision", "Use the current contract.",
            "--source", "AGENTS.md",
            "--source-version", "retrieved-2026-08-14",
            "--verified", "The rule exists.",
            "--fresh-until", "2099-12-31",
            "--unknown", "none",
        )
        require(bad_external.returncode != 0, "external research accepted no HTTPS source")

        recorded = run(
            repo,
            "record-research",
            "--repo", str(repo),
            "--plan", relative,
            "--scope", "local",
            "--question", "Which local owner applies?",
            "--decision", "Use AGENTS.md.",
            "--source", "AGENTS.md",
            "--verified", "AGENTS.md owns the rule.",
            "--fresh-until", "2099-12-31",
            "--unknown", "none",
        )
        require(recorded.returncode == 0, recorded.stderr)

        (repo / "AGENTS.md").write_text("# Changed rules\n", encoding="utf-8")
        stale = run_current(
            repo, "challenge-ready", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--allowed-action", "approved-build",
        )
        require(
            stale.returncode != 0 and "source changed" in stale.stderr,
            "changed local research source passed",
        )
        recorded = run(
            repo,
            "record-research", "--repo", str(repo), "--plan", relative,
            "--scope", "local", "--question", "Which local owner applies?",
            "--decision", "Use AGENTS.md.", "--source", "AGENTS.md",
            "--verified", "AGENTS.md owns the rule.",
            "--fresh-until", "2099-12-31", "--unknown", "none",
        )
        require(recorded.returncode == 0, recorded.stderr)

        challenge = run_current(
            repo, "challenge-ready", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--allowed-action", "approved-build",
        )
        exact_reply = challenge_response(challenge)
        rejected = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", "looks fine",
        )
        require(rejected.returncode != 0, "non-affirmative reply authorized execution")

        for reply in (
            "do not proceed",
            "I don't approve",
            "not approved",
            "never go ahead",
            "yes, but do not build it",
            "yes",
        ):
            ambiguous = run_current(
                repo, "authorize",
                "--repo", str(repo),
                "--plan", relative,
                "--fingerprint", FINGERPRINT,
                "--approval-reply", reply,
            )
            require(
                ambiguous.returncode != 0,
                f"ambiguous or negated reply authorized execution: {reply!r}",
            )

        negated = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", "approved, do not use autonomous mode",
        )
        require(negated.returncode != 0, "negated autonomy authorized execution")

        informational = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", "what is autonomous mode?",
        )
        require(informational.returncode != 0, "autonomy question enabled autonomous mode")

        standard = run_current(
            repo, "authorize",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", exact_reply,
        )
        require(standard.returncode == 0, standard.stderr)
        auth_path = plan.parent / "receipts" / "authorization.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(auth["mode"] == "standard", "exact challenge enabled wrong mode")
        require(auth["allowed"] == ["approved-build"], "challenge enabled extra actions")
        duplicate = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", exact_reply,
        )
        require(duplicate.returncode != 0, "consumed challenge was reused")
        auth["allowed"] = ["approved-build", "named-deployment"]
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        overbroad = run_current(
            repo, "check", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(overbroad.returncode != 0, "overbroad standard authorization passed")

        agents_challenge = run_current(
            repo, "challenge-ready", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--allowed-action", "approved-build",
            "--allowed-action", "parallel-subagents",
        )
        with_agents = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", challenge_response(agents_challenge),
        )
        require(with_agents.returncode == 0, with_agents.stderr)
        agent_auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require("parallel-subagents" in agent_auth["allowed"], "explicit subagents were not recorded")

        autonomous = run_current(
            repo, "authorize",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", AUTONOMOUS_DIRECTIVE,
            "--allowed-action", "build-and-verify",
            "--allowed-action", "parallel-subagents",
        )
        require(autonomous.returncode == 0, autonomous.stderr)
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(auth["mode"] == "autonomous", "explicit autonomy was not recorded")
        require(
            auth["stop_before"] == [
                "account-or-permission-change",
                "data-deletion-or-destructive-schema",
                "force-or-history-rewrite",
                "material-payment-or-spend",
                "protected-live-write-retry",
                "secret-exposure",
            ],
            "autonomous stop boundary drifted",
        )

        checked = run_current(
            repo, "check",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(checked.returncode == 0, checked.stderr)

        wrong_session = run_current(
            repo, "check", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, session_id="session-two",
        )
        require(wrong_session.returncode != 0, "previous session authorization passed")
        wrong_request = run_current(
            repo, "check", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, request_digest="sha256:" + "e" * 64,
        )
        require(wrong_request.returncode != 0, "previous request authorization passed")
        auth["plan_fingerprint"] = "sha256:" + "b" * 64
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        tampered = run_current(
            repo, "check",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(tampered.returncode != 0, "tampered authorization passed")

        autonomous = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", AUTONOMOUS_DIRECTIVE,
            "--allowed-action", "build-and-verify",
        )
        require(autonomous.returncode == 0, autonomous.stderr)
        (repo / "unrelated.py").write_text("changed = True\n", encoding="utf-8")
        changed_tree = run_current(
            repo, "check", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(changed_tree.returncode != 0, "changed repository tree passed")
        (repo / "unrelated.py").unlink()

        autonomous = run_current(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", AUTONOMOUS_DIRECTIVE,
            "--allowed-action", "build-and-verify",
        )
        require(autonomous.returncode == 0, autonomous.stderr)
        plan.write_text(
            plan.read_text(encoding="utf-8")
            .replace("lifecycle_status = planning", "lifecycle_status = building")
            .replace("approval_status = pending", "approval_status = approved")
            .replace("approval_fingerprint = none", f"approval_fingerprint = {FINGERPRINT}"),
            encoding="utf-8",
        )
        protected = [
            "--repo", str(repo), "--plan", relative,
            "--kind", "external-live-write-or-delivery",
            "--target", "events row", "--effect", "create one events row",
            "--tool-name", "mcp__appwrite__createRow",
            "--tool-input-json", '{"table":"events","value":"one"}',
        ]
        protected_consume = [
            "--repo", str(repo), "--plan", relative,
            "--kind", "external-live-write-or-delivery",
            "--tool-name", "mcp__appwrite__createRow",
            "--tool-input-json", '{"table":"events","value":"one"}',
        ]
        action_challenge = run_current(repo, "challenge-protected", *protected)
        action_reply = challenge_response(action_challenge)
        malformed = run_current(
            repo, "authorize-protected", *protected,
            "--approval-reply", action_reply + " now",
        )
        require(malformed.returncode != 0, "malformed protected response passed")
        changed_target = list(protected)
        changed_target[changed_target.index("events row")] = "audit row"
        wrong_target = run_current(
            repo, "authorize-protected", *changed_target, "--approval-reply", action_reply,
        )
        require(wrong_target.returncode != 0, "changed protected target passed")
        changed_input = list(protected)
        changed_input[-1] = '{"table":"events","value":"two"}'
        wrong_input = run_current(
            repo, "authorize-protected", *changed_input, "--approval-reply", action_reply,
        )
        require(wrong_input.returncode != 0, "changed protected tool input passed")

        expired_challenge = plan.parent / "receipts" / "protected-challenge.json"
        expired = json.loads(expired_challenge.read_text(encoding="utf-8"))
        expired["expires_at_epoch"] = 0
        expired_challenge.write_text(json.dumps(expired) + "\n", encoding="utf-8")
        expired_result = run_current(
            repo, "authorize-protected", *protected, "--approval-reply", action_reply,
        )
        require(expired_result.returncode != 0, "expired protected challenge passed")

        action_challenge = run_current(repo, "challenge-protected", *protected)
        action_reply = challenge_response(action_challenge)
        action_authorized = run_current(
            repo, "authorize-protected", *protected, "--approval-reply", action_reply,
        )
        require(action_authorized.returncode == 0, action_authorized.stderr)
        (repo / "action-state.py").write_text("changed = True\n", encoding="utf-8")
        stale_action = run_current(repo, "consume-protected", *protected_consume)
        require(stale_action.returncode != 0, "changed-state protected action passed")
        (repo / "action-state.py").unlink()
        consumed_action = run_current(repo, "consume-protected", *protected_consume)
        require(consumed_action.returncode == 0, consumed_action.stderr)
        duplicate_action = run_current(repo, "consume-protected", *protected_consume)
        require(duplicate_action.returncode != 0, "protected action was reused")

        action_challenge = run_current(repo, "challenge-protected", *protected)
        action_reply = challenge_response(action_challenge)
        action_authorized = run_current(
            repo, "authorize-protected", *protected, "--approval-reply", action_reply,
        )
        require(action_authorized.returncode == 0, action_authorized.stderr)
        protected_command = [
            sys.executable, str(OWNER), "consume-protected",
            "--session-id", SESSION_ID, "--request-digest", REQUEST_DIGEST,
            *protected_consume,
        ]
        protected_consumers = [subprocess.Popen(protected_command, cwd=repo) for _ in range(2)]
        require(
            sorted(process.wait() for process in protected_consumers) == [0, 4],
            "concurrent protected consumption did not produce exactly one winner",
        )

        race_challenge = run_current(
            repo, "challenge-ready", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--allowed-action", "approved-build",
        )
        race_reply = challenge_response(race_challenge)
        command = [
            sys.executable, str(OWNER), "authorize", "--session-id", SESSION_ID,
            "--request-digest", REQUEST_DIGEST, "--repo", str(repo),
            "--plan", relative, "--fingerprint", FINGERPRINT,
            "--approval-reply", race_reply,
        ]
        consumers = [subprocess.Popen(command, cwd=repo) for _ in range(2)]
        require(
            sorted(process.wait() for process in consumers) == [0, 4],
            "concurrent challenge consumption did not produce exactly one winner",
        )

        approval_repo, approval_plan, token = approval_fixture(root)
        approve = [
            sys.executable, str(PLAN_STATE), "approve", "--repo", str(approval_repo),
            "--plan", str(approval_plan), "--expect-token", token,
            "--approval-reply", AUTONOMOUS_DIRECTIVE,
            "--session-id", SESSION_ID,
            "--request-digest", REQUEST_DIGEST,
            "--allowed-action", "build-and-verify",
        ]
        missing_research = subprocess.run(approve, text=True, capture_output=True, check=False)
        require(missing_research.returncode != 0, "configured approval skipped research")
        recorded = run(
            approval_repo,
            "record-research", "--repo", str(approval_repo), "--plan", str(approval_plan),
            "--scope", "local", "--question", "Which gate applies?",
            "--decision", "Use hard-eng.gates.json.", "--source", "hard-eng.gates.json",
            "--verified", "The manifest enables enforcement.",
            "--fresh-until", "2099-12-31", "--unknown", "none",
        )
        require(recorded.returncode == 0, recorded.stderr)
        approved = subprocess.run(approve, text=True, capture_output=True, check=False)
        require(approved.returncode == 0, approved.stderr)
        integrated = json.loads(
            (approval_plan.parent / "receipts" / "authorization.json").read_text()
        )
        require(integrated["mode"] == "autonomous", "plan approval lost explicit autonomy")

    print("execution-evidence regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

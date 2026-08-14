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


def run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(OWNER), *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )


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
        stale = run(
            repo, "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", "approved",
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

        rejected = run(
            repo,
            "authorize",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", "looks fine",
        )
        require(rejected.returncode != 0, "non-affirmative reply authorized execution")

        negated = run(
            repo,
            "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", "approved, do not use autonomous mode",
        )
        require(negated.returncode == 0, negated.stderr)
        negated_auth = json.loads(
            (plan.parent / "receipts" / "authorization.json").read_text()
        )
        require(negated_auth["mode"] == "standard", "negated autonomy enabled autonomous mode")

        informational = run(
            repo,
            "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", "what is autonomous mode?",
        )
        require(informational.returncode != 0, "autonomy question enabled autonomous mode")

        standard = run(
            repo,
            "authorize",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", "approved",
        )
        require(standard.returncode == 0, standard.stderr)
        auth_path = plan.parent / "receipts" / "authorization.json"
        auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require(auth["mode"] == "standard", "plain approval enabled autonomy")
        require(auth["allowed"] == ["approved-build"], "plain approval enabled extra actions")
        auth["allowed"] = ["approved-build", "named-deployment"]
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        overbroad = run(
            repo, "check", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(overbroad.returncode != 0, "overbroad standard authorization passed")

        with_agents = run(
            repo,
            "authorize", "--repo", str(repo), "--plan", relative,
            "--fingerprint", FINGERPRINT, "--approval-reply", "approved, use subagents",
        )
        require(with_agents.returncode == 0, with_agents.stderr)
        agent_auth = json.loads(auth_path.read_text(encoding="utf-8"))
        require("parallel-subagents" in agent_auth["allowed"], "explicit subagents were not recorded")

        autonomous = run(
            repo,
            "authorize",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
            "--approval-reply", "use autonomous mode for this feature",
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

        checked = run(
            repo,
            "check",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(checked.returncode == 0, checked.stderr)

        auth["fingerprint"] = "sha256:" + "b" * 64
        auth_path.write_text(json.dumps(auth) + "\n", encoding="utf-8")
        tampered = run(
            repo,
            "check",
            "--repo", str(repo),
            "--plan", relative,
            "--fingerprint", FINGERPRINT,
        )
        require(tampered.returncode != 0, "tampered authorization passed")

        approval_repo, approval_plan, token = approval_fixture(root)
        approve = [
            sys.executable, str(PLAN_STATE), "approve", "--repo", str(approval_repo),
            "--plan", str(approval_plan), "--expect-token", token,
            "--approval-reply", "approved autonomous",
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

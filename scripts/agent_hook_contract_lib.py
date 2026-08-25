"""Shared fixtures and helpers for the agent hook contract checks."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
sys.path.insert(0, str(ROOT / "skills/he/scripts"))
from git_env import git_env
from plan_state import frozen_fingerprint, parse_sections

HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
EVIDENCE = ROOT / "skills" / "he" / "scripts" / "execution_evidence.py"
FAILURES: list[str] = []
REQUEST_DIGEST = "sha256:" + "d" * 64
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
BRIEF_FINGERPRINT = frozen_fingerprint(parse_sections(BRIEF_SECTIONS))


def protected_digest(tool_name: str, tool_input: object) -> str:
    value = json.dumps(
        {"tool_input": tool_input, "tool_name": tool_name.casefold()}, sort_keys=True, separators=(",", ":")
    )
    return "sha256:" + hashlib.sha256(value.encode("ascii")).hexdigest()


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def agent_fixture(name: str) -> dict:
    path = ROOT / "scripts/test_fixtures/agent-hooks" / name
    return json.loads(path.read_text(encoding="utf-8"))


def run_hook(
    runtime: str, event: str, payload: object, *, env: dict[str, str] | None = None
) -> tuple[dict | None, str]:
    if isinstance(payload, dict):
        payload = dict(payload)
        payload.setdefault("session_id", "contract")
        payload.setdefault("request_digest", REQUEST_DIGEST)
    result = subprocess.run(
        ["bash", str(HOOK), runtime, event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
        check=False,
    )
    check("hook exits cleanly", result.returncode == 0, result.stderr.strip())
    output = result.stdout.strip()
    try:
        return (json.loads(output) if output else None), result.stderr.strip()
    except ValueError as error:
        check("hook returns JSON or silence", False, f"{output}: {error}")
        return None, result.stderr.strip()


def denial(response: dict | None, runtime: str) -> str | None:
    if response is None:
        return None
    body = response if runtime == "copilot" else response.get("hookSpecificOutput", {})
    if body.get("permissionDecision") != "deny":
        return None
    reason = body.get("permissionDecisionReason")
    return reason if isinstance(reason, str) else ""


def advice_context(response: dict | None) -> str | None:
    body = (response or {}).get("hookSpecificOutput", {})
    context = body.get("additionalContext")
    if not isinstance(context, str) or "hard-eng.gates.json" not in context:
        return None
    return None if "permissionDecision" in body else context


def manifest(repo: Path) -> None:
    (repo / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enforcement": {
                    "schema_version": 1,
                    "coverage": {
                        "fixture-block": ["block", "hard-eng.gates.json", "hard-eng.gates.json"],
                        "fixture-check": ["checkpoint check", "hard-eng.gates.json", "hard-eng.gates.json"],
                    },
                },
                "families": {"targeted": ["python3", "check.py"]},
                "phases": {"commit": ["targeted"], "push": ["targeted"], "ci": ["targeted"]},
            }
        ),
        encoding="utf-8",
    )


def write_evidence(repo: Path, folder: Path, slug: str) -> None:
    receipts = folder / "receipts"
    receipts.mkdir(exist_ok=True)
    resolved = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "HEAD"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=git_env(),
    )
    repository_head = resolved.stdout.strip() if resolved.returncode == 0 else "unborn"
    (receipts / "research.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "plan_id": f"{slug}-12345678",
                "scope": "local",
                "sources": ["hard-eng.gates.json"],
                "verified": ["The local gate manifest exists."],
                "unknown": [],
                "question": "Which local gate applies?",
                "decision": "Use hard-eng.gates.json.",
                "checked_at": "2026-08-14",
                "fresh_until": "2099-12-31",
                "repository_head": repository_head,
                "source_versions": [
                    "sha256:" + hashlib.sha256((repo / "hard-eng.gates.json").read_bytes()).hexdigest()
                ],
            }
        ),
        encoding="utf-8",
    )
    challenge = subprocess.run(
        [
            sys.executable,
            str(EVIDENCE),
            "challenge-ready",
            "--repo",
            str(repo),
            "--plan",
            str(folder / "PLAN.md"),
            "--fingerprint",
            BRIEF_FINGERPRINT,
            "--session-id",
            "contract",
            "--request-digest",
            REQUEST_DIGEST,
            "--allowed-action",
            "approved-build",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    replies = [line.removeprefix("response=") for line in challenge.stdout.splitlines() if line.startswith("response=")]
    if challenge.returncode != 0 or len(replies) != 1:
        raise SystemExit(challenge.stderr or "missing Ready-to-build challenge response")
    authorized = subprocess.run(
        [
            sys.executable,
            str(EVIDENCE),
            "authorize",
            "--repo",
            str(repo),
            "--plan",
            str(folder / "PLAN.md"),
            "--fingerprint",
            BRIEF_FINGERPRINT,
            "--session-id",
            "contract",
            "--request-digest",
            REQUEST_DIGEST,
            "--approval-reply",
            replies[0],
            "--allowed-action",
            "approved-build",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if authorized.returncode != 0:
        raise SystemExit(authorized.stderr)


def authorize_protected(
    repo: Path, active: Path, payload: dict, kind: str, target: str
) -> subprocess.CompletedProcess[str]:
    session_id = str(payload.get("session_id", "contract"))
    request_digest = str(payload.get("request_digest", REQUEST_DIGEST))
    effect = f"{kind} on {target}"
    base = [
        "--repo",
        str(repo),
        "--plan",
        str(active),
        "--kind",
        kind,
        "--target",
        target,
        "--effect",
        effect,
        "--session-id",
        session_id,
        "--request-digest",
        request_digest,
        "--tool-name",
        str(payload["tool_name"]),
        "--action-digest",
        protected_digest(str(payload["tool_name"]), payload["tool_input"]),
    ]
    challenge = subprocess.run(
        [sys.executable, str(EVIDENCE), "challenge-protected", *base], capture_output=True, text=True, check=False
    )
    if challenge.returncode != 0:
        return challenge
    replies = [line.removeprefix("response=") for line in challenge.stdout.splitlines() if line.startswith("response=")]
    if len(replies) != 1:
        return subprocess.CompletedProcess([], 4, "", "missing protected challenge response")
    return subprocess.run(
        [sys.executable, str(EVIDENCE), "authorize-protected", *base, "--approval-reply", replies[0]],
        capture_output=True,
        text=True,
        check=False,
    )


def start_direct(
    repo: Path,
    session_id: str,
    intended_path: str,
    *additional_paths: str,
    allow_subagents: bool = False,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(EVIDENCE),
        "start-direct",
        "--repo",
        str(repo),
        "--session-id",
        session_id,
        "--intended-path",
        intended_path,
        "--request-digest",
        "sha256:" + "d" * 64,
        "--scope",
        "local",
        "--question",
        "Which route and local rule apply?",
        "--decision",
        "Use the direct route for the intended path.",
        "--source",
        "hard-eng.gates.json",
        "--verified",
        "The local gate is configured.",
        "--unknown",
        "none",
        "--fresh-until",
        "2099-12-31",
    ]
    for path in additional_paths:
        command += ["--intended-path", path]
    if allow_subagents:
        command.append("--allow-subagents")
    return subprocess.run(command, capture_output=True, text=True, check=False, env=env)


def plan(repo: Path, slug: str, state: str) -> Path:
    folder = repo / "features" / slug
    folder.mkdir(parents=True)
    path = folder / "PLAN.md"
    path.write_text(
        "\n".join(
            (
                "# Feature Brief",
                "<!-- hard-eng-state:v1 -->",
                f"- plan_id = {slug}-12345678",
                f"- lifecycle_status = {state}",
                f"- approval_status = {'pending' if state == 'planning' else 'approved'}",
                f"- approval_fingerprint = {'none' if state == 'planning' else BRIEF_FINGERPRINT}",
                "<!-- /hard-eng-state -->",
                BRIEF_SECTIONS,
            )
        ),
        encoding="utf-8",
    )
    if state != "planning":
        write_evidence(repo, folder, slug)
    return path


def edit_payload(repo: Path, path: Path | None = None, args: object | None = None) -> dict:
    return {
        "session_id": "contract",
        "cwd": str(repo),
        "tool_name": "Edit",
        "tool_input": args if args is not None else {"file_path": str(path or repo / "src.py")},
    }

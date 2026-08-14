#!/usr/bin/env python3
"""Behavior checks for the shared agent hook."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env

HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
EVIDENCE = ROOT / "skills" / "he" / "scripts" / "execution_evidence.py"
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run_hook(runtime: str, event: str, payload: object) -> tuple[dict | None, str]:
    result = subprocess.run(
        ["bash", str(HOOK), runtime, event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=5,
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


def manifest(repo: Path) -> None:
    (repo / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "enforcement": {
                    "schema_version": 1,
                    "coverage": {
                        "fixture-block": [
                            "block", "hard-eng.gates.json", "hard-eng.gates.json",
                        ],
                        "fixture-check": [
                            "checkpoint check", "hard-eng.gates.json", "hard-eng.gates.json",
                        ],
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
    (receipts / "research.json").write_text(
        json.dumps(
            {
                "schema_version": 1, "plan_id": f"{slug}-12345678", "scope": "local",
                "sources": ["hard-eng.gates.json"], "verified": ["The local gate manifest exists."],
                "unknown": [], "question": "Which local gate applies?",
                "decision": "Use hard-eng.gates.json.", "checked_at": "2026-08-14",
                "fresh_until": "2099-12-31", "repository_head": "fixture",
                "source_versions": [
                    "sha256:" + hashlib.sha256(
                        (repo / "hard-eng.gates.json").read_bytes()
                    ).hexdigest()
                ],
            }
        ),
        encoding="utf-8",
    )
    (receipts / "authorization.json").write_text(
        json.dumps(
            {
                "schema_version": 1, "plan_id": f"{slug}-12345678",
                "fingerprint": "sha256:" + "a" * 64, "mode": "standard",
                "allowed": ["approved-build"],
                "approval_digest": "sha256:" + "c" * 64,
                "stop_before": [
                    "account-or-permission-change", "data-deletion-or-destructive-schema",
                    "force-or-history-rewrite", "material-payment-or-spend",
                    "protected-live-write-retry", "secret-exposure",
                ],
            }
        ),
        encoding="utf-8",
    )


def authorize_protected(
    repo: Path, active: Path, payload: dict, kind: str, target: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable, str(EVIDENCE), "authorize-protected",
            "--repo", str(repo), "--plan", str(active), "--kind", kind,
            "--target", target, "--tool-name", str(payload["tool_name"]),
            "--tool-input-json", json.dumps(payload["tool_input"]),
            "--approval-reply", f"approved {target}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def start_direct(
    repo: Path, session_id: str, intended_path: str, allow_subagents: bool = False
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable, str(EVIDENCE), "start-direct", "--repo", str(repo),
        "--session-id", session_id, "--intended-path", intended_path,
        "--request-digest", "sha256:" + "d" * 64,
        "--scope", "local", "--question", "Which route and local rule apply?",
        "--decision", "Use the direct route for the intended path.",
        "--source", "hard-eng.gates.json", "--verified", "The local gate is configured.",
        "--unknown", "none", "--fresh-until", "2099-12-31",
    ]
    if allow_subagents:
        command.append("--allow-subagents")
    return subprocess.run(command, capture_output=True, text=True, check=False)


def plan(repo: Path, slug: str, state: str) -> Path:
    folder = repo / "features" / slug
    folder.mkdir(parents=True)
    path = folder / "PLAN.md"
    path.write_text(
        "\n".join(
            (
                "# Feature Brief", "<!-- hard-eng-state:v1 -->", f"- plan_id = {slug}-12345678",
                f"- lifecycle_status = {state}",
                f"- approval_status = {'pending' if state == 'planning' else 'approved'}",
                f"- approval_fingerprint = {'none' if state == 'planning' else 'sha256:' + 'a' * 64}",
                "<!-- /hard-eng-state -->", "",
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


def check_unconfigured(root: Path) -> None:
    repo = root / "plain"
    repo.mkdir()
    (repo / ".git").mkdir()
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo))
    check("unconfigured repository is untouched", response is None, repr(response))


def check_direct_route(root: Path) -> None:
    repo = root / "direct"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    source = repo / "src.py"
    source.write_text("value = 1\n", encoding="utf-8")
    payload = edit_payload(repo, source)
    payload["session_id"] = "direct-one"
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct write without route receipt blocks", bool(denial(response, "codex")), repr(response))

    started = start_direct(repo, "direct-one", "src.py")
    check("direct route receipt records", started.returncode == 0, started.stderr)
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct intended write is allowed", response is None, repr(response))
    manifest_before = (repo / "hard-eng.gates.json").read_text(encoding="utf-8")
    (repo / "hard-eng.gates.json").write_text(
        manifest_before.replace('"schema_version": 1', '"schema_version": 1 '),
        encoding="utf-8",
    )
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct changed local research source blocks", bool(denial(response, "codex")), repr(response))
    manifest(repo)
    started = start_direct(repo, "direct-one", "src.py")
    check("direct route refresh records", started.returncode == 0, started.stderr)
    wrong_session = dict(payload, session_id="direct-two")
    response, _ = run_hook("codex", "pretooluse", wrong_session)
    check("direct receipt is session-bound", bool(denial(response, "codex")), repr(response))
    outside = edit_payload(repo, repo / "other.py")
    outside["session_id"] = "direct-one"
    response, _ = run_hook("codex", "pretooluse", outside)
    check("direct write outside intended path blocks", bool(denial(response, "codex")), repr(response))

    agent = {
        "cwd": str(repo), "session_id": "direct-one", "tool_name": "Agent",
        "tool_input": {"prompt": "inspect"},
    }
    response, _ = run_hook("claude", "pretooluse", agent)
    check("direct subagent without explicit flag blocks", bool(denial(response, "claude")), repr(response))
    started = start_direct(repo, "direct-one", "src.py", allow_subagents=True)
    check("direct subagent authorization records", started.returncode == 0, started.stderr)
    response, _ = run_hook("claude", "pretooluse", agent)
    check("direct explicitly authorized subagent is allowed", response is None, repr(response))

    live = {
        "cwd": str(repo), "session_id": "direct-one",
        "tool_name": "mcp__appwrite__createRow", "tool_input": {"table": "events"},
    }
    response, _ = run_hook("codex", "pretooluse", live)
    check("direct live write requires Feature Loop", "Feature Loop" in (denial(response, "codex") or ""))

    checkpoint = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    check("direct intended checkpoint passes", checkpoint.returncode == 0, checkpoint.stderr)
    (repo / "other.py").write_text("value = 2\n", encoding="utf-8")
    checkpoint = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."],
        cwd=repo, capture_output=True, text=True, check=False,
    )
    check("direct unknown outside write fails checkpoint", checkpoint.returncode != 0, checkpoint.stderr)


def check_lifecycle(root: Path) -> None:
    repo = root / "lifecycle"
    repo.mkdir()
    (repo / ".git").mkdir()
    manifest(repo)
    active = plan(repo, "one", "planning")
    source = repo / "src.py"
    source.write_text("value = 1\n", encoding="utf-8")

    for runtime in ("codex", "claude", "copilot"):
        response, _ = run_hook(runtime, "pretooluse", edit_payload(repo, source))
        reason = denial(response, runtime)
        check(f"planning blocks source write on {runtime}", bool(reason), repr(response))
        check(f"planning reason is useful on {runtime}", bool(reason) and "building" in reason, repr(reason))

    active.write_text(
        active.read_text()
        .replace("planning", "building")
        .replace("approval_status = pending", "approval_status = approved")
        .replace("approval_fingerprint = none", "approval_fingerprint = sha256:" + "a" * 64),
        encoding="utf-8",
    )
    write_evidence(repo, active.parent, "one")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("building allows source write", response is None, repr(response))

    agent_payload = {
        "cwd": str(repo), "tool_name": "Agent", "tool_input": {"prompt": "inspect"},
    }
    response, _ = run_hook("claude", "pretooluse", agent_payload)
    check("subagent without explicit authorization blocks", bool(denial(response, "claude")))
    codex_agent_payload = {
        "cwd": str(repo),
        "tool_name": "collaboration.spawn_agent",
        "tool_input": {"message": "inspect"},
    }
    response, _ = run_hook("codex", "pretooluse", codex_agent_payload)
    check("namespaced Codex subagent without authorization blocks", bool(denial(response, "codex")))
    auth_path = active.parent / "receipts" / "authorization.json"
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    auth["allowed"] = ["approved-build", "parallel-subagents"]
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("claude", "pretooluse", agent_payload)
    check("explicitly authorized subagent is allowed", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", codex_agent_payload)
    check("explicitly authorized namespaced subagent is allowed", response is None, repr(response))

    auth["approval_digest"] = "bad"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("bad authorization digest blocks", bool(denial(response, "codex")), repr(response))
    auth["approval_digest"] = "sha256:" + "c" * 64
    auth_path.write_text(json.dumps(auth), encoding="utf-8")

    external_delete = {
        "cwd": str(repo),
        "tool_name": "mcp__appwrite__deleteRows",
        "tool_input": {"table": "users"},
    }
    response, _ = run_hook("codex", "pretooluse", external_delete)
    check("external destructive tool blocks", "destructive" in (denial(response, "codex") or ""))
    approved_delete = authorize_protected(
        repo, active, external_delete, "data-deletion-or-destructive-schema", "users table",
    )
    check("exact external delete approval records", approved_delete.returncode == 0, approved_delete.stderr)
    changed_delete = dict(external_delete, tool_input={"table": "admins"})
    response, _ = run_hook("codex", "pretooluse", changed_delete)
    check("external delete approval rejects changed input", bool(denial(response, "codex")), repr(response))
    response, _ = run_hook("codex", "pretooluse", external_delete)
    check("exact approved external delete is allowed once", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", external_delete)
    check("external delete approval is consumed", bool(denial(response, "codex")), repr(response))

    for label, payload in (
        ("external payment", {"cwd": str(repo), "tool_name": "mcp__stripe__createPayment", "tool_input": {"amount": 10}}),
        ("external account change", {"cwd": str(repo), "tool_name": "mcp__auth__updateUser", "tool_input": {"user": "one"}}),
        ("external secret send", {"cwd": str(repo), "tool_name": "mcp__vendor__sendRequest", "tool_input": {"headers": {"apiToken": "fixture"}}}),
    ):
        response, _ = run_hook("codex", "pretooluse", payload)
        check(f"{label} blocks", bool(denial(response, "codex")), repr(response))
    benign_external = {
        "cwd": str(repo), "tool_name": "mcp__vendor__get_status", "tool_input": {},
    }
    response, _ = run_hook("codex", "pretooluse", benign_external)
    check("benign external read is allowed", response is None, repr(response))

    create_row = {
        "cwd": str(repo), "tool_name": "mcp__appwrite__createRow",
        "tool_input": {"table": "events", "value": "one"},
    }
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("standard mode live write blocks", bool(denial(response, "codex")), repr(response))
    approved_create = authorize_protected(
        repo, active, create_row, "external-live-write-or-delivery", "events row",
    )
    check("exact standard live write approval records", approved_create.returncode == 0, approved_create.stderr)
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("exact approved standard live write is allowed once", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("standard live write approval is consumed", bool(denial(response, "codex")), repr(response))

    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    auth["mode"] = "autonomous"
    auth["allowed"] = [
        "additive-live-data-or-schema", "build-and-verify", "commit-push-pr-merge-ci",
        "named-deployment", "parallel-subagents", "planning-and-engineering-decisions",
    ]
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("autonomous additive live write is allowed", response is None, repr(response))
    autonomous_message = {
        "cwd": str(repo), "tool_name": "mcp__vendor__send_message",
        "tool_input": {"recipient": "one", "body": "hello"},
    }
    response, _ = run_hook("codex", "pretooluse", autonomous_message)
    check("autonomous unrelated live write still blocks", bool(denial(response, "codex")), repr(response))

    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, outside))
    check("repository policy ignores outside target", response is None, repr(response))

    extra = active.parent / "notes" / "detail.md"
    extra.parent.mkdir()
    extra.write_text("extra\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    reason = denial(response, "codex")
    check("extra Markdown blocks", bool(reason) and "detail.md" in reason, repr(reason))
    extra.unlink()

    second = plan(repo, "two", "build-ready")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    reason = denial(response, "codex")
    check("two active plans block", bool(reason) and "one" in reason and "two" in reason, repr(reason))
    second.write_text(second.read_text().replace("build-ready", "shipped"), encoding="utf-8")

    patch = f"*** Begin Patch\n*** Delete File: {active}\n*** End Patch\n"
    response, _ = run_hook(
        "codex",
        "pretooluse",
        {
            "cwd": str(repo),
            "tool_name": "apply_patch",
            "tool_input": {"patch": patch},
        },
    )
    reason = denial(response, "codex")
    check("active PLAN deletion blocks", bool(reason) and "PLAN.md" in reason, repr(reason))

    alias = repo / "plan-alias.md"
    alias.symlink_to(active)
    response, _ = run_hook(
        "codex",
        "pretooluse",
        {
            "cwd": str(repo),
            "tool_name": "apply_patch",
            "tool_input": {"patch": f"*** Begin Patch\n*** Delete File: {alias}\n*** End Patch\n"},
        },
    )
    reason = denial(response, "codex")
    check("active PLAN alias deletion blocks", bool(reason) and "PLAN.md" in reason, repr(reason))

    response, _ = run_hook(
        "codex",
        "pretooluse",
        {
            "cwd": str(repo),
            "tool_name": "exec_command",
            "tool_input": {"cmd": "mv features/one/PLAN.md features/one/OLD.md"},
        },
    )
    reason = denial(response, "codex")
    check("active PLAN shell rename blocks", bool(reason) and "PLAN.md" in reason, repr(reason))

    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, args="{"))
    reason = denial(response, "codex")
    check("malformed known edit blocks", bool(reason) and "target path" in reason, repr(reason))


def check_shell_safety(root: Path) -> None:
    repo = root / "shell"
    repo.mkdir()
    (repo / ".git").mkdir()
    manifest(repo)
    active = plan(repo, "one", "building")
    changed = repo / "generated.txt"
    changed.write_text("user bytes\n", encoding="utf-8")
    payload = {
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": "generator --output generated.txt"},
    }
    pre, _ = run_hook("codex", "pretooluse", payload)
    post, _ = run_hook("codex", "posttooluse", payload)
    check("unknown shell write is not pre-blocked", pre is None, repr(pre))
    check("unknown shell write is not post-blocked", post is None, repr(post))
    check("unknown shell bytes remain", changed.read_text() == "user bytes\n")

    bad_rg = dict(payload, tool_input={"command": "rg -rn thing src"})
    response, _ = run_hook("codex", "pretooluse", bad_rg)
    check("ripgrep typo blocks", "--replace" in (denial(response, "codex") or ""))

    exec_bad_rg = {
        "cwd": str(repo),
        "tool_name": "exec_command",
        "tool_input": {"cmd": "rg -rn thing src"},
    }
    response, _ = run_hook("codex", "pretooluse", exec_bad_rg)
    check("Codex exec command typo blocks", "--replace" in (denial(response, "codex") or ""))

    discard = dict(payload, tool_input={"command": "git restore src.py"})
    response, _ = run_hook("codex", "pretooluse", discard)
    check("Git discard blocks", "discard" in (denial(response, "codex") or "").lower())

    stash = dict(payload, tool_input={"command": "git stash push"})
    response, _ = run_hook("codex", "pretooluse", stash)
    check("recoverable stash is allowed", response is None, repr(response))

    unstage = dict(payload, tool_input={"command": "git restore --staged src.py"})
    response, _ = run_hook("codex", "pretooluse", unstage)
    check("unstage without worktree restore is allowed", response is None, repr(response))

    staged_worktree = dict(
        payload, tool_input={"command": "git restore --staged --worktree src.py"}
    )
    response, _ = run_hook("codex", "pretooluse", staged_worktree)
    check("staged worktree restore blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_file = dict(payload, tool_input={"command": "git checkout src/file.py"})
    response, _ = run_hook("codex", "pretooluse", checkout_file)
    check("checkout of a file blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_branch = dict(payload, tool_input={"command": "git checkout feature/name"})
    response, _ = run_hook("codex", "pretooluse", checkout_branch)
    check("checkout of a branch is allowed", response is None, repr(response))

    dry_clean = dict(payload, tool_input={"command": "git clean -nd"})
    response, _ = run_hook("codex", "pretooluse", dry_clean)
    check("dry-run clean is allowed", response is None, repr(response))

    forced = dict(payload, tool_input={"command": "git push --force origin main"})
    response, _ = run_hook("codex", "pretooluse", forced)
    check("forced push blocks", "remote history" in (denial(response, "codex") or ""))
    approved_force = authorize_protected(
        repo, active, forced, "force-or-history-rewrite", "origin main",
    )
    check("exact forced push approval records", approved_force.returncode == 0, approved_force.stderr)
    response, _ = run_hook("codex", "pretooluse", forced)
    check("exact approved forced push is allowed once", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", forced)
    check("forced push approval is consumed", bool(denial(response, "codex")), repr(response))

    amend = dict(payload, tool_input={"command": "git commit --amend --no-edit"})
    response, _ = run_hook("codex", "pretooluse", amend)
    check("Git amend blocks", "history rewrite" in (denial(response, "codex") or ""))
    rebase = dict(payload, tool_input={"command": "git rebase main"})
    response, _ = run_hook("codex", "pretooluse", rebase)
    check("Git rebase blocks", "history rewrite" in (denial(response, "codex") or ""))

    destructive_sql = dict(payload, tool_input={"command": "psql -c 'DROP TABLE users'"})
    response, _ = run_hook("codex", "pretooluse", destructive_sql)
    check("destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))


def check_hot_path_shape() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "scripts").glob("enforcement_*.pl"))
    )
    check("hot hook does not start subprocesses", "system(" not in source and "qx(" not in source)
    check("hot hook does not use codebase map", "codebase-memory" not in source)
    check("hot hook does not auto-undo", "system(" not in source and "qx(" not in source)
    check("hot hook does not run formatter", "format_lane" not in source)


def check_repository_checkpoint(root: Path) -> None:
    repo = root / "checkpoint"
    repo.mkdir()
    (repo / ".git").mkdir()
    manifest(repo)
    active = plan(repo, "one", "building")
    command = ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."]
    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    clean = run()
    check("clean checkpoint passes", clean.returncode == 0, clean.stderr)
    (active.parent / "notes.md").write_text("extra\n", encoding="utf-8")
    blocked = run()
    check(
        "checkpoint blocks extra Markdown",
        blocked.returncode != 0 and "notes.md" in blocked.stderr,
        blocked.stderr,
    )

    planning_repo = root / "planning-checkpoint"
    planning_repo.mkdir()
    subprocess.run(
        ["git", "init", "-q", str(planning_repo)], check=True, env=git_env()
    )
    manifest(planning_repo)
    plan(planning_repo, "one", "planning")
    (planning_repo / "late.py").write_text("value = 1\n", encoding="utf-8")
    planning = subprocess.run(command, cwd=planning_repo, capture_output=True, text=True, check=False)
    check(
        "checkpoint catches unknown planning source write",
        planning.returncode != 0 and "late.py" in planning.stderr,
        planning.stderr,
    )


def check_coverage() -> None:
    result = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "coverage"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    value = json.loads(result.stdout)
    weak = {name: mode for name, mode in value["rules"].items() if mode not in {"block", "checkpoint check"}}
    check("coverage has no guidance or unsupported rules", not weak, repr(weak))
    required = {
        "research-evidence", "autonomous-explicit-activation", "build-verify-loop",
        "direct-route-receipt",
    }
    check("coverage names research routes autonomy and build verify", required <= value["rules"].keys())


def check_broken_policy_fails_closed(root: Path) -> None:
    hooks = root / "broken/hooks"
    hooks.mkdir(parents=True)
    wrapper = hooks / "agent-hook.sh"
    wrapper.write_bytes(HOOK.read_bytes())
    wrapper.chmod(0o755)
    result = subprocess.run(
        ["bash", str(wrapper), "codex", "pretooluse"],
        input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "x.py"}}),
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        response = json.loads(result.stdout)
    except ValueError:
        response = None
    reason = denial(response, "codex")
    check("broken policy fails closed", bool(reason) and "setup.sh check" in reason, repr(result.stdout))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-hook-") as temporary:
        root = Path(temporary).resolve()
        check_unconfigured(root)
        check_direct_route(root)
        check_lifecycle(root)
        check_shell_safety(root)
        check_broken_policy_fails_closed(root)
        check_repository_checkpoint(root)
    check_hot_path_shape()
    check_coverage()
    if FAILURES:
        for failure in FAILURES:
            print(f"agent-hook-contract: FAIL: {failure}", file=sys.stderr)
        return 1
    print("agent-hook-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

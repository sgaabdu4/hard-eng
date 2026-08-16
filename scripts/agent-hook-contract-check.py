#!/usr/bin/env python3
"""Behavior checks for the shared agent hook."""

from __future__ import annotations

import json
import hashlib
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env

HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
EVIDENCE = ROOT / "skills" / "he" / "scripts" / "execution_evidence.py"
FAILURES: list[str] = []
REQUEST_DIGEST = "sha256:" + "d" * 64


def protected_digest(tool_name: str, tool_input: object) -> str:
    value = json.dumps(
        {"tool_input": tool_input, "tool_name": tool_name.casefold()},
        sort_keys=True,
        separators=(",", ":"),
    )
    return "sha256:" + hashlib.sha256(value.encode("ascii")).hexdigest()


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def agent_fixture(name: str) -> dict:
    path = ROOT / "scripts/test_fixtures/agent-hooks" / name
    return json.loads(path.read_text(encoding="utf-8"))


def run_hook(
    runtime: str,
    event: str,
    payload: object,
    *,
    env: dict[str, str] | None = None,
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
                "schema_version": 1, "plan_id": f"{slug}-12345678", "scope": "local",
                "sources": ["hard-eng.gates.json"], "verified": ["The local gate manifest exists."],
                "unknown": [], "question": "Which local gate applies?",
                "decision": "Use hard-eng.gates.json.", "checked_at": "2026-08-14",
                "fresh_until": "2099-12-31", "repository_head": repository_head,
                "source_versions": [
                    "sha256:" + hashlib.sha256(
                        (repo / "hard-eng.gates.json").read_bytes()
                    ).hexdigest()
                ],
            }
        ),
        encoding="utf-8",
    )
    challenge = subprocess.run(
        [
            sys.executable, str(EVIDENCE), "challenge-ready", "--repo", str(repo),
            "--plan", str(folder / "PLAN.md"), "--fingerprint", "sha256:" + "a" * 64,
            "--session-id", "contract", "--request-digest", REQUEST_DIGEST,
            "--allowed-action", "approved-build",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    replies = [line.removeprefix("response=") for line in challenge.stdout.splitlines()
               if line.startswith("response=")]
    if challenge.returncode != 0 or len(replies) != 1:
        raise SystemExit(challenge.stderr or "missing Ready-to-build challenge response")
    authorized = subprocess.run(
        [
            sys.executable, str(EVIDENCE), "authorize", "--repo", str(repo),
            "--plan", str(folder / "PLAN.md"), "--fingerprint", "sha256:" + "a" * 64,
            "--session-id", "contract", "--request-digest", REQUEST_DIGEST,
            "--approval-reply", replies[0], "--allowed-action", "approved-build",
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
        "--repo", str(repo), "--plan", str(active), "--kind", kind,
        "--target", target, "--effect", effect,
        "--session-id", session_id, "--request-digest", request_digest,
        "--tool-name", str(payload["tool_name"]),
        "--action-digest", protected_digest(
            str(payload["tool_name"]), payload["tool_input"]
        ),
    ]
    challenge = subprocess.run(
        [sys.executable, str(EVIDENCE), "challenge-protected", *base],
        capture_output=True, text=True, check=False,
    )
    if challenge.returncode != 0:
        return challenge
    replies = [line.removeprefix("response=") for line in challenge.stdout.splitlines()
               if line.startswith("response=")]
    if len(replies) != 1:
        return subprocess.CompletedProcess([], 4, "", "missing protected challenge response")
    return subprocess.run(
        [sys.executable, str(EVIDENCE), "authorize-protected", *base,
         "--approval-reply", replies[0]],
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
    for path in additional_paths:
        command += ["--intended-path", path]
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
    (repo / "src.py").write_text("value = 2\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct receipt rejects changed worktree artifact", bool(denial(response, "codex")), repr(response))
    started = start_direct(repo, "direct-one", "src.py")
    check("direct route refresh after worktree change records", started.returncode == 0, started.stderr)
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda _: run_hook("codex", "pretooluse", payload)[0], range(2)))
    check(
        "direct write nonce allows one concurrent consumer",
        sum(response is None for response in concurrent) == 1,
        repr(concurrent),
    )
    started = start_direct(repo, "direct-one", "src.py")
    check("direct route refresh after nonce consumption records", started.returncode == 0, started.stderr)
    missing_session = dict(payload, session_id="")
    response, _ = run_hook("codex", "pretooluse", missing_session)
    check("direct adapter rejects missing session", bool(denial(response, "codex")), repr(response))
    wrong_request = dict(payload, request_digest="sha256:" + "e" * 64)
    response, _ = run_hook("codex", "pretooluse", wrong_request)
    check("direct receipt is request-bound", bool(denial(response, "codex")), repr(response))
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
    learning = repo / ".agents/learning/proven-gap.json"
    learning.parent.mkdir(parents=True)
    learning.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "learning_id": "proven-gap",
                "status": "open",
                "trigger": "engineering-correction",
                "failure": "A verified repository process failed.",
                "evidence": ["user correction"],
                "root_cause": "The repository lacked durable prevention.",
                "occurrences": 1,
                "prevention": {"kind": "none"},
                "next_action": "Select deterministic prevention.",
                "helper": {"name": "he-learn", "selections": 1, "state": "selected"},
            }
        ),
        encoding="utf-8",
    )
    learning_agent = {
        **agent,
        "tool_input": {
            "prompt": "Use he-learn for .agents/learning/proven-gap.json"
        },
    }
    response, learning_stderr = run_hook("claude", "pretooluse", learning_agent)
    check(
        "recorded he-learn helper is allowed",
        response is None,
        f"{response!r} stderr={learning_stderr} record={learning.read_text(encoding='utf-8')}",
    )
    response, _ = run_hook("claude", "pretooluse", learning_agent)
    check("a second he-learn helper for one record blocks", bool(denial(response, "claude")), repr(response))
    missing_learning = {
        **agent,
        "tool_input": {
            "prompt": "Use he-learn for .agents/learning/missing-gap.json"
        },
    }
    response, _ = run_hook("claude", "pretooluse", missing_learning)
    check("he-learn helper without its record blocks", bool(denial(response, "claude")), repr(response))
    started = start_direct(
        repo,
        "direct-one",
        "src.py",
        "hard-eng.gates.json",
        ".agents/learning/proven-gap.json",
        allow_subagents=True,
    )
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
        env={
            **os.environ,
            "HARD_ENG_SESSION_ID": "direct-one",
            "HARD_ENG_REQUEST_DIGEST": REQUEST_DIGEST,
        },
    )
    check(
        "open learning blocks task closure",
        checkpoint.returncode != 0 and "learning state is invalid" in checkpoint.stderr,
        checkpoint.stderr,
    )
    record = json.loads(learning.read_text(encoding="utf-8"))
    record["status"] = "deferred"
    record["deferred_owner"] = "repository maintainer"
    learning.write_text(json.dumps(record), encoding="utf-8")
    started = start_direct(
        repo,
        "direct-one",
        "src.py",
        "hard-eng.gates.json",
        ".agents/learning/proven-gap.json",
        allow_subagents=True,
    )
    check("direct route refresh after learning update records", started.returncode == 0, started.stderr)
    checkpoint = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."],
        cwd=repo, capture_output=True, text=True, check=False,
        env={
            **os.environ,
            "HARD_ENG_SESSION_ID": "direct-one",
            "HARD_ENG_REQUEST_DIGEST": REQUEST_DIGEST,
        },
    )
    check("assigned learning allows task closure", checkpoint.returncode == 0, checkpoint.stderr)
    (repo / "other.py").write_text("value = 2\n", encoding="utf-8")
    checkpoint = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."],
        cwd=repo, capture_output=True, text=True, check=False,
        env={
            **os.environ,
            "HARD_ENG_SESSION_ID": "direct-one",
            "HARD_ENG_REQUEST_DIGEST": REQUEST_DIGEST,
        },
    )
    check("direct unknown outside write fails checkpoint", checkpoint.returncode != 0, checkpoint.stderr)


def check_lifecycle(root: Path) -> None:
    repo = root / "lifecycle"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    active = plan(repo, "one", "planning")
    source = repo / "src.py"
    source.write_text("value = 1\n", encoding="utf-8")

    for filename in (
        "page.html", "schema.sql", "api.graphql", "wire.proto", "settings.json",
        "config.yaml", "project.toml", "layout.xml", "Dockerfile", "Makefile",
        "build.gradle", "local.properties", "mystery.zzz", "extensionless",
    ):
        response, _ = run_hook(
            "codex", "pretooluse", edit_payload(repo, repo / filename)
        )
        check(
            f"planning blocks structurally product-like path {filename}",
            bool(denial(response, "codex")),
            repr(response),
        )

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
    wrong_session_write = edit_payload(repo, source)
    wrong_session_write["session_id"] = "wrong-session"
    response, _ = run_hook("codex", "pretooluse", wrong_session_write)
    check("building write rejects a different session", bool(denial(response, "codex")), repr(response))
    wrong_request_write = edit_payload(repo, source)
    wrong_request_write["request_digest"] = "sha256:" + "e" * 64
    response, _ = run_hook("codex", "pretooluse", wrong_request_write)
    check("building write rejects a different request", bool(denial(response, "codex")), repr(response))
    auth_path = active.parent / "receipts" / "authorization.json"
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, active))
    check("building blocks raw PLAN writes", bool(denial(response, "codex")), repr(response))
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, auth_path))
    check("building blocks raw receipt writes", bool(denial(response, "codex")), repr(response))
    parent_segment = edit_payload(repo, args={"file_path": str(repo / "src/../src.py")})
    response, _ = run_hook("codex", "pretooluse", parent_segment)
    check("write path with a parent segment blocks", bool(denial(response, "codex")), repr(response))

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
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    auth["allowed"] = ["approved-build", "parallel-subagents"]
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("claude", "pretooluse", agent_payload)
    check("explicitly authorized subagent is allowed", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", codex_agent_payload)
    check("explicitly authorized namespaced subagent is allowed", response is None, repr(response))
    wrong_session_agent = dict(codex_agent_payload, session_id="wrong-session")
    response, _ = run_hook("codex", "pretooluse", wrong_session_agent)
    check("authorized subagent rejects a different session", bool(denial(response, "codex")), repr(response))

    auth["approval_digest"] = "bad"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("bad authorization digest blocks", bool(denial(response, "codex")), repr(response))
    auth["approval_digest"] = "sha256:" + "c" * 64
    auth_path.write_text(json.dumps(auth), encoding="utf-8")

    auth_backup = auth_path.with_name("authorization.backup.json")
    auth_path.rename(auth_backup)
    auth_path.symlink_to(auth_backup.name)
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("symlinked authorization receipt blocks", bool(denial(response, "codex")), repr(response))
    auth_path.unlink()
    auth_backup.rename(auth_path)

    manifest_path = repo / "hard-eng.gates.json"
    manifest_backup = repo / "hard-eng.gates.backup.json"
    manifest_path.rename(manifest_backup)
    manifest_path.symlink_to(manifest_backup.name)
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("symlinked enforcement manifest blocks", bool(denial(response, "codex")), repr(response))
    manifest_path.unlink()
    manifest_backup.rename(manifest_path)

    subprocess.run(
        ["git", "-C", str(repo), "add", "hard-eng.gates.json", "src.py"],
        check=True,
        env=git_env(),
    )
    subprocess.run(
        [
            "git", "-C", str(repo), "-c", "user.name=Test", "-c",
            "user.email=test@example.invalid", "commit", "-qm", "change head",
        ],
        check=True,
        env=git_env(),
    )
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("building write rejects a changed HEAD", bool(denial(response, "codex")), repr(response))
    write_evidence(repo, active.parent, "one")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("refreshed current HEAD allows building write", response is None, repr(response))

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
    fake_bin = root / "fake-bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python3"
    fake_python.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake_python.chmod(0o755)
    hostile_path = {**os.environ, "PATH": f"{fake_bin}:{os.environ['PATH']}"}
    response, _ = run_hook("codex", "pretooluse", external_delete, env=hostile_path)
    check("exact approved external delete is allowed once", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", external_delete, env=hostile_path)
    check("PATH hijack cannot forge protected consumption", bool(denial(response, "codex")), repr(response))

    process_secret = "hook-process-secret-4f9c2e7a"
    secret_payload = {
        "cwd": str(repo),
        "tool_name": "mcp__vendor__sendRequest",
        "tool_input": {"headers": {"authorization": process_secret}},
    }
    approved_secret = authorize_protected(
        repo, active, secret_payload, "secret-exposure", "fixture request",
    )
    check("exact secret action approval records", approved_secret.returncode == 0, approved_secret.stderr)
    observed_commands = ""
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(run_hook, "codex", "pretooluse", secret_payload)
        samples = 0
        while not pending.done():
            process_list = subprocess.run(
                ["ps", "-axo", "command="],
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
            samples += 1
            observed_commands += process_list.stdout
        secret_response, _ = pending.result()
    check("secret action is allowed once", secret_response is None, repr(secret_response))
    check("secret action process list was sampled", samples > 0)
    check("protected consumer argv omits secret input", process_secret not in observed_commands)

    for label, payload in (
        ("external payment", {"cwd": str(repo), "tool_name": "mcp__stripe__createPayment", "tool_input": {"amount": 10}}),
        ("external account change", {"cwd": str(repo), "tool_name": "mcp__auth__updateUser", "tool_input": {"user": "one"}}),
        ("external secret send", {"cwd": str(repo), "tool_name": "mcp__vendor__sendRequest", "tool_input": {"headers": {"apiToken": "fixture"}}}),
    ):
        response, _ = run_hook("codex", "pretooluse", payload)
        check(f"{label} blocks", bool(denial(response, "codex")), repr(response))
    for label, tool_name in (
        ("external close", "mcp__vendor__closeTicket"),
        ("external trigger", "mcp__vendor__triggerJob"),
        ("external upload", "mcp__vendor__uploadBlob"),
        ("external read-prefix mutation", "mcp__vendor__checkAndDeploy"),
        ("external unknown", "mcp__vendor__mysteryThing"),
    ):
        response, _ = run_hook(
            "codex", "pretooluse",
            {"cwd": str(repo), "tool_name": tool_name, "tool_input": {"value": "one"}},
        )
        check(f"{label} is not assumed read-only", bool(denial(response, "codex")), repr(response))
    for label, value in (
        ("Authorization header", "Authorization: Bearer abcdefghijklmnop"),
        ("cookie", "Cookie: session=abcdefghijklmnop"),
        ("bearer value", "Bearer abcdefghijklmnop"),
        ("PEM private key", "-----BEGIN PRIVATE KEY-----"),
        ("DSN", "postgresql://user:pass@example.test/db"),
        ("signed URL", "https://example.test/file?signature=abcdefghijklmnop"),
    ):
        response, _ = run_hook(
            "codex", "pretooluse",
            {"cwd": str(repo), "tool_name": "mcp__vendor__get_status", "tool_input": {"body": value}},
        )
        check(f"{label} is blocked without leaking value", bool(denial(response, "codex")), repr(response))
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
    wrong_session_create = dict(create_row, session_id="wrong-session")
    response, _ = run_hook("codex", "pretooluse", wrong_session_create)
    check("autonomous additive live write rejects a different session", bool(denial(response, "codex")), repr(response))
    autonomous_message = {
        "cwd": str(repo), "tool_name": "mcp__vendor__send_message",
        "tool_input": {"recipient": "one", "body": "hello"},
    }
    response, _ = run_hook("codex", "pretooluse", autonomous_message)
    check("autonomous unrelated live write still blocks", bool(denial(response, "codex")), repr(response))

    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, outside))
    check("repository policy blocks outside target", bool(denial(response, "codex")), repr(response))

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
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    changed = repo / "generated.txt"
    changed.write_text("user bytes\n", encoding="utf-8")
    active = plan(repo, "one", "building")
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

    safe_read = dict(payload, tool_input={"command": "rg -n thing src"})
    response, _ = run_hook("codex", "pretooluse", safe_read)
    check("normal shell read remains allowed", response is None, repr(response))
    variable_argument = dict(
        payload,
        tool_input={"command": 'rg -n thing "$HOME/project"'},
    )
    response, _ = run_hook("codex", "pretooluse", variable_argument)
    check("simple command variable argument remains allowed", response is None, repr(response))
    for label, command in (
        ("git config reset", "git -c core.pager=cat reset --hard"),
        ("shell wrapper", "bash -c 'git reset --hard'"),
        ("command substitution", "printf '%s' $(git status)"),
        ("variable command", "action='git reset --hard'; $action"),
        ("pipeline", "git status | rm -f status.txt"),
        ("interpreter evaluation", "python3 -c 'print(1)'"),
        ("unregistered wrapper", "./unknown-wrapper.sh status"),
        ("link creation", "ln -s outside hard-eng.gates.json"),
    ):
        response, _ = run_hook(
            "codex", "pretooluse", dict(payload, tool_input={"command": command})
        )
        check(f"{label} shell indirection blocks", bool(denial(response, "codex")), repr(response))

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
    upstream_rebase = dict(payload, tool_input=agent_fixture("upstream-rebase-allowed.json"))
    response, _ = run_hook("codex", "pretooluse", upstream_rebase)
    check("ordinary upstream rebase is allowed", response is None, repr(response))
    interactive_rebase = dict(payload, tool_input=agent_fixture("interactive-rebase-blocked.json"))
    response, _ = run_hook("codex", "pretooluse", interactive_rebase)
    check("interactive rebase blocks", "history rewrite" in (denial(response, "codex") or ""))
    local_rebase = dict(payload, tool_input={"command": "git rebase main"})
    response, _ = run_hook("codex", "pretooluse", local_rebase)
    check("non-upstream rebase blocks", "history rewrite" in (denial(response, "codex") or ""))

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
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    active = plan(repo, "one", "building")
    command = ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."]
    def run() -> subprocess.CompletedProcess[str]:
        return subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
    clean = run()
    check("clean checkpoint passes", clean.returncode == 0, clean.stderr)
    invalid_learning = repo / ".agents/learning/broken.json"
    invalid_learning.parent.mkdir(parents=True)
    invalid_learning.write_text("{}\n", encoding="utf-8")
    invalid = run()
    check(
        "checkpoint blocks invalid learning state",
        invalid.returncode != 0 and "learning state is invalid" in invalid.stderr,
        invalid.stderr,
    )
    invalid_learning.unlink()
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

    green_repo = root / "green-checkpoint"
    subprocess.run(["git", "init", "-q", str(green_repo)], check=True, env=git_env())
    manifest(green_repo)
    green_plan = plan(green_repo, "one", "green")
    validator = green_repo / "skills/he/scripts/plan_state.py"
    validator.parent.mkdir(parents=True)
    validator.write_text(
        "import os, sys\n"
        "valid = (\n"
        "    'assert-green' in sys.argv\n"
        "    and '--artifact-only' in sys.argv\n"
        "    and '--session-id' not in sys.argv\n"
        "    and '--request-digest' not in sys.argv\n"
        "    and os.environ.get('GREEN_FIXTURE_FAIL') != '1'\n"
        ")\n"
        "raise SystemExit(0 if valid else 1)\n",
        encoding="utf-8",
    )
    (green_repo / "ready.py").write_text("value = 1\n", encoding="utf-8")
    write_evidence(green_repo, green_plan.parent, "one")
    green_command = ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."]
    green_environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"HARD_ENG_SESSION_ID", "HARD_ENG_REQUEST_DIGEST"}
    }
    exact_green = subprocess.run(
        green_command,
        cwd=green_repo,
        capture_output=True,
        text=True,
        check=False,
        env=green_environment,
    )
    check(
        "checkpoint accepts an exact green artifact",
        exact_green.returncode == 0,
        exact_green.stderr,
    )
    stale_green = subprocess.run(
        green_command,
        cwd=green_repo,
        capture_output=True,
        text=True,
        check=False,
        env={**green_environment, "GREEN_FIXTURE_FAIL": "1"},
    )
    check(
        "checkpoint rejects a stale green artifact",
        stale_green.returncode != 0
        and "green repository snapshot no longer matches" in stale_green.stderr,
        stale_green.stderr,
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

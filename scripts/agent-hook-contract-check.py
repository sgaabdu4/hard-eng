#!/usr/bin/env python3
"""Behavior checks for the shared agent hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from agent_hook_contract_lib import (
    BRIEF_FINGERPRINT,
    EVIDENCE,
    FAILURES,
    HOOK,
    ROOT,
    advice_context,
    agent_fixture,
    authorize_protected,
    authorize_protected_direct,
    check,
    check_direct_external_scope,
    denial,
    edit_payload,
    manifest,
    plan,
    run_hook,
    start_direct,
    write_evidence,
)

sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env


def check_unconfigured(root: Path) -> None:
    repo = root / "plain"
    repo.mkdir()
    (repo / ".git").mkdir()
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo))
    check("unconfigured repository is untouched", response is None, repr(response))


def check_advisory(root: Path) -> None:
    repo = root / "advice"
    repo.mkdir()
    (repo / ".git").mkdir()
    env = {**os.environ, "TMPDIR": str(root / "advice-tmp")}
    (root / "advice-tmp").mkdir()
    payload = edit_payload(repo)
    payload["session_id"] = "advice-one"
    response, _ = run_hook("claude", "pretooluse", payload, env=env)
    check(
        "unwired write advises routing without deciding permission",
        advice_context(response) is not None,
        repr(response),
    )
    repeat, _ = run_hook("claude", "pretooluse", payload, env=env)
    check("advice appears once per session", repeat is None, repr(repeat))
    fresh = dict(payload)
    fresh["session_id"] = "advice-two"
    response, _ = run_hook("claude", "pretooluse", fresh, env=env)
    check("new session advises again", advice_context(response) is not None, repr(response))
    bare = {
        "session_id": None,
        "cwd": str(repo),
        "tool_name": "Edit",
        "tool_input": {"file_path": str(repo / "src.py")},
    }
    response, _ = run_hook("claude", "pretooluse", bare, env=env)
    check("missing session id still advises", advice_context(response) is not None, repr(response))
    response, _ = run_hook("claude", "pretooluse", bare, env=env)
    check("missing session id deduplicates", response is None, repr(response))
    init_payload = {
        "session_id": "advice-init",
        "cwd": str(root),
        "tool_name": "Bash",
        "tool_input": agent_fixture("unwired-git-init-advised.json"),
    }
    response, _ = run_hook("claude", "pretooluse", init_payload, env=env)
    check("git init advises routing", advice_context(response) is not None, repr(response))
    plain_git = {**init_payload, "session_id": "advice-plain", "tool_input": agent_fixture("init-argument-silent.json")}
    response, _ = run_hook("claude", "pretooluse", plain_git, env=env)
    check("init as an argument stays silent", response is None, repr(response))
    codex_init, _ = run_hook("codex", "pretooluse", {**init_payload, "session_id": "advice-codex"}, env=env)
    check("codex runtime never advises", codex_init is None, repr(codex_init))
    batch = {
        "session_id": "advice-deny",
        "cwd": str(repo),
        "toolCalls": [
            {"name": "Edit", "args": {"file_path": str(repo / "src.py")}},
            {"name": "Bash", "args": {"command": "git push --force origin main"}},
        ],
    }
    response, _ = run_hook("claude", "pretooluse", batch, env=env)
    check("denial outranks advice in one batch", denial(response, "claude") is not None, repr(response))
    after_deny, _ = run_hook("claude", "pretooluse", {**payload, "session_id": "advice-deny"}, env=env)
    check("denied batch keeps the advice for later", advice_context(after_deny) is not None, repr(after_deny))
    wired = root / "advice-wired"
    subprocess.run(["git", "init", "-q", str(wired)], check=True, env=git_env())
    manifest(wired)
    elsewhere = root / "advice-elsewhere"
    elsewhere.mkdir()
    (elsewhere / ".git").mkdir()
    cross = {
        "session_id": "advice-cross",
        "cwd": str(wired),
        "tool_name": "Write",
        "tool_input": {"file_path": str(elsewhere / "notes.txt")},
    }
    response, _ = run_hook("claude", "pretooluse", cross, env=env)
    check(
        "wired session without Direct scope cannot write another repo", bool(denial(response, "claude")), repr(response)
    )
    repeat, _ = run_hook("claude", "pretooluse", cross, env=env)
    check("cross-repo Direct block is stable", bool(denial(repeat, "claude")), repr(repeat))
    inside = {**cross, "session_id": "advice-inside", "tool_input": {"file_path": str(wired / "src.py")}}
    response, _ = run_hook("claude", "pretooluse", inside, env=env)
    check("wired session without a Direct receipt blocks", bool(denial(response, "claude")), repr(response))
    homeless = {
        "session_id": "advice-homeless",
        "cwd": str(root),
        "tool_name": "Write",
        "tool_input": {"file_path": str(elsewhere / "more.txt")},
    }
    response, _ = run_hook("claude", "pretooluse", homeless, env=env)
    check(
        "session outside any repo writing into an unwired repo advises",
        advice_context(response) is not None,
        repr(response),
    )
    stray = {**homeless, "session_id": "advice-stray", "tool_input": {"file_path": str(root / "loose.txt")}}
    response, _ = run_hook("claude", "pretooluse", stray, env=env)
    check("write outside any repo stays silent", response is None, repr(response))
    garbled = {"session_id": "advice-garbled", "cwd": str(root), "tool_name": "Write", "tool_input": "not json"}
    response, _ = run_hook("claude", "pretooluse", garbled, env=env)
    check("malformed ungoverned write stays silent", response is None, repr(response))


def check_direct_route(root: Path) -> None:
    repo = root / "direct"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    source = repo / "src.py"
    source.write_text("value = 1\n", encoding="utf-8")
    payload = edit_payload(repo, source)
    payload["session_id"] = "direct-one"
    response, _ = run_hook("codex", "pretooluse", payload)
    check(
        "direct write without route receipt blocks",
        "no valid Direct receipt" in (denial(response, "codex") or ""),
        repr(response),
    )

    started = start_direct(repo, "src.py")
    check("direct route receipt records", started.returncode == 0, started.stderr)
    shifted_env = git_env()
    shifted_env["TZ"] = "UTC+12" if datetime.now(timezone.utc).hour < 12 else "UTC-14"
    started = start_direct(repo, "src.py", env=shifted_env)
    receipt = json.loads((repo / ".git/hard-eng/current-direct.json").read_text())
    shifted_date = subprocess.run(
        [sys.executable, "-c", "from datetime import date; print(date.today().isoformat())"],
        capture_output=True,
        text=True,
        check=True,
        env=shifted_env,
    ).stdout.strip()
    check(
        "direct timezone fixture crosses the UTC date",
        shifted_date != receipt["created_at"][:10],
        f"local={shifted_date} receipt={receipt!r}",
    )
    validated = subprocess.run(
        [sys.executable, str(EVIDENCE), "check-direct", "--repo", str(repo)],
        capture_output=True,
        text=True,
        check=False,
        env=shifted_env,
    )
    check("direct receipt survives a local date different from UTC", validated.returncode == 0, validated.stderr)
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct intended write is allowed", response is None, repr(response))
    (repo / "src.py").write_text("value = 2\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", payload)
    check("changed worktree artifact does not block a write", response is None, repr(response))
    started = start_direct(repo, "src.py")
    check("direct route refresh after worktree change records", started.returncode == 0, started.stderr)
    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent = list(pool.map(lambda _: run_hook("codex", "pretooluse", payload)[0], range(2)))
    check(
        "direct writes do not consume a one-use nonce",
        all(response is None for response in concurrent),
        repr(concurrent),
    )
    manifest_before = (repo / "hard-eng.gates.json").read_text(encoding="utf-8")
    (repo / "hard-eng.gates.json").write_text(
        manifest_before.replace('"schema_version": 1', '"schema_version": 1 '), encoding="utf-8"
    )
    response, _ = run_hook("codex", "pretooluse", payload)
    check("changed local research source waits for the checkpoint", response is None, repr(response))
    checkpoint = subprocess.run(
        ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    check(
        "checkpoint catches changed local research source",
        checkpoint.returncode != 0 and "direct local research source changed" in checkpoint.stderr,
        checkpoint.stderr,
    )
    manifest(repo)
    started = start_direct(repo, "src.py")
    check("direct route refresh records", started.returncode == 0, started.stderr)
    different_session = dict(payload, session_id="direct-two")
    response, _ = run_hook("codex", "pretooluse", different_session)
    check("direct write from a different session id passes", response is None, repr(response))
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "direct commit",
        ],
        check=True,
        env=git_env(),
    )
    response, _ = run_hook("codex", "pretooluse", payload)
    check("direct write after a commit passes", response is None, repr(response))
    outside = edit_payload(repo, repo / "other.py")
    outside["session_id"] = "direct-one"
    response, _ = run_hook("codex", "pretooluse", outside)
    check("direct write outside intended path blocks", bool(denial(response, "codex")), repr(response))

    widened = start_direct(repo, "src.py", "hard-eng.gates.json")
    check("re-running start-direct widens intended paths", widened.returncode == 0, widened.stderr)
    widened_target = edit_payload(repo, repo / "hard-eng.gates.json")
    widened_target["session_id"] = "direct-one"
    response, _ = run_hook("codex", "pretooluse", widened_target)
    check("write inside the widened scope is allowed", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", outside)
    check("write still outside the widened scope blocks", bool(denial(response, "codex")), repr(response))

    agent = {"cwd": str(repo), "session_id": "direct-one", "tool_name": "Agent", "tool_input": {"prompt": "inspect"}}
    response, _ = run_hook("claude", "pretooluse", agent)
    check("direct subagent is not blocked by Hard Eng", response is None, repr(response))
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
    learning_agent = {**agent, "tool_input": {"prompt": "Use he-learn for .agents/learning/proven-gap.json"}}
    response, learning_stderr = run_hook("claude", "pretooluse", learning_agent)
    check(
        "recorded he-learn helper is allowed",
        response is None,
        f"{response!r} stderr={learning_stderr} record={learning.read_text(encoding='utf-8')}",
    )
    response, _ = run_hook("claude", "pretooluse", learning_agent)
    check("a second helper call is not blocked by the tool hook", response is None, repr(response))
    missing_learning = {**agent, "tool_input": {"prompt": "Use he-learn for .agents/learning/missing-gap.json"}}
    response, _ = run_hook("claude", "pretooluse", missing_learning)
    check("a missing learning record does not block tool access", response is None, repr(response))
    intended = ("hard-eng.gates.json", ".agents/learning/proven-gap.json")
    started = start_direct(repo, "src.py", *intended, allow_subagents=True)
    check("direct subagent authorization records", started.returncode == 0, started.stderr)
    response, _ = run_hook("claude", "pretooluse", agent)
    check("direct explicitly authorized subagent is allowed", response is None, repr(response))

    check_direct_external_scope(repo, learning, intended)


def check_lifecycle(root: Path) -> None:
    repo = root / "lifecycle"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    active = plan(repo, "one", "planning")
    source = repo / "src.py"
    source.write_text("value = 1\n", encoding="utf-8")
    receipts = active.parent / "receipts"
    receipts.mkdir(exist_ok=True)
    for name in ("S-1.json", "S-1-verify-before.json"):
        (receipts / name).write_text("{}\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, receipts / "S-1.json"))
    check("raw write to a slice receipt blocks", "lifecycle-owned" in (denial(response, "codex") or ""), repr(response))
    start_direct(repo, "features/one/receipts/S-1-verify-before.json")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, receipts / "S-1-verify-before.json"))
    check("verifier evidence file is writable under a Direct receipt", response is None, repr(response))
    (repo / ".git/hard-eng/current-direct.json").unlink()

    for filename in (
        "page.html",
        "schema.sql",
        "api.graphql",
        "wire.proto",
        "settings.json",
        "config.yaml",
        "project.toml",
        "layout.xml",
        "Dockerfile",
        "Makefile",
        "build.gradle",
        "local.properties",
        "mystery.zzz",
        "extensionless",
    ):
        response, _ = run_hook("codex", "pretooluse", edit_payload(repo, repo / filename))
        check(f"planning allows structurally product-like path {filename}", response is None, repr(response))

    for runtime in ("codex", "claude", "copilot"):
        response, _ = run_hook(runtime, "pretooluse", edit_payload(repo, source))
        check(f"planning allows source write on {runtime}", response is None, repr(response))

    active.write_text(
        active.read_text()
        .replace("planning", "building")
        .replace("approval_status = pending", "approval_status = approved")
        .replace("approval_fingerprint = none", f"approval_fingerprint = {BRIEF_FINGERPRINT}"),
        encoding="utf-8",
    )
    write_evidence(repo, active.parent, "one")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("building allows source write", response is None, repr(response))
    wrong_session_write = edit_payload(repo, source)
    wrong_session_write["session_id"] = "wrong-session"
    response, _ = run_hook("codex", "pretooluse", wrong_session_write)
    check("building write allows a different session", response is None, repr(response))
    wrong_request_write = edit_payload(repo, source)
    wrong_request_write["request_digest"] = "sha256:" + "e" * 64
    response, _ = run_hook("codex", "pretooluse", wrong_request_write)
    check("building write allows a different request", response is None, repr(response))
    auth_path = active.parent / "receipts" / "authorization.json"
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, active))
    check("building blocks raw PLAN writes", bool(denial(response, "codex")), repr(response))
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, auth_path))
    check("building blocks raw receipt writes", bool(denial(response, "codex")), repr(response))

    tickets_dir = active.parent / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("T-1.md", "T-int.md"):
        (tickets_dir / name).write_text("<!-- hard-eng-ticket-state:v1 -->\n", encoding="utf-8")
        response, _ = run_hook("codex", "pretooluse", edit_payload(repo, tickets_dir / name))
        check(f"building blocks raw ticket writes ({name})", bool(denial(response, "codex")), repr(response))
    tool_input = {"command": f"printf '%s' 'claimed' > {tickets_dir / 'T-1.md'}"}
    shell_payload = {"session_id": "contract", "cwd": str(repo), "tool_name": "bash", "tool_input": tool_input}
    response, _ = run_hook("codex", "pretooluse", shell_payload)
    check("a shell write to a ticket file is not blocked by the tool hook", response is None, repr(response))

    parent_segment = edit_payload(repo, args={"file_path": str(repo / "src/../src.py")})
    response, _ = run_hook("codex", "pretooluse", parent_segment)
    check("write path with a parent segment blocks", bool(denial(response, "codex")), repr(response))

    agent_payload = {"cwd": str(repo), "tool_name": "Agent", "tool_input": {"prompt": "inspect"}}
    response, _ = run_hook("claude", "pretooluse", agent_payload)
    check("subagent is not blocked by Hard Eng", response is None, repr(response))
    codex_agent_payload = {
        "cwd": str(repo),
        "tool_name": "collaboration.spawn_agent",
        "tool_input": {"message": "inspect"},
    }
    response, _ = run_hook("codex", "pretooluse", codex_agent_payload)
    check("namespaced Codex subagent is not blocked by Hard Eng", response is None, repr(response))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    auth["allowed"] = ["approved-build", "parallel-subagents"]
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("claude", "pretooluse", agent_payload)
    check("explicitly authorized subagent is allowed", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", codex_agent_payload)
    check("explicitly authorized namespaced subagent is allowed", response is None, repr(response))
    wrong_session_agent = dict(codex_agent_payload, session_id="wrong-session")
    response, _ = run_hook("codex", "pretooluse", wrong_session_agent)
    check("subagent access is not tied to a session", response is None, repr(response))

    auth["approval_digest"] = "bad"
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("bad authorization digest does not block normal writes", response is None, repr(response))
    auth["approval_digest"] = "sha256:" + "c" * 64
    auth_path.write_text(json.dumps(auth), encoding="utf-8")

    auth_backup = auth_path.with_name("authorization.backup.json")
    auth_path.rename(auth_backup)
    auth_path.symlink_to(auth_backup.name)
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("symlinked authorization receipt does not block normal writes", response is None, repr(response))
    auth_path.unlink()
    auth_backup.rename(auth_path)

    manifest_path = repo / "hard-eng.gates.json"
    manifest_backup = repo / "hard-eng.gates.backup.json"
    manifest_path.rename(manifest_backup)
    manifest_path.symlink_to(manifest_backup.name)
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("symlinked enforcement manifest does not block normal writes", response is None, repr(response))
    manifest_path.unlink()
    manifest_backup.rename(manifest_path)

    subprocess.run(["git", "-C", str(repo), "add", "hard-eng.gates.json", "src.py"], check=True, env=git_env())
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "change head",
        ],
        check=True,
        env=git_env(),
    )
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("building write allows a changed HEAD", response is None, repr(response))
    write_evidence(repo, active.parent, "one")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("refreshed current HEAD allows building write", response is None, repr(response))

    external_delete = {"cwd": str(repo), "tool_name": "mcp__appwrite__deleteRows", "tool_input": {"table": "users"}}
    response, _ = run_hook("codex", "pretooluse", external_delete)
    check("external destructive tool blocks", "destructive" in (denial(response, "codex") or ""))
    approved_delete = authorize_protected(
        repo, active, external_delete, "data-deletion-or-destructive-schema", "users table"
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
    approved_secret = authorize_protected(repo, active, secret_payload, "secret-exposure", "fixture request")
    check("exact secret action approval records", approved_secret.returncode == 0, approved_secret.stderr)
    observed_commands = ""
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(run_hook, "codex", "pretooluse", secret_payload)
        samples = 0
        while not pending.done():
            process_list = subprocess.run(
                ["ps", "-axo", "command="], check=False, capture_output=True, text=True, timeout=5
            )
            samples += 1
            observed_commands += process_list.stdout
        secret_response, _ = pending.result()
    check("secret action is allowed once", secret_response is None, repr(secret_response))
    check("secret action process list was sampled", samples > 0)
    check("protected consumer argv omits secret input", process_secret not in observed_commands)

    for label, payload in (
        (
            "external secret send",
            {
                "cwd": str(repo),
                "tool_name": "mcp__vendor__sendRequest",
                "tool_input": {"headers": {"apiToken": "fixture"}},
            },
        ),
    ):
        response, _ = run_hook("codex", "pretooluse", payload)
        check(f"{label} blocks", bool(denial(response, "codex")), repr(response))
    for label, payload in (
        (
            "external payment",
            {"cwd": str(repo), "tool_name": "mcp__stripe__createPayment", "tool_input": {"amount": 10}},
        ),
        (
            "external account change",
            {"cwd": str(repo), "tool_name": "mcp__auth__updateUser", "tool_input": {"user": "one"}},
        ),
    ):
        response, _ = run_hook("codex", "pretooluse", payload)
        check(f"{label} is allowed", response is None, repr(response))
    for label, tool_name in (
        ("external close", "mcp__vendor__closeTicket"),
        ("external trigger", "mcp__vendor__triggerJob"),
        ("external upload", "mcp__vendor__uploadBlob"),
        ("external read-prefix mutation", "mcp__vendor__checkAndDeploy"),
        ("external unknown", "mcp__vendor__mysteryThing"),
        ("external archive", "mcp__vendor__archiveTicket"),
        ("external remove", "mcp__vendor__removeLabel"),
        ("external clear", "mcp__vendor__clearFilters"),
        ("Chrome snapshot", "mcp__chrome__takeSnapshot"),
        ("Chrome navigation", "mcp__chrome__navigatePage"),
        ("Chrome click", "mcp__chrome__click"),
    ):
        response, _ = run_hook(
            "codex", "pretooluse", {"cwd": str(repo), "tool_name": tool_name, "tool_input": {"value": "one"}}
        )
        check(f"{label} is allowed", response is None, repr(response))
    for label, value in (
        ("Authorization header", "Authorization: Bearer abcdefghijklmnop"),
        ("cookie", "Cookie: session=abcdefghijklmnop"),
        ("bearer value", "Bearer abcdefghijklmnop"),
        ("PEM private key", "-----BEGIN PRIVATE KEY-----"),
        ("DSN", "postgresql://user:pass@example.test/db"),
        ("signed URL", "https://example.test/file?signature=abcdefghijklmnop"),
    ):
        response, _ = run_hook(
            "codex",
            "pretooluse",
            {"cwd": str(repo), "tool_name": "mcp__vendor__get_status", "tool_input": {"body": value}},
        )
        check(f"{label} is blocked without leaking value", bool(denial(response, "codex")), repr(response))
    benign_external = {"cwd": str(repo), "tool_name": "mcp__vendor__get_status", "tool_input": {}}
    response, _ = run_hook("codex", "pretooluse", benign_external)
    check("benign external read is allowed", response is None, repr(response))

    create_row = {
        "cwd": str(repo),
        "tool_name": "mcp__appwrite__createRow",
        "tool_input": {"table": "events", "value": "one"},
    }
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("standard mode live write is allowed", response is None, repr(response))

    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    auth["mode"] = "autonomous"
    auth["allowed"] = [
        "additive-live-data-or-schema",
        "build-and-verify",
        "commit-push-pr-merge-ci",
        "named-deployment",
        "parallel-subagents",
        "planning-and-engineering-decisions",
    ]
    auth_path.write_text(json.dumps(auth), encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", create_row)
    check("autonomous additive live write is allowed", response is None, repr(response))
    wrong_session_create = dict(create_row, session_id="wrong-session")
    response, _ = run_hook("codex", "pretooluse", wrong_session_create)
    check("additive live write is not tied to a session", response is None, repr(response))
    autonomous_message = {
        "cwd": str(repo),
        "tool_name": "mcp__vendor__send_message",
        "tool_input": {"recipient": "one", "body": "hello"},
    }
    response, _ = run_hook("codex", "pretooluse", autonomous_message)
    check("unrelated live write is allowed", response is None, repr(response))

    outside = repo.parent / "outside.py"
    outside.write_text("value = 1\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, outside))
    check("repository policy allows outside target", response is None, repr(response))

    extra = active.parent / "notes" / "detail.md"
    extra.parent.mkdir()
    extra.write_text("extra\n", encoding="utf-8")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("extra Markdown does not block tool access", response is None, repr(response))
    extra.unlink()

    second = plan(repo, "two", "build-ready")
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("two active plans do not block tool access", response is None, repr(response))
    second.write_text(second.read_text().replace("build-ready", "shipped"), encoding="utf-8")

    patch = f"*** Begin Patch\n*** Delete File: {active}\n*** End Patch\n"
    response, _ = run_hook(
        "codex", "pretooluse", {"cwd": str(repo), "tool_name": "apply_patch", "tool_input": {"patch": patch}}
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

    cmd = "mv features/one/PLAN.md features/one/OLD.md"
    rename = {"cwd": str(repo), "tool_name": "exec_command", "tool_input": {"cmd": cmd}}
    response, _ = run_hook("codex", "pretooluse", rename)
    check("active PLAN shell rename is allowed", response is None, repr(response))

    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, args="{"))
    check("malformed known edit is left to the tool", response is None, repr(response))


def check_shell_safety(root: Path) -> None:
    repo = root / "shell"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    changed = repo / "generated.txt"
    changed.write_text("user bytes\n", encoding="utf-8")
    active = plan(repo, "one", "building")
    payload = {"cwd": str(repo), "tool_name": "Bash", "tool_input": {"command": "generator --output generated.txt"}}
    pre, _ = run_hook("codex", "pretooluse", payload)
    post, _ = run_hook("codex", "posttooluse", payload)
    check("unknown shell write is not pre-blocked", pre is None, repr(pre))
    check("unknown shell write is not post-blocked", post is None, repr(post))
    check("unknown shell bytes remain", changed.read_text() == "user bytes\n")
    destructive = {"command": "git reset --hard HEAD"}
    shaped = {"cwd": str(repo), "toolName": "bash", "toolArgs": destructive}
    response, _ = run_hook("claude", "pretooluse", shaped)
    check("Copilot payload answers in Copilot format", denial(response, "copilot") is not None, repr(response))

    bad_rg = dict(payload, tool_input={"command": "rg -rn thing src"})
    response, _ = run_hook("codex", "pretooluse", bad_rg)
    check("ripgrep typo is left to ripgrep", response is None, repr(response))

    exec_bad_rg = {"cwd": str(repo), "tool_name": "exec_command", "tool_input": {"cmd": "rg -rn thing src"}}
    response, _ = run_hook("codex", "pretooluse", exec_bad_rg)
    check("Codex exec command typo is left to ripgrep", response is None, repr(response))

    safe_read = dict(payload, tool_input={"command": "rg -n thing src"})
    response, _ = run_hook("codex", "pretooluse", safe_read)
    check("normal shell read remains allowed", response is None, repr(response))
    for label, command in (
        ("Wrangler inspection", "wrangler deployments list"),
        ("Wrangler upload", "wrangler versions upload"),
    ):
        response, _ = run_hook("codex", "pretooluse", dict(payload, tool_input={"command": command}))
        check(f"{label} is allowed", response is None, repr(response))
    wrangler_delete = dict(payload, tool_input={"command": "wrangler delete worker-one"})
    response, _ = run_hook("codex", "pretooluse", wrangler_delete)
    check("Wrangler permanent delete blocks", "permanent" in (denial(response, "codex") or "").lower(), repr(response))
    variable_argument = dict(payload, tool_input={"command": 'rg -n thing "$HOME/project"'})
    response, _ = run_hook("codex", "pretooluse", variable_argument)
    check("simple command variable argument remains allowed", response is None, repr(response))
    for label, command in (
        ("command substitution", "printf '%s' $(git status)"),
        ("interpreter evaluation", "python3 -c 'print(1)'"),
        ("unregistered wrapper", "./unknown-wrapper.sh status"),
        ("link creation", "ln -s outside hard-eng.gates.json"),
        ("pipeline", "git status | rm -f status.txt"),
    ):
        response, _ = run_hook("codex", "pretooluse", dict(payload, tool_input={"command": command}))
        check(f"{label} is allowed", response is None, repr(response))
    for label, command in (
        ("git config reset", "git -c core.pager=cat reset --hard"),
        ("shell wrapper", "bash -c 'git reset --hard'"),
        ("variable command", "action='git reset --hard'; $action"),
    ):
        response, _ = run_hook("codex", "pretooluse", dict(payload, tool_input={"command": command}))
        check(f"{label} destructive indirection blocks", bool(denial(response, "codex")), repr(response))

    discard = dict(payload, tool_input={"command": "git restore src.py"})
    response, _ = run_hook("codex", "pretooluse", discard)
    check("Git discard blocks", "discard" in (denial(response, "codex") or "").lower())

    stash = dict(payload, tool_input={"command": "git stash push"})
    response, _ = run_hook("codex", "pretooluse", stash)
    check("recoverable stash is allowed", response is None, repr(response))

    unstage = dict(payload, tool_input={"command": "git restore --staged src.py"})
    response, _ = run_hook("codex", "pretooluse", unstage)
    check("unstage without worktree restore is allowed", response is None, repr(response))

    staged_worktree = dict(payload, tool_input={"command": "git restore --staged --worktree src.py"})
    response, _ = run_hook("codex", "pretooluse", staged_worktree)
    check("staged worktree restore blocks", "discard" in (denial(response, "codex") or "").lower())

    source_restore = dict(payload, tool_input={"command": "git restore --source=HEAD~1 src.py"})
    response, _ = run_hook("codex", "pretooluse", source_restore)
    check("source restore of the worktree blocks", "discard" in (denial(response, "codex") or "").lower())

    source_unstage = dict(payload, tool_input={"command": "git restore --source=HEAD --staged src.py"})
    response, _ = run_hook("codex", "pretooluse", source_unstage)
    check("source restore of the index alone is allowed", response is None, repr(response))

    staged_pathspec = dict(payload, tool_input={"command": "git restore my--staged"})
    response, _ = run_hook("codex", "pretooluse", staged_pathspec)
    check("pathspec containing --staged still blocks", "discard" in (denial(response, "codex") or "").lower())

    staged_suffix = dict(payload, tool_input={"command": "git restore some-fileS"})
    response, _ = run_hook("codex", "pretooluse", staged_suffix)
    check("pathspec ending in capital S still blocks", "discard" in (denial(response, "codex") or "").lower())

    quoted_worktree = dict(payload, tool_input={"command": 'git restore --staged "--worktree" src.py'})
    response, _ = run_hook("codex", "pretooluse", quoted_worktree)
    check("quoted worktree restore blocks", "discard" in (denial(response, "codex") or "").lower())

    cluster_staged = dict(payload, tool_input={"command": "git restore -Sq src.py"})
    response, _ = run_hook("codex", "pretooluse", cluster_staged)
    check("mid-cluster staged restore is allowed", response is None, repr(response))

    prefixed_restore = dict(payload, tool_input={"command": "git -c core.pager=cat restore src.py"})
    response, _ = run_hook("codex", "pretooluse", prefixed_restore)
    check("config-prefixed restore blocks", "discard" in (denial(response, "codex") or "").lower())

    prefixed_staged = dict(payload, tool_input={"command": "git -c core.pager=cat restore --staged src.py"})
    response, _ = run_hook("codex", "pretooluse", prefixed_staged)
    check("config-prefixed staged restore is allowed", response is None, repr(response))

    treeish_checkout = dict(payload, tool_input={"command": "git checkout HEAD src.py"})
    response, _ = run_hook("codex", "pretooluse", treeish_checkout)
    check("treeish pathspec checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    treeish_dot = dict(payload, tool_input={"command": "git checkout HEAD~1 ."})
    response, _ = run_hook("codex", "pretooluse", treeish_dot)
    check("treeish dot checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    branch_start_point = dict(payload, tool_input={"command": "git checkout -b topic origin/main"})
    response, _ = run_hook("codex", "pretooluse", branch_start_point)
    check("branch creation with start point is allowed", response is None, repr(response))

    checkout_redirect = dict(payload, tool_input={"command": "git checkout feature/name 2>/dev/null"})
    response, _ = run_hook("codex", "pretooluse", checkout_redirect)
    check("branch checkout with redirect is allowed", response is None, repr(response))

    checkout_prose = dict(payload, tool_input={"command": 'git commit -m "Fix checkout page styling"'})
    response, _ = run_hook("codex", "pretooluse", checkout_prose)
    check("commit message naming a checkout feature is allowed", response is None, repr(response))

    chained_treeish = dict(payload, tool_input={"command": "cd /tmp/x && git checkout HEAD src.py"})
    response, _ = run_hook("codex", "pretooluse", chained_treeish)
    check("chained treeish pathspec checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    flagged_reset = dict(payload, tool_input={"command": "git reset -q --hard HEAD"})
    response, _ = run_hook("codex", "pretooluse", flagged_reset)
    check("flag-separated hard reset blocks", "discard" in (denial(response, "codex") or "").lower())

    reflog_delete = dict(payload, tool_input={"command": "git reflog delete stash@{0}"})
    response, _ = run_hook("codex", "pretooluse", reflog_delete)
    check("reflog deletion blocks", "recovery" in (denial(response, "codex") or "").lower())

    switch_force = dict(payload, tool_input={"command": "git switch -f main"})
    response, _ = run_hook("codex", "pretooluse", switch_force)
    check("forced branch switch blocks", "discard" in (denial(response, "codex") or "").lower())

    switch_plain = dict(payload, tool_input={"command": "git switch feature/name"})
    response, _ = run_hook("codex", "pretooluse", switch_plain)
    check("plain branch switch is allowed", response is None, repr(response))

    checkout_force = dict(payload, tool_input={"command": "git checkout -f main"})
    response, _ = run_hook("codex", "pretooluse", checkout_force)
    check("forced checkout switch blocks", "discard" in (denial(response, "codex") or "").lower())

    quiet_dot = dict(payload, tool_input={"command": "git checkout -q ."})
    response, _ = run_hook("codex", "pretooluse", quiet_dot)
    check("flagged whole-tree checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    dir_slash = dict(payload, tool_input={"command": "git checkout src/"})
    response, _ = run_hook("codex", "pretooluse", dir_slash)
    check("directory pathspec checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    multiline_switch = dict(payload, tool_input={"command": "git checkout main\ngit pull"})
    response, _ = run_hook("codex", "pretooluse", multiline_switch)
    check("multiline branch switch is allowed", response is None, repr(response))

    comment_switch = dict(payload, tool_input={"command": "git checkout main # switch back"})
    response, _ = run_hook("codex", "pretooluse", comment_switch)
    check("commented branch switch is allowed", response is None, repr(response))

    substitution_checkout = dict(payload, tool_input={"command": "git checkout $(git rev-parse HEAD)"})
    response, _ = run_hook("codex", "pretooluse", substitution_checkout)
    check("computed rev checkout is allowed", response is None, repr(response))

    leading_redirect = dict(payload, tool_input={"command": "git checkout 2>/dev/null main"})
    response, _ = run_hook("codex", "pretooluse", leading_redirect)
    check("leading redirect branch switch is allowed", response is None, repr(response))

    branch_reset_start = dict(payload, tool_input={"command": "git checkout -B topic origin/main"})
    response, _ = run_hook("codex", "pretooluse", branch_reset_start)
    check("branch reset with start point is allowed", response is None, repr(response))

    hardcoded_prose = dict(
        payload, tool_input={"command": 'git commit -m "reset the flow --hard-coded values were removed"'}
    )
    response, _ = run_hook("codex", "pretooluse", hardcoded_prose)
    check("hard-coded prose commit is allowed", response is None, repr(response))

    reflog_wrapper = dict(payload, tool_input={"command": "bash -c 'git reflog delete stash@{0}'"})
    response, _ = run_hook("codex", "pretooluse", reflog_wrapper)
    check("wrapper reflog deletion blocks", "recovery" in (denial(response, "codex") or "").lower())

    quoted_hard_reset = dict(payload, tool_input={"command": 'git reset "--hard"'})
    response, _ = run_hook("codex", "pretooluse", quoted_hard_reset)
    check("quoted hard reset blocks", "discard" in (denial(response, "codex") or "").lower())

    substitution_suffix = dict(payload, tool_input={"command": "git checkout HEAD src.py $(true)"})
    response, _ = run_hook("codex", "pretooluse", substitution_suffix)
    check("treeish checkout with trailing substitution blocks", "discard" in (denial(response, "codex") or "").lower())

    redirect_first_treeish = dict(payload, tool_input={"command": "git checkout 2>/dev/null HEAD src.py"})
    response, _ = run_hook("codex", "pretooluse", redirect_first_treeish)
    check("redirect-first treeish checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    newline_switch_force = dict(payload, tool_input={"command": "git pull\ngit switch -f main"})
    response, _ = run_hook("codex", "pretooluse", newline_switch_force)
    check("second-line forced switch blocks", "discard" in (denial(response, "codex") or "").lower())

    soft_reset_note = dict(payload, tool_input={"command": "git reset --soft HEAD\necho --hard notes"})
    response, _ = run_hook("codex", "pretooluse", soft_reset_note)
    check("soft reset with later hard note is allowed", response is None, repr(response))

    pathspec_file_checkout = dict(payload, tool_input={"command": "git checkout --pathspec-from-file=filelist"})
    response, _ = run_hook("codex", "pretooluse", pathspec_file_checkout)
    check("pathspec-from-file checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_file = dict(payload, tool_input={"command": "git checkout src/file.py"})
    response, _ = run_hook("codex", "pretooluse", checkout_file)
    check("checkout of a file blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_branch = dict(payload, tool_input={"command": "git checkout feature/name"})
    response, _ = run_hook("codex", "pretooluse", checkout_branch)
    check("checkout of a branch is allowed", response is None, repr(response))

    checkout_separator = dict(payload, tool_input={"command": "git checkout -- generated.txt"})
    response, _ = run_hook("codex", "pretooluse", checkout_separator)
    check("checkout -- of a file blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_dot = dict(payload, tool_input={"command": "git checkout ."})
    response, _ = run_hook("codex", "pretooluse", checkout_dot)
    check("checkout of the whole tree blocks", "discard" in (denial(response, "codex") or "").lower())

    checkout_detach = dict(payload, tool_input={"command": "git checkout --detach"})
    response, _ = run_hook("codex", "pretooluse", checkout_detach)
    check("checkout --detach is allowed", response is None, repr(response))

    stash_drop = dict(payload, tool_input={"command": "git stash drop"})
    response, _ = run_hook("codex", "pretooluse", stash_drop)
    check("stash drop denial names stash", "stash" in (denial(response, "codex") or "").lower())

    foreign_plan_rm = {"cwd": str(root), "tool_name": "Bash", "tool_input": {"command": f"rm {active}"}}
    response, _ = run_hook("codex", "pretooluse", foreign_plan_rm)
    check("active plan rm from a foreign cwd blocks", "deleting active" in (denial(response, "codex") or ""))

    dry_clean = dict(payload, tool_input={"command": "git clean -nd"})
    response, _ = run_hook("codex", "pretooluse", dry_clean)
    check("dry-run clean is allowed", response is None, repr(response))

    forced = dict(payload, tool_input={"command": "git push --force origin main"})
    response, _ = run_hook("codex", "pretooluse", forced)
    check("forced push blocks", "remote history" in (denial(response, "codex") or ""))
    approved_force = authorize_protected(repo, active, forced, "force-or-history-rewrite", "origin main")
    check("exact forced push approval records", approved_force.returncode == 0, approved_force.stderr)
    response, _ = run_hook("codex", "pretooluse", forced)
    check("exact approved forced push is allowed once", response is None, repr(response))
    response, _ = run_hook("codex", "pretooluse", forced)
    check("forced push approval is consumed", bool(denial(response, "codex")), repr(response))

    leased = dict(payload, tool_input={"command": "git push --force-with-lease=refs/heads/main origin main"})
    response, _ = run_hook("codex", "pretooluse", leased)
    check("value-form lease push blocks", "remote history" in (denial(response, "codex") or ""))

    argv_forced = dict(payload, tool_input={"command": ["git", "push", "--force", "origin", "main"]})
    response, _ = run_hook("codex", "pretooluse", argv_forced)
    check("argv-array forced push blocks", "remote history" in (denial(response, "codex") or ""))

    argv_read = dict(payload, tool_input={"command": ["git", "status"]})
    response, _ = run_hook("codex", "pretooluse", argv_read)
    check("argv-array read command is allowed", response is None, repr(response))

    cluster_forced = dict(payload, tool_input={"command": "git push -fu origin main"})
    response, _ = run_hook("codex", "pretooluse", cluster_forced)
    check("bundled short-flag force push blocks", "remote history" in (denial(response, "codex") or ""))

    system_config = dict(payload, tool_input={"command": "git config --system user.name x"})
    response, _ = run_hook("codex", "pretooluse", system_config)
    check("system config write blocks", "machine-wide" in (denial(response, "codex") or ""))

    prefixed_config = dict(payload, tool_input={"command": "git -c a=b config --global user.email x"})
    response, _ = run_hook("codex", "pretooluse", prefixed_config)
    check("option-prefixed global config write blocks", "machine-wide" in (denial(response, "codex") or ""))

    project_config_file = dict(payload, tool_input={"command": "git config --file /tmp/proj.cfg user.name x"})
    response, _ = run_hook("codex", "pretooluse", project_config_file)
    check("project config file write is allowed", response is None, repr(response))

    mariadb_drop = dict(payload, tool_input={"command": 'mariadb -e "DROP TABLE t"'})
    response, _ = run_hook("codex", "pretooluse", mariadb_drop)
    check("mariadb destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))

    tee_append = dict(payload, tool_input={"command": "printf x | tee --append $HOME/.zshrc"})
    response, _ = run_hook("codex", "pretooluse", tee_append)
    check("long-form tee append to home blocks", "home directory" in (denial(response, "codex") or ""))

    defaults_host = dict(payload, tool_input={"command": "defaults -currentHost write com.apple.dock size 32"})
    response, _ = run_hook("codex", "pretooluse", defaults_host)
    check("current-host defaults write blocks", "machine-wide" in (denial(response, "codex") or ""))

    npm_set = dict(payload, tool_input={"command": "npm set registry https://example.invalid"})
    response, _ = run_hook("codex", "pretooluse", npm_set)
    check("npm set alias blocks", "machine-wide" in (denial(response, "codex") or ""))

    multiline_push = dict(payload, tool_input={"command": "git push origin main\ntar -czf release.tgz build"})
    response, _ = run_hook("codex", "pretooluse", multiline_push)
    check("push before archive line is allowed", response is None, repr(response))

    home_config_file = dict(payload, tool_input={"command": "git config --file ~/.gitconfig user.name x"})
    response, _ = run_hook("codex", "pretooluse", home_config_file)
    check("home config file write blocks", "machine-wide" in (denial(response, "codex") or ""))

    pnpm_wrangler = dict(payload, tool_input={"command": "pnpm dlx wrangler delete my-worker"})
    response, _ = run_hook("codex", "pretooluse", pnpm_wrangler)
    check("pnpm dlx wrangler delete blocks", "permanent" in (denial(response, "codex") or "").lower())

    quoted_sql = dict(payload, tool_input={"command": 'mysql -e "SET FOREIGN_KEY_CHECKS=0; DROP TABLE x"'})
    response, _ = run_hook("codex", "pretooluse", quoted_sql)
    check("semicolon-separated destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))

    sql_then_prose = dict(payload, tool_input={"command": 'mysql -e "SELECT 1"; git commit -m "drop table doc"'})
    response, _ = run_hook("codex", "pretooluse", sql_then_prose)
    check("prose after a SQL read is allowed", response is None, repr(response))

    alias_config_file = dict(payload, tool_input={"command": "git config -f ~/.gitconfig user.name x"})
    response, _ = run_hook("codex", "pretooluse", alias_config_file)
    check("short-flag home config file write blocks", "machine-wide" in (denial(response, "codex") or ""))

    newline_config_write = dict(payload, tool_input={"command": "echo a\ngit config --global user.email x"})
    response, _ = run_hook("codex", "pretooluse", newline_config_write)
    check("second-line global config write blocks", "machine-wide" in (denial(response, "codex") or ""))

    short_yes_wrangler = dict(payload, tool_input={"command": "npx -y wrangler delete mydb"})
    response, _ = run_hook("codex", "pretooluse", short_yes_wrangler)
    check("short-flag npx wrangler delete blocks", "permanent" in (denial(response, "codex") or "").lower())

    bare_yarn_wrangler = dict(payload, tool_input={"command": "yarn wrangler delete my-worker"})
    response, _ = run_hook("codex", "pretooluse", bare_yarn_wrangler)
    check("bare yarn wrangler delete blocks", "permanent" in (denial(response, "codex") or "").lower())

    wrangler_message = dict(payload, tool_input={"command": 'yarn wrangler deploy --message "delete old assets"'})
    response, _ = run_hook("codex", "pretooluse", wrangler_message)
    check("wrangler deploy with quoted delete prose is allowed", response is None, repr(response))

    quoted_refspec = dict(payload, tool_input={"command": 'git push origin "+main"'})
    response, _ = run_hook("codex", "pretooluse", quoted_refspec)
    check("quoted force refspec push blocks", "remote history" in (denial(response, "codex") or ""))

    clobber_home = dict(payload, tool_input={"command": "echo x >| ~/.bashrc"})
    response, _ = run_hook("codex", "pretooluse", clobber_home)
    check("clobber redirect to home blocks", "home directory" in (denial(response, "codex") or ""))

    later_arg_sql = dict(payload, tool_input={"command": "psql -c 'SELECT 1;' -c 'TRUNCATE t'"})
    response, _ = run_hook("codex", "pretooluse", later_arg_sql)
    check("destructive SQL in a later argument blocks", "destructive database" in (denial(response, "codex") or ""))

    quoted_client_prose = dict(payload, tool_input={"command": 'echo "use mysql here" && echo drop table plan'})
    response, _ = run_hook("codex", "pretooluse", quoted_client_prose)
    check("quoted client name before prose is allowed", response is None, repr(response))

    dropdb_block = dict(payload, tool_input={"command": "dropdb devdb"})
    response, _ = run_hook("codex", "pretooluse", dropdb_block)
    check("database drop utility blocks", "destructive database" in (denial(response, "codex") or ""))

    admin_drop_block = dict(payload, tool_input={"command": "mysqladmin -f drop appdb"})
    response, _ = run_hook("codex", "pretooluse", admin_drop_block)
    check("admin utility drop blocks", "destructive database" in (denial(response, "codex") or ""))

    admin_status = dict(payload, tool_input={"command": "mysqladmin status"})
    response, _ = run_hook("codex", "pretooluse", admin_status)
    check("admin utility status is allowed", response is None, repr(response))

    nested_substitution_checkout = dict(
        payload, tool_input={"command": "git checkout $(git rev-parse $(echo HEAD)) src.py"}
    )
    response, _ = run_hook("codex", "pretooluse", nested_substitution_checkout)
    check("nested substitution treeish checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    stderr_merge_checkout = dict(payload, tool_input={"command": "git checkout 2>&1 HEAD src.py"})
    response, _ = run_hook("codex", "pretooluse", stderr_merge_checkout)
    check("stderr-merge treeish checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    quoted_substitution_checkout = dict(payload, tool_input={"command": 'git checkout "$(git branch --show-current)"'})
    response, _ = run_hook("codex", "pretooluse", quoted_substitution_checkout)
    check("quoted substitution branch checkout is allowed", response is None, repr(response))

    quoted_substitution_pathspec = dict(payload, tool_input={"command": 'git checkout "$(cat .b)" file.txt'})
    response, _ = run_hook("codex", "pretooluse", quoted_substitution_pathspec)
    check("quoted substitution with pathspec blocks", "discard" in (denial(response, "codex") or "").lower())

    pathspec_prose_commit = dict(
        payload, tool_input={"command": 'git commit -m "git checkout --pathspec-from-file support"'}
    )
    response, _ = run_hook("codex", "pretooluse", pathspec_prose_commit)
    check("pathspec-from-file prose commit is allowed", response is None, repr(response))

    wrangler_quoted_tag = dict(payload, tool_input={"command": 'npx wrangler deploy --tag "x" delete-me'})
    response, _ = run_hook("codex", "pretooluse", wrangler_quoted_tag)
    check("wrangler quoted value before delete word is allowed", response is None, repr(response))

    glued_eval_sql = dict(payload, tool_input={"command": "mysql -e'SET x=0; DROP TABLE t'"})
    response, _ = run_hook("codex", "pretooluse", glued_eval_sql)
    check("glued short-flag destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))

    span_gate_double = dict(payload, tool_input={"command": 'echo mysql notes"a; b" -c "drop table t"'})
    response, _ = run_hook("codex", "pretooluse", span_gate_double)
    check("mid-word double quote prose is allowed", response is None, repr(response))

    span_gate_single = dict(payload, tool_input={"command": "echo mysql notes'a; b' -c 'drop table t'"})
    response, _ = run_hook("codex", "pretooluse", span_gate_single)
    check("mid-word single quote prose is allowed", response is None, repr(response))

    argv_embedded_sql = dict(payload, tool_input={"command": ["mysql", "-e", "SET x; DROP TABLE t"]})
    response, _ = run_hook("codex", "pretooluse", argv_embedded_sql)
    check("argv-array embedded destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))

    dropdb_url = dict(payload, tool_input={"command": "curl https://dropdb.example.com/api"})
    response, _ = run_hook("codex", "pretooluse", dropdb_url)
    check("drop utility name inside a hostname is allowed", response is None, repr(response))

    dropdbx_file = dict(payload, tool_input={"command": "cat dropdbx.txt"})
    response, _ = run_hook("codex", "pretooluse", dropdbx_file)
    check("drop utility prefix word is allowed", response is None, repr(response))

    admin_ping_prose = dict(payload, tool_input={"command": "mysqladmin ping; echo drop plans"})
    response, _ = run_hook("codex", "pretooluse", admin_ping_prose)
    check("admin ping before prose segment is allowed", response is None, repr(response))

    wrangler_quoted_config = dict(payload, tool_input={"command": 'wrangler --config "w.toml" d1 delete x'})
    response, _ = run_hook("codex", "pretooluse", wrangler_quoted_config)
    check("wrangler quoted flag value before delete blocks", "permanent" in (denial(response, "codex") or "").lower())

    mid_redirect_checkout = dict(payload, tool_input={"command": "git checkout HEAD 2>/dev/null file.txt"})
    response, _ = run_hook("codex", "pretooluse", mid_redirect_checkout)
    check("mid-command redirect treeish checkout blocks", "discard" in (denial(response, "codex") or "").lower())

    trailing_redirect_checkout = dict(payload, tool_input={"command": "git checkout main > out.log"})
    response, _ = run_hook("codex", "pretooluse", trailing_redirect_checkout)
    check("trailing redirect branch checkout is allowed", response is None, repr(response))

    backtick_quoted_pathspec = dict(payload, tool_input={"command": 'git checkout "`cat .b`" file.txt'})
    response, _ = run_hook("codex", "pretooluse", backtick_quoted_pathspec)
    check("quoted backtick with pathspec blocks", "discard" in (denial(response, "codex") or "").lower())

    backtick_quoted_single = dict(payload, tool_input={"command": 'git checkout "`git branch --show-current`"'})
    response, _ = run_hook("codex", "pretooluse", backtick_quoted_single)
    check("quoted backtick single argument is allowed", response is None, repr(response))

    amend = dict(payload, tool_input={"command": "git commit --amend --no-edit"})
    response, _ = run_hook("codex", "pretooluse", amend)
    check("Git amend is allowed", response is None, repr(response))
    upstream_rebase = dict(payload, tool_input=agent_fixture("upstream-rebase-allowed.json"))
    response, _ = run_hook("codex", "pretooluse", upstream_rebase)
    check("ordinary upstream rebase is allowed", response is None, repr(response))
    interactive_rebase = dict(payload, tool_input=agent_fixture("interactive-rebase-blocked.json"))
    response, _ = run_hook("codex", "pretooluse", interactive_rebase)
    check("interactive rebase is allowed", response is None, repr(response))
    local_rebase = dict(payload, tool_input={"command": "git rebase main"})
    response, _ = run_hook("codex", "pretooluse", local_rebase)
    check("non-upstream rebase is allowed", response is None, repr(response))

    destructive_sql = dict(payload, tool_input={"command": "psql -c 'DROP TABLE users'"})
    response, _ = run_hook("codex", "pretooluse", destructive_sql)
    check("destructive SQL blocks", "destructive database" in (denial(response, "codex") or ""))


def check_hot_path_shape() -> None:
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted((ROOT / "scripts").glob("enforcement_*.pl")))
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
    shipping = plan(repo, "shipping", "green")
    with_green = run()
    check(
        "checkpoint checks the green brief beside the one being built",
        with_green.returncode != 0 and "green repository snapshot no longer matches" in with_green.stderr,
        with_green.stderr,
    )
    shipping.write_text(shipping.read_text().replace("= green", "= building"), encoding="utf-8")
    two_building = run()
    check(
        "checkpoint blocks two briefs under construction",
        two_building.returncode != 0 and "under construction" in two_building.stderr,
        two_building.stderr,
    )
    shipping.write_text(shipping.read_text().replace("= building", "= shipped"), encoding="utf-8")
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
    tickets = active.parent / "tickets"
    tickets.mkdir(parents=True)
    for name in ("T-1.md", "T-int.md"):
        (tickets / name).write_text("<!-- hard-eng-ticket-state:v1 -->\n", encoding="utf-8")
    allowed = run()
    check("checkpoint allows untracked ticket files", allowed.returncode == 0, allowed.stderr)
    (tickets / "notes.md").write_text("extra\n", encoding="utf-8")
    stray = run()
    check(
        "checkpoint blocks extra Markdown under tickets/",
        stray.returncode != 0 and "notes.md" in stray.stderr,
        stray.stderr,
    )
    (tickets / "notes.md").unlink()
    (active.parent / "notes.md").write_text("extra\n", encoding="utf-8")
    blocked = run()
    check("checkpoint blocks extra Markdown", blocked.returncode != 0 and "notes.md" in blocked.stderr, blocked.stderr)

    planning_repo = root / "planning-checkpoint"
    planning_repo.mkdir()
    subprocess.run(["git", "init", "-q", str(planning_repo)], check=True, env=git_env())
    manifest(planning_repo)
    plan(planning_repo, "one", "planning")
    (planning_repo / "late.py").write_text("value = 1\n", encoding="utf-8")
    planning = subprocess.run(command, cwd=planning_repo, capture_output=True, text=True, check=False)
    check(
        "checkpoint catches unknown planning source write",
        planning.returncode != 0 and "late.py" in planning.stderr,
        planning.stderr,
    )
    mixed_repo = root / "mixed-direct-checkpoint"
    subprocess.run(["git", "init", "-q", str(mixed_repo)], check=True, env=git_env())
    manifest(mixed_repo)
    plan(mixed_repo, "one", "planning")
    started = start_direct(mixed_repo, "src.py")
    check("mixed checkpoint direct route records", started.returncode == 0, started.stderr)
    (mixed_repo / "src.py").write_text("value = 1\n", encoding="utf-8")
    mixed = subprocess.run(command, cwd=mixed_repo, capture_output=True, text=True, check=False)
    check("checkpoint accepts matching Direct work beside an active plan", mixed.returncode == 0, mixed.stderr)

    green_repo = root / "green-checkpoint"
    subprocess.run(["git", "init", "-q", str(green_repo)], check=True, env=git_env())
    manifest(green_repo)
    green_plan = plan(green_repo, "one", "green")
    install = root / "green-install"
    (install / "scripts").mkdir(parents=True)
    for helper in sorted((ROOT / "scripts").glob("enforcement_*.pl")):
        (install / "scripts" / helper.name).write_bytes(helper.read_bytes())
    validator = install / "skills/he/scripts/plan_state.py"
    validator.parent.mkdir(parents=True)
    validator.write_text(
        "import os, sys\n"
        "valid = (\n"
        "    'assert-green' in sys.argv\n"
        "    and '--artifact-only' in sys.argv\n"
        "    and '--session-id' not in sys.argv\n"
        "    and '--request-digest' not in sys.argv\n"
        "    and os.environ.get('GREEN_FIXTURE_FAIL') != '1'\n"
        "    and os.environ.get('GREEN_FIXTURE_STALE', '/none/') not in ' '.join(sys.argv)\n"
        ")\n"
        "raise SystemExit(0 if valid else 1)\n",
        encoding="utf-8",
    )
    hijack = green_repo / "skills/he/scripts/plan_state.py"
    hijack.parent.mkdir(parents=True)
    hijack.write_text("raise SystemExit(0)\n", encoding="utf-8")
    (green_repo / "ready.py").write_text("value = 1\n", encoding="utf-8")
    write_evidence(green_repo, green_plan.parent, "one")
    green_command = ["perl", str(install / "scripts/enforcement_policy.pl"), "check", "."]

    def green_run(**extra_env: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, **extra_env}
        return subprocess.run(green_command, cwd=green_repo, capture_output=True, text=True, check=False, env=env)

    exact_green = green_run()
    check("checkpoint accepts an exact green artifact", exact_green.returncode == 0, exact_green.stderr)
    stale_green = green_run(GREEN_FIXTURE_FAIL="1")
    check(
        "checkpoint rejects a stale green artifact",
        stale_green.returncode != 0 and "green repository snapshot no longer matches" in stale_green.stderr,
        stale_green.stderr,
    )
    check(
        "green validation ignores a repository-planted validator",
        stale_green.returncode != 0,
        "repository copy of plan_state.py was executed",
    )
    second_green = plan(green_repo, "two", "green")
    write_evidence(green_repo, second_green.parent, "two")
    one_matches = green_run(GREEN_FIXTURE_STALE="features/two/")
    check("checkpoint accepts two green briefs when one matches", one_matches.returncode == 0, one_matches.stderr)
    none_match = green_run(GREEN_FIXTURE_STALE="features/")
    check(
        "checkpoint rejects two green briefs when neither matches",
        none_match.returncode != 0 and "green repository snapshot no longer matches" in none_match.stderr,
        none_match.stderr,
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
    weak = {name: mode for name, mode in value["rules"].items() if mode not in {"block", "checkpoint check", "advise"}}
    check("coverage has no guidance or unsupported rules", not weak, repr(weak))
    required = {
        "research-evidence",
        "autonomous-explicit-activation",
        "build-verify-loop",
        "direct-live-action-scope",
        "direct-receipt-scope",
        "direct-route-receipt",
        "protected-direct-approval",
        "unwired-repo-advice",
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


def check_protected_direct(root: Path) -> None:
    repo = root / "protected-direct"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    base_env = {key: value for key, value in os.environ.items() if not key.startswith("HARD_ENG_")}
    kind = "data-deletion-or-destructive-schema"
    payload = {
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": "git stash drop stash@{0}", "description": "release entry"},
    }
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=base_env)
    check("planless protected shell denies without authorization", bool(denial(response, "claude")), repr(response))
    approved = authorize_protected_direct(repo, payload, kind, "fixture stash entry")
    check("direct protected authorization records", approved.returncode == 0, approved.stderr)
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=base_env)
    check("approved direct shell action is allowed once", response is None, repr(response))
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=base_env)
    check("direct approval is one-use", bool(denial(response, "claude")), repr(response))
    approved = authorize_protected_direct(repo, payload, kind, "fixture stash entry")
    check("direct re-authorization records", approved.returncode == 0, approved.stderr)
    changed = dict(payload, tool_input={"command": "git stash drop stash@{9}", "description": "release entry"})
    response, _ = run_hook("claude", "pretooluse", changed, env=base_env)
    check("direct approval rejects changed input", bool(denial(response, "claude")), repr(response))
    response, _ = run_hook("claude", "pretooluse", dict(payload), env=base_env)
    check("original input still consumes after a rejected variant", response is None, repr(response))
    approved = authorize_protected_direct(repo, payload, kind, "fixture stash entry")
    check("bare-payload authorization records", approved.returncode == 0, approved.stderr)
    bare = {"cwd": str(repo), "tool_name": "Bash", "tool_input": payload["tool_input"]}
    response, _ = run_hook("claude", "pretooluse", bare, env=base_env, defaults=False)
    check("payload without session or request fields still consumes", response is None, repr(response))
    external = {"cwd": str(repo), "tool_name": "mcp__appwrite__deleteRows", "tool_input": {"table": "users"}}
    response, _ = run_hook("claude", "pretooluse", dict(external), env=base_env)
    check("planless external destructive tool denies", bool(denial(response, "claude")), repr(response))
    approved = authorize_protected_direct(repo, external, kind, "users table")
    check("external direct authorization records", approved.returncode == 0, approved.stderr)
    response, _ = run_hook("claude", "pretooluse", dict(external), env=base_env)
    check("approved external destructive tool is allowed once without a plan", response is None, repr(response))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-hook-") as temporary:
        root = Path(temporary).resolve()
        check_unconfigured(root)
        check_advisory(root)
        check_direct_route(root)
        check_lifecycle(root)
        check_shell_safety(root)
        check_protected_direct(root)
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

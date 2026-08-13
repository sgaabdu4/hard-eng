#!/usr/bin/env python3
"""Behavior checks for the shared agent hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
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
                "enforcement": {"schema_version": 1},
                "families": {"targeted": ["python3", "check.py"]},
                "phases": {"commit": ["targeted"], "push": ["targeted"], "ci": ["targeted"]},
            }
        ),
        encoding="utf-8",
    )


def plan(repo: Path, slug: str, state: str) -> Path:
    folder = repo / "features" / slug
    folder.mkdir(parents=True)
    path = folder / "PLAN.md"
    path.write_text(
        "\n".join(
            (
                "# Feature Brief",
                "<!-- hard-eng-state:v1 -->",
                f"- lifecycle_status = {state}",
                f"- approval_status = {'pending' if state == 'planning' else 'approved'}",
                f"- approval_fingerprint = {'none' if state == 'planning' else 'sha256:' + 'a' * 64}",
                "<!-- /hard-eng-state -->",
                "",
            )
        ),
        encoding="utf-8",
    )
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
    response, _ = run_hook("codex", "pretooluse", edit_payload(repo, source))
    check("building allows source write", response is None, repr(response))

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


def check_hot_path_shape() -> None:
    source = (ROOT / "scripts" / "enforcement_policy.pl").read_text(encoding="utf-8")
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
        root = Path(temporary)
        check_unconfigured(root)
        check_lifecycle(root)
        check_shell_safety(root)
        check_broken_policy_fails_closed(root)
        check_repository_checkpoint(root)
    check_hot_path_shape()
    if FAILURES:
        for failure in FAILURES:
            print(f"agent-hook-contract: FAIL: {failure}", file=sys.stderr)
        return 1
    print("agent-hook-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

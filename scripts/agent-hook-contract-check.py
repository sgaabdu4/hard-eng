#!/usr/bin/env python3
"""Regression contract for the shared agent guard hooks.

Proves the guard blocks what it must, allows what it must, speaks each
runtime's deny dialect, and that the registrars converge without evicting
hook entries owned by anyone else.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts" / "hooks" / "agent-hook.sh"
REGISTRAR = ROOT / "scripts" / "setup" / "agent-hooks.py"
RECEIPTS = ROOT / "receipts" / "agent-hooks.json"
RECEIPT_RUNTIMES = ("claude", "codex", "copilot")
RECEIPT_FIELDS = ("version", "version_command", "command", "observed", "proven_on")
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if not condition:
        FAILURES.append(f"{name}: {detail}" if detail else name)


def run_hook(state: Path, runtime: str, event: str, payload: dict) -> dict | None:
    environment = dict(os.environ, HARD_ENG_HOOK_STATE=str(state))
    result = subprocess.run(
        ["bash", str(HOOK), runtime, event],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )
    if result.returncode != 0:
        FAILURES.append(f"hook exited {result.returncode}: {result.stderr.strip()}")
    out = result.stdout.strip()
    return json.loads(out) if out else None


def denial_reason(response: dict | None, runtime: str) -> str | None:
    if response is None:
        return None
    body = response if runtime == "copilot" else response.get("hookSpecificOutput", {})
    if body.get("permissionDecision") != "deny":
        return None
    return body.get("permissionDecisionReason", "")


def git_fixture(root: Path) -> Path:
    repo = root / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / ".git").mkdir()
    (repo / "src" / "owner.py").write_text("value = 1\n", encoding="utf-8")
    (repo / "src" / "other.py").write_text("value = 2\n", encoding="utf-8")
    (repo / "notes.md").write_text("prose\n", encoding="utf-8")
    return repo


def check_rg_rule(state: Path) -> None:
    for runtime in ("claude", "codex", "copilot"):
        blocked = denial_reason(
            run_hook(
                state,
                runtime,
                "pretooluse",
                {"tool_name": "Bash", "tool_input": {"command": "rg -rn thing src/"}},
            ),
            runtime,
        )
        check(f"rg rule blocks -rn on {runtime}", blocked is not None)
        check(
            f"rg rule explains itself on {runtime}",
            bool(blocked) and "--replace" in blocked,
            repr(blocked),
        )
    allowed = run_hook(
        state,
        "claude",
        "pretooluse",
        {"tool_name": "Bash", "tool_input": {"command": "rg -n thing src/"}},
    )
    check("rg rule allows -n", allowed is None, repr(allowed))
    wrapped = denial_reason(
        run_hook(
            state,
            "claude",
            "pretooluse",
            {"tool_name": "Bash", "tool_input": {"command": "ls && sudo rg -rl thing"}},
        ),
        "claude",
    )
    check("rg rule reads past wrappers and separators", wrapped is not None)
    unrelated = run_hook(
        state,
        "claude",
        "pretooluse",
        {"tool_name": "Bash", "tool_input": {"command": "grep -rn thing src/"}},
    )
    check("rg rule ignores other commands", unrelated is None, repr(unrelated))


def edit_payload(repo: Path, name: str, tool: str = "Edit") -> dict:
    return {
        "session_id": name,
        "cwd": str(repo),
        "tool_name": tool,
        "tool_input": {"file_path": str(repo / "src" / "owner.py")},
    }


def check_impact_rule(state: Path, repo: Path) -> None:
    blocked = denial_reason(
        run_hook(state, "claude", "pretooluse", edit_payload(repo, "fresh")), "claude"
    )
    check("impact rule blocks an uncovered edit", blocked is not None)
    check(
        "impact rule names the unblocking command",
        bool(blocked) and "search_graph" in blocked,
        repr(blocked),
    )

    exempt = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "notes.md")},
        },
    )
    check("impact rule exempts prose", exempt is None, repr(exempt))

    new_file = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo / "src" / "brand-new.py")},
        },
    )
    check("impact rule exempts a file with no callers yet", new_file is None, repr(new_file))

    outside = run_hook(
        state,
        "claude",
        "pretooluse",
        {
            "session_id": "fresh",
            "cwd": str(repo.parent),
            "tool_name": "Write",
            "tool_input": {"file_path": str(repo.parent / "loose.py")},
        },
    )
    check("impact rule ignores files outside a repository", outside is None, repr(outside))


def shell_payload(repo: Path, name: str, command: str) -> dict:
    return {
        "session_id": name,
        "cwd": str(repo),
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def check_shell_write_rule(state: Path, repo: Path) -> None:
    """Denying the edit tool is worthless while the same file is one shell command away."""
    writes = {
        "in-place perl": "perl -0pi -e 's/1/2/' src/owner.py",
        "in-place sed": "sed -i '' 's/1/2/' src/owner.py",
        "truncating redirect": "echo 'def compute(): return 2' > src/owner.py",
        "appending redirect": "printf 'x\\n' >> src/owner.py",
        "tee": "echo x | tee src/owner.py",
        "copy over": "cp /etc/hostname src/owner.py",
        "move over": "mv other.py src/owner.py",
        "inline python write": "python3 -c \"open('src/owner.py','w').write('x')\"",
        "shell heredoc patch": (
            "apply_patch <<'EOF'\n*** Begin Patch\n"
            "*** Update File: src/owner.py\n*** End Patch\nEOF"
        ),
        "absolute path write": f"echo x > {repo / 'src' / 'owner.py'}",
        "write after cd": f"cd {repo} && perl -0pi -e 's/1/2/' src/owner.py",
        "write after relative cd": "cd src && sed -i '' 's/1/2/' owner.py",
    }
    for label, command in writes.items():
        reason = denial_reason(
            run_hook(state, "claude", "pretooluse", shell_payload(repo, "shellfresh", command)),
            "claude",
        )
        check(f"shell write blocked: {label}", reason is not None, command)

    reads = {
        "cat": "cat src/owner.py",
        "rg": "rg -n compute src",
        "diff redirect outside the repo": "cat src/owner.py > /tmp/copy.py",
        "new file redirect": "echo x > src/brand-new.py",
        "prose write": "echo x > notes.md",
        "stderr redirect": "python3 -c 'pass' 2>&1",
        "discarded output": "git status --short > /dev/null",
    }
    for label, command in reads.items():
        allowed = run_hook(
            state, "claude", "pretooluse", shell_payload(repo, "shellfresh", command)
        )
        check(f"shell read allowed: {label}", allowed is None, f"{command} -> {allowed!r}")


def check_clearance(state: Path, repo: Path) -> None:
    # A query answered from an unrelated working directory still clears the file.
    run_hook(
        state,
        "claude",
        "posttooluse",
        {
            "session_id": "cleared",
            "cwd": str(repo.parent),
            "tool_name": "Bash",
            "tool_input": {"command": "codebase-memory-mcp cli search_graph '{}'"},
            "tool_response": '{"stdout":"{\\"file_path\\":\\"src/owner.py\\"}"}',
        },
    )
    allowed = run_hook(state, "claude", "pretooluse", edit_payload(repo, "cleared"))
    check("a map result clears the file it names", allowed is None, repr(allowed))

    still_blocked = denial_reason(
        run_hook(
            state,
            "claude",
            "pretooluse",
            {
                "session_id": "cleared",
                "cwd": str(repo),
                "tool_name": "Edit",
                "tool_input": {"file_path": str(repo / "src" / "other.py")},
            },
        ),
        "claude",
    )
    check("clearance does not spread to unnamed files", still_blocked is not None)

    stale = state / "expired.json"
    stale.parent.mkdir(parents=True, exist_ok=True)
    stale.write_text(
        json.dumps({"cleared": {"src/owner.py": time.time() - 24 * 60 * 60}}),
        encoding="utf-8",
    )
    expired = denial_reason(
        run_hook(state, "claude", "pretooluse", edit_payload(repo, "expired")), "claude"
    )
    check("clearance expires", expired is not None)


def check_dialects(state: Path, repo: Path) -> None:
    claude = run_hook(state, "claude", "pretooluse", edit_payload(repo, "dialect"))
    check(
        "Claude denial is wrapped in hookSpecificOutput",
        isinstance(claude, dict) and "hookSpecificOutput" in claude,
        repr(claude),
    )
    copilot = run_hook(
        state,
        "copilot",
        "pretooluse",
        {
            "sessionId": "dialect",
            "cwd": str(repo),
            "toolName": "str_replace",
            "toolArgs": {"path": "src/owner.py"},
        },
    )
    check(
        "Copilot denial is flat",
        isinstance(copilot, dict) and copilot.get("permissionDecision") == "deny",
        repr(copilot),
    )
    # Copilot encodes arguments as a string: JSON for most tools, and the bare
    # patch body for apply_patch.
    encoded = run_hook(
        state,
        "copilot",
        "pretooluse",
        {
            "sessionId": "dialect",
            "cwd": str(repo),
            "toolName": "str_replace",
            "toolArgs": json.dumps({"path": str(repo / "src" / "owner.py")}),
        },
    )
    check("Copilot string arguments are decoded", encoded is not None, repr(encoded))
    patch_body = run_hook(
        state,
        "copilot",
        "pretooluse",
        {
            "sessionId": "dialect",
            "cwd": str(repo),
            "toolName": "apply_patch",
            "toolArgs": (
                f"*** Begin Patch\n*** Update File: {repo / 'src' / 'owner.py'}\n*** End Patch\n"
            ),
        },
    )
    check("Copilot bare patch bodies are read", patch_body is not None, repr(patch_body))

    codex = run_hook(
        state,
        "codex",
        "pretooluse",
        {
            "session_id": "dialect",
            "cwd": str(repo),
            "tool_name": "apply_patch",
            "tool_input": {"input": "*** Begin Patch\n*** Update File: src/owner.py\n"},
        },
    )
    check("Codex apply_patch targets are read from the patch body", codex is not None)


def check_resilience(state: Path) -> None:
    for payload in ("not json", "[]", ""):
        result = subprocess.run(
            ["bash", str(HOOK), "claude", "pretooluse"],
            input=payload,
            capture_output=True,
            text=True,
            env=dict(os.environ, HARD_ENG_HOOK_STATE=str(state)),
            timeout=30,
        )
        check(
            f"unusable input {payload!r} allows the call",
            result.returncode == 0 and not result.stdout.strip(),
            result.stdout.strip() or result.stderr.strip(),
        )


def registrar(path: Path, runtime: str, mode: str) -> int:
    return subprocess.run(
        [sys.executable, str(REGISTRAR), runtime, mode],
        capture_output=True,
        text=True,
        env=dict(
            os.environ,
            HARD_ENG_HOOK_COMMAND='bash "/canonical/agent-hook.sh"',
            CODEX_HOOKS=str(path),
            COPILOT_HOOKS=str(path),
        ),
        timeout=30,
    ).returncode


def check_registrars(root: Path) -> None:
    codex = root / "codex-hooks.json"
    foreign = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "bash other.sh session"}]}
            ]
        }
    }
    codex.write_text(json.dumps(foreign), encoding="utf-8")
    check("Codex drift is reported", registrar(codex, "codex", "check") == 5)
    check("Codex converges", registrar(codex, "codex", "install") == 0)
    converged = json.loads(codex.read_text(encoding="utf-8"))
    check(
        "Codex keeps hook entries owned by others",
        converged["hooks"]["SessionStart"] == foreign["hooks"]["SessionStart"],
        json.dumps(converged["hooks"].get("SessionStart")),
    )
    for event in ("PreToolUse", "PostToolUse"):
        check(f"Codex registers {event}", len(converged["hooks"].get(event, [])) == 1)
    check("Codex convergence is idempotent", registrar(codex, "codex", "check") == 0)
    check("Codex install is idempotent", registrar(codex, "codex", "install") == 0)
    check(
        "Codex does not stack duplicates",
        len(json.loads(codex.read_text(encoding="utf-8"))["hooks"]["PreToolUse"]) == 1,
    )

    codex_hook = converged["hooks"]["PreToolUse"][0]["hooks"][0]
    check(
        "Codex names its command and timeout keys",
        codex_hook.get("timeout") == 10 and "agent-hook.sh" in codex_hook.get("command", ""),
        json.dumps(codex_hook),
    )

    copilot = root / "copilot-hooks.json"
    # A hook written under Claude's key names is invisible to Copilot, so a
    # stale entry in that shape must be replaced, not kept alongside.
    copilot.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    "preToolUse": [
                        {
                            "type": "command",
                            "command": 'bash "/canonical/agent-hook.sh" copilot pretooluse',
                            "timeout": 10,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )
    check("Copilot converges", registrar(copilot, "copilot", "install") == 0)
    written = json.loads(copilot.read_text(encoding="utf-8"))
    check("Copilot declares its schema version", written.get("version") == 1)
    check(
        "Copilot uses camelCase events",
        {"preToolUse", "postToolUse"} <= set(written.get("hooks", {})),
        json.dumps(list(written.get("hooks", {}))),
    )
    for event in ("preToolUse", "postToolUse"):
        entries = written["hooks"][event]
        check(f"Copilot registers one {event} hook", len(entries) == 1, json.dumps(entries))
        hook = entries[0] if entries else {}
        check(
            f"Copilot {event} runs the guard under the bash key",
            "agent-hook.sh" in hook.get("bash", ""),
            json.dumps(hook),
        )
        check(
            f"Copilot {event} states its timeout in seconds",
            hook.get("timeoutSec") == 10 and "timeout" not in hook,
            json.dumps(hook),
        )
        check(
            f"Copilot {event} drops the key Copilot ignores",
            "command" not in hook,
            json.dumps(hook),
        )
    check("Copilot convergence is idempotent", registrar(copilot, "copilot", "check") == 0)


def installed_version(argv: list[str]) -> str | None:
    """First line the runtime itself prints, or None when it is not installed."""
    if shutil.which(argv[0]) is None:
        return None
    # These runtimes fork helpers that outlive the version print, so the probe
    # owns a process group it can reap; a stray descendant fails the bounded runner.
    try:
        process = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
    except OSError:
        return ""
    try:
        out, err = process.communicate(timeout=60)
    except subprocess.TimeoutExpired:
        out, err = "", ""
    finally:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
        process.wait()
    output = (out or err).strip().splitlines()
    return output[0].strip() if output else ""


def check_receipts() -> None:
    """Every runtime the guard claims to block must name the version it was proven on.

    The contract check below only proves the guard's own logic; whether a
    third-party runtime honours a deny is that runtime's behaviour, and it
    changes between releases. A receipt older than the installed release is
    an unproven claim, so it fails here until someone runs the guard live again.
    """
    try:
        receipts = json.loads(RECEIPTS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        FAILURES.append(f"live-run receipts are unreadable: {RECEIPTS}: {error}")
        return
    if not isinstance(receipts, dict):
        FAILURES.append(f"live-run receipts are not a JSON object: {RECEIPTS}")
        return
    for runtime in RECEIPT_RUNTIMES:
        receipt = receipts.get(runtime)
        if not isinstance(receipt, dict):
            FAILURES.append(f"{runtime} has no live-run receipt in {RECEIPTS}")
            continue
        missing = [
            field
            for field in RECEIPT_FIELDS
            if not str(receipt.get(field) or "").strip()
            and not isinstance(receipt.get(field), list)
        ]
        if missing:
            FAILURES.append(f"{runtime} receipt is missing: {', '.join(missing)}")
            continue
        argv = receipt["version_command"]
        if not isinstance(argv, list) or not argv:
            FAILURES.append(f"{runtime} receipt has no version command")
            continue
        found = installed_version([str(item) for item in argv])
        if found is None:
            print(f"agent-hook-contract: NOTE: {runtime} is not installed; receipt not rechecked")
            continue
        if found != receipt["version"]:
            FAILURES.append(
                f"{runtime} guard proof is stale: proven against {receipt['version']!r}, "
                f"installed {found!r}. Run the guard live against the installed release "
                f"and record what it did in {RECEIPTS}."
            )


def main() -> int:
    if not HOOK.exists() or not os.access(HOOK, os.X_OK):
        print(f"agent-hook-contract: FAIL: guard hook is not executable: {HOOK}")
        return 1
    with tempfile.TemporaryDirectory() as name:
        root = Path(name)
        repo = git_fixture(root)
        state = root / "state"
        check_rg_rule(state)
        check_impact_rule(state, repo)
        check_shell_write_rule(state, repo)
        check_clearance(state, repo)
        check_dialects(state, repo)
        check_resilience(state)
        check_registrars(root)
    check_receipts()
    if FAILURES:
        for failure in FAILURES:
            print(f"agent-hook-contract: FAIL: {failure}")
        return 1
    print("agent-hook-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

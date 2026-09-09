#!/usr/bin/env python3
"""Run native gate commands and handle the three agreed hook events."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    config = json.loads((ROOT / "hard-eng.gates.json").read_text())
    groups = [*config["packages"], {"path": ".", "checks": config["shared"]}]
    failed = False
    for group in groups:
        for gate in group["checks"]:
            print(f"CHECK {group['path']}/{gate['name']}", flush=True)
            try:
                result = subprocess.run(gate["command"], cwd=ROOT / group["path"], check=False, timeout=600)
                failed |= result.returncode != 0
            except (OSError, subprocess.TimeoutExpired) as error:
                print(f"FAIL {gate['name']}: {error}")
                failed = True
    return int(failed)


def pre_push():
    for line in sys.stdin:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("Invalid pre-push input")
        revision = fields[1]
        if set(revision) == {"0"}:
            continue
        with tempfile.TemporaryDirectory(prefix="hard-eng-push-") as temporary:
            checkout = Path(temporary) / "project"
            subprocess.run(["git", "worktree", "add", "--detach", str(checkout), revision], cwd=ROOT, check=True)
            try:
                result = subprocess.run([sys.executable, str(checkout / ".hooks/hard-eng.py"), "check"], cwd=checkout, check=False)
                if result.returncode:
                    return result.returncode
            finally:
                subprocess.run(["git", "worktree", "remove", "--force", str(checkout)], cwd=ROOT, check=True)
    return 0


def agent_hook(event, agent):
    payload = json.load(sys.stdin)
    if event == "stop" and payload.get("stop_hook_active"):
        print(json.dumps({"systemMessage": "Report any remaining verification blocker honestly; do not claim success."}))
        return 0
    if event == "session":
        messages = []
        for name in ("context-mode", "codebase-memory-mcp"):
            try:
                subprocess.run(["npx", "--yes", f"{name}@latest", "--version"], cwd=ROOT,
                               capture_output=True, text=True, check=True, timeout=60)
            except (OSError, subprocess.SubprocessError):
                messages.append(f"{name} unavailable; continue with available tools.")
        message = " ".join(messages) or "Hard Eng plugin commands are available."
        output = {"additionalContext": message} if agent == "copilot" else {
            "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": message}}
    else:
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "check"], cwd=ROOT,
                                capture_output=True, text=True, check=False)
        output = {"decision": "block", "reason": "Repair the gates or verification command before claiming completion. Questions and honest blocked reports remain possible.\n" + result.stdout + result.stderr} if result.returncode else {}
    print(json.dumps(output))
    return 0


def main():
    command = "pre-push" if Path(sys.argv[0]).name == "pre-push" else sys.argv[1]
    if command == "check":
        return check()
    if command == "pre-push":
        return pre_push()
    return agent_hook(command, sys.argv[2])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print(f"Hard Eng: {error}", file=sys.stderr)
        raise SystemExit(1) from error

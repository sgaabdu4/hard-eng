"""Prove the guard that stops a write from changing settings outside this repository."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts/hooks/agent-hook.sh"
FIXTURES = ROOT / "scripts/test_fixtures/agent-hooks"
REQUEST_DIGEST = "sha256:" + "d" * 64

FAILURES: list[str] = []


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def denial(command: str) -> str:
    payload = {
        "tool_name": "bash",
        "tool_input": {"command": command},
        "cwd": str(ROOT),
        "session_id": "machine-scope-contract",
        "request_digest": REQUEST_DIGEST,
    }
    result = subprocess.run(
        ["bash", str(HOOK), "codex", "pretooluse"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    if result.returncode != 0:
        FAILURES.append(f"hook crashed on {command!r}: {result.stderr.strip()}")
        return ""
    if not result.stdout.strip():
        return ""
    body = json.loads(result.stdout).get("hookSpecificOutput", {})
    if body.get("permissionDecision") != "deny":
        return ""
    return str(body.get("permissionDecisionReason", ""))


CASES: list[tuple[str, str | None]] = [
    (fixture("global-mcp-add-blocked.json")["command"], "machine-wide"),
    (fixture("project-mcp-read-allowed.json")["command"], None),
    ("printf x >> ~/.codex/config.toml", "home directory"),
    ('printf x >> "$HOME/.npmrc"', "home directory"),
    ("git config --global user.name x", "machine-wide"),
    ("git config --global --get core.hooksPath", None),
    ("git config --global --list", None),
    ("git config --global --get-regexp alias", None),
    ("git config get --global core.hooksPath", None),
    ("git config --global --unset user.name", "machine-wide"),
    ("git config --global --get x || git config --global user.name y", "machine-wide"),
    ("defaults write com.example key -bool true", "machine-wide"),
    ("git config user.name x", None),
    ("printf x >> ./notes.txt", None),
    ("npm config set registry https://r --location project", None),
    ('printf \'{"c":"codex mcp add y"}\' > fixture.json', None),
]


def main() -> int:
    for command, expected in CASES:
        reason = denial(command)
        if expected is None and reason:
            FAILURES.append(f"blocked an allowed command {command!r}: {reason}")
        elif expected is not None and expected not in reason:
            FAILURES.append(f"failed to block {command!r}: {reason or 'allowed'}")
    if FAILURES:
        for failure in FAILURES:
            print(f"machine-scope-guard: FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"machine-scope-guard: PASS ({len(CASES)} cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

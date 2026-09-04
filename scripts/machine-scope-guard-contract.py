"""Prove the guard that stops a write from changing settings outside this repository."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from agent_hook_contract_lib import git_env, manifest, start_direct

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "scripts/hooks/agent-hook.sh"
FIXTURES = ROOT / "scripts/test_fixtures/agent-hooks"
FAILURES: list[str] = []


def fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def denial(command: str) -> str:
    payload = {
        "tool_name": "bash",
        "tool_input": {"command": command},
        "cwd": str(ROOT),
        "session_id": "machine-scope-contract",
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


def write_denial(repo: Path, target: Path) -> str | None:
    payload = {
        "session_id": "cross-repo-write",
        "cwd": str(repo),
        "tool_name": "Write",
        "tool_input": {"file_path": str(target)},
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
        FAILURES.append(f"hook crashed on write to {target}: {result.stderr.strip()}")
        return None
    if not result.stdout.strip():
        return ""
    body = json.loads(result.stdout).get("hookSpecificOutput", {})
    if body.get("permissionDecision") != "deny":
        return ""
    return str(body.get("permissionDecisionReason", ""))


def check_cross_repo_write(root: Path) -> None:
    """A Direct-routed write into another repository needs no protected receipt; a home-directory write still does."""
    repo = root / "cross-repo-write"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    started = start_direct(repo, "note.txt")
    if started.returncode != 0:
        FAILURES.append(f"cross-repo write case: direct receipt did not record: {started.stderr}")
        return
    reason = write_denial(repo, ROOT / "machine-scope-guard-probe.txt")
    if reason:
        FAILURES.append(f"write into another repository's working tree was blocked: {reason}")
    reason = write_denial(repo, Path.home() / ".hard-eng-guard-probe" / "settings.json")
    if reason is not None and "outside every repository" not in reason:
        FAILURES.append(f"home-directory write was not blocked as machine scope: {reason or 'allowed'}")


def check_lifecycle_media_scope(root: Path) -> None:
    """Lifecycle evidence (e2e visual receipts, ux references) is evidence, not a machine setting."""
    repo = root / "lifecycle-media-write"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    started = start_direct(repo, "note.txt")
    if started.returncode != 0:
        FAILURES.append(f"lifecycle-media case: direct receipt did not record: {started.stderr}")
        return
    lifecycle_target = (
        Path.home() / ".claude" / "lifecycle-media" / "sample-plan" / "step.visual-review.json"
    )
    reason = write_denial(repo, lifecycle_target)
    if reason:
        FAILURES.append(f"lifecycle-media write was blocked as machine scope: {reason}")
    settings_target = Path.home() / ".claude" / "settings.json"
    reason = write_denial(repo, settings_target)
    if reason is not None and "outside every repository" not in reason:
        FAILURES.append(f"settings.json write was not blocked as machine scope: {reason or 'allowed'}")


def main() -> int:
    for command, expected in CASES:
        reason = denial(command)
        if expected is None and reason:
            FAILURES.append(f"blocked an allowed command {command!r}: {reason}")
        elif expected is not None and expected not in reason:
            FAILURES.append(f"failed to block {command!r}: {reason or 'allowed'}")
    with tempfile.TemporaryDirectory(prefix="machine-scope-guard-") as temporary:
        check_cross_repo_write(Path(temporary).resolve())
    with tempfile.TemporaryDirectory(prefix="machine-scope-guard-lifecycle-") as temporary:
        check_lifecycle_media_scope(Path(temporary).resolve())
    if FAILURES:
        for failure in FAILURES:
            print(f"machine-scope-guard: FAIL: {failure}", file=sys.stderr)
        return 1
    print(f"machine-scope-guard: PASS ({len(CASES)} shell cases + cross-repo write)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

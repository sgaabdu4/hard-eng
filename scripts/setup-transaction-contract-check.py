#!/usr/bin/env python3
"""Failure-injection checks for cross-stage setup rollback."""

from __future__ import annotations

import os
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import NoReturn


ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-transaction-contract: FAIL: {message}")


def run_claude(home: Path, *, concurrent_edit: bool) -> subprocess.CompletedProcess[str]:
    check = "return 1"
    if concurrent_edit:
        check = """printf '%s\\n' '{"user":true}' >"$CLAUDE_SETTINGS_FILE"; return 1"""
    body = f"""
set -u
ROOT={shlex.quote(str(ROOT))}
. "$ROOT/scripts/setup/common.sh"
CANONICAL_AGENTS="$HOME/.agents/AGENTS.md"
. "$ROOT/scripts/setup/claude.sh"
load_context_contract() {{
  CONTEXT_MARKETPLACE_NAME=context-mode
  CONTEXT_MARKETPLACE_REPO=openai/context-mode
  CONTEXT_MARKETPLACE_REF=v1.0.0
  CONTEXT_PLUGIN_ID=context-mode@context-mode
}}
check_claude_integration() {{ {check}; }}
install_claude_integration
"""
    environment = {**os.environ, "HOME": str(home), "TMPDIR": str(home / "tmp")}
    return subprocess.run(
        ["bash", "-c", body],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
        env=environment,
    )


def prepare_claude(home: Path) -> tuple[Path, Path]:
    (home / "tmp").mkdir()
    (home / ".agents").symlink_to(ROOT, target_is_directory=True)
    claude = home / ".claude"
    hooks = claude / "hooks"
    hooks.mkdir(parents=True)
    legacy = hooks / "rg-guard.py"
    legacy.symlink_to("/reviewed/claude-rg-guard.py")
    settings = claude / "settings.json"
    settings.write_text('{"unrelated":{"keep":true}}\n', encoding="utf-8")
    settings.chmod(0o640)
    return settings, legacy


def assert_other_claude_state_rolled_back(home: Path, legacy: Path) -> None:
    claude = home / ".claude"
    if (claude / "CLAUDE.md").exists() or (claude / "CLAUDE.md").is_symlink():
        fail("Claude rollback left a new memory stub")
    for name in ("skills", "output-styles"):
        path = claude / name
        if path.exists() or path.is_symlink():
            fail(f"Claude rollback left a new {name} link")
    if not legacy.is_symlink() or os.readlink(legacy) != "/reviewed/claude-rg-guard.py":
        fail("Claude rollback did not restore the exact legacy hook link")


def check_claude_rollback() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-claude-transaction-") as temporary:
        home = Path(temporary)
        settings, legacy = prepare_claude(home)
        before = settings.read_bytes(), settings.stat().st_mode & 0o777
        result = run_claude(home, concurrent_edit=False)
        if result.returncode == 0:
            fail("injected Claude final-check failure was accepted")
        after = settings.read_bytes(), settings.stat().st_mode & 0o777
        if after != before:
            fail("Claude transaction did not restore settings bytes and mode")
        assert_other_claude_state_rolled_back(home, legacy)


def check_claude_concurrent_edit() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-claude-concurrent-") as temporary:
        home = Path(temporary)
        settings, legacy = prepare_claude(home)
        result = run_claude(home, concurrent_edit=True)
        if result.returncode == 0:
            fail("Claude rollback accepted a concurrent settings edit")
        if settings.read_text(encoding="utf-8") != '{"user":true}\n':
            fail("Claude rollback overwrote a concurrent settings edit")
        if "rollback incomplete" not in result.stderr:
            fail("Claude concurrent-edit rollback did not report manual recovery")
        assert_other_claude_state_rolled_back(home, legacy)


def main() -> int:
    check_claude_rollback()
    check_claude_concurrent_edit()
    print("setup-transaction-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

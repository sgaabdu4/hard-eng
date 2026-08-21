#!/usr/bin/env python3
"""Behavior checks for the shared setup JSON writer."""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
SETUP = ROOT / "scripts/setup"
sys.path.insert(0, str(ROOT))
from scripts.setup import safe_file


def fail(message: str) -> NoReturn:
    raise SystemExit(f"setup-safe-writer-contract: FAIL: {message}")


def run(
    script: str, runtime: str, path: Path, mode: str = "install", **values: str
) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "CODEX_HOOKS": str(path),
        "COPILOT_HOOKS": str(path),
        "CLAUDE_SETTINGS": str(path),
        "HARD_ENG_HOOK_COMMAND": 'bash "/Users/abid/.agents/scripts/hooks/agent-hook.sh"',
        "CONTEXT_MARKETPLACE_NAME": "context-mode",
        "CONTEXT_MARKETPLACE_REPO": "openai/context-mode",
        "CONTEXT_MARKETPLACE_REF": "v1.0.0",
        "CONTEXT_PLUGIN_ID": "context-mode@context-mode",
        **values,
    }
    argv = [sys.executable, str(SETUP / script)]
    if script == "agent-hooks.py":
        argv += [runtime, mode]
    else:
        argv += [mode]
    return subprocess.run(argv, env=environment, capture_output=True, text=True, timeout=10, check=False)


def check_json_preservation() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-writer-") as directory:
        root = Path(directory).resolve()
        settings = root / "claude/settings.json"
        settings.parent.mkdir(parents=True)
        original = {"unrelated": {"keep": True}, "includeCoAuthoredBy": True}
        settings.write_text(json.dumps(original) + "\n", encoding="utf-8")
        settings.chmod(0o640)
        result = run("claude-settings.py", "claude", settings)
        if result.returncode:
            fail(result.stderr.strip())
        updated = json.loads(settings.read_text(encoding="utf-8"))
        if updated["unrelated"] != original["unrelated"]:
            fail("Claude writer removed an unrelated JSON key")
        if settings.stat().st_mode & 0o777 != 0o640:
            fail("Claude writer changed the existing file mode")
        if run("claude-settings.py", "claude", settings, mode="check").returncode:
            fail("Claude writer check rejected its own output")

        hooks = root / "codex/hooks.json"
        hooks.parent.mkdir(parents=True)
        hooks.write_text(json.dumps({"unrelated": [1, 2]}) + "\n", encoding="utf-8")
        hooks.chmod(0o640)
        result = run("agent-hooks.py", "codex", hooks)
        if result.returncode:
            fail(result.stderr.strip())
        if json.loads(hooks.read_text(encoding="utf-8"))["unrelated"] != [1, 2]:
            fail("agent hook writer removed an unrelated JSON key")
        if hooks.stat().st_mode & 0o777 != 0o640:
            fail("agent hook writer changed the existing file mode")


def check_structural_marker() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-marker-") as directory:
        path = Path(directory).resolve() / "hooks.json"
        path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "hooks": [
                                    {"type": "command", "command": "echo agent-hook.sh.bak"},
                                    {"type": "command", "command": "bash /repo/agent-hook.sh"},
                                ]
                            }
                        ]
                    }
                }
            ),
            encoding="utf-8",
        )
        result = run("agent-hooks.py", "codex", path)
        if result.returncode:
            fail(result.stderr.strip())
        text = path.read_text(encoding="utf-8")
        if "agent-hook.sh.bak" not in text or "bash /repo/agent-hook.sh" in text:
            fail("hook ownership used a substring instead of a command token")


def check_no_follow() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-links-") as directory:
        root = Path(directory).resolve()
        outside = root / "outside.json"
        outside.write_text('{"outside": true}\n', encoding="utf-8")
        final = root / "final.json"
        final.symlink_to(outside)
        result = run("claude-settings.py", "claude", final)
        if result.returncode == 0 or outside.read_text(encoding="utf-8") != '{"outside": true}\n':
            fail("final symlink was followed by the settings writer")
        real_parent = root / "real"
        real_parent.mkdir()
        link_parent = root / "link"
        link_parent.symlink_to(real_parent, target_is_directory=True)
        result = run("agent-hooks.py", "codex", link_parent / "hooks.json")
        if result.returncode == 0:
            fail("intermediate symlink was followed by the hook writer")

        unsafe_parent = root / "unsafe"
        unsafe_parent.mkdir(mode=0o777)
        unsafe_parent.chmod(0o777)
        result = run("claude-settings.py", "claude", unsafe_parent / "settings.json")
        if result.returncode == 0:
            fail("group-writable intermediate directory was accepted")

        unsafe_file = root / "unsafe.json"
        unsafe_file.write_text("{}\n", encoding="utf-8")
        unsafe_file.chmod(0o666)
        result = run("claude-settings.py", "claude", unsafe_file)
        if result.returncode == 0 or unsafe_file.read_text(encoding="utf-8") != "{}\n":
            fail("group-writable final file was accepted")


def check_hostile_temp() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-temp-") as directory:
        root = Path(directory).resolve()
        target = root / "state.json"
        hostile = root / ".hard-eng-fixed"
        hostile.write_bytes(b"do not replace")
        original = safe_file.secrets.token_hex
        safe_file.secrets.token_hex = lambda _length: "fixed"
        try:
            try:
                safe_file.create_path(target, b"new", 0o600)
            except safe_file.SafeFileError:
                pass
            else:
                fail("precreated temporary file was overwritten")
        finally:
            safe_file.secrets.token_hex = original
        if hostile.read_bytes() != b"do not replace" or target.exists():
            fail("hostile temporary-file handling changed state")


def check_directory_lock() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-lock-") as directory:
        first = os.open(directory, os.O_RDONLY)
        second = os.open(directory, os.O_RDONLY)
        try:
            fcntl.flock(first, fcntl.LOCK_EX)
            try:
                fcntl.flock(second, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                pass
            else:
                fail("parent directory lock did not exclude a second writer")
        finally:
            fcntl.flock(first, fcntl.LOCK_UN)
            os.close(second)
            os.close(first)


def check_hostile_consume_claim() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-consume-") as directory:
        root = Path(directory).resolve()
        target = root / "state.json"
        hostile = root / ".hard-eng-consumed-fixed"
        target.write_bytes(b"old")
        target.chmod(0o600)
        hostile.write_bytes(b"hostile")
        original = safe_file.secrets.token_hex
        safe_file.secrets.token_hex = lambda _length: "fixed"
        try:
            try:
                safe_file.consume_if_unchanged(root, Path(target.name), b"old", 0o600)
            except safe_file.SafeFileError:
                pass
            else:
                fail("precreated consume claim was overwritten")
        finally:
            safe_file.secrets.token_hex = original
        if target.read_bytes() != b"old" or hostile.read_bytes() != b"hostile":
            fail("hostile consume claim changed state")


def check_concurrent_cas() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-cas-") as directory:
        target = Path(directory).resolve() / "state.json"
        safe_file.create_path(target, b"old", 0o600)
        expected, mode = safe_file.read_snapshot(target.parent, Path(target.name))
        gate = threading.Barrier(2)
        results: list[object] = []

        def writer(data: bytes) -> None:
            gate.wait()
            try:
                safe_file.replace_path_if_unchanged(target, expected, mode, data)
            except Exception as error:  # one writer must lose the exact preimage race
                results.append(error)
            else:
                results.append(None)

        threads = [threading.Thread(target=writer, args=(data,)) for data in (b"one", b"two")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        if any(thread.is_alive() for thread in threads) or results.count(None) != 1:
            fail("concurrent writers did not produce exactly one winner")
        if target.read_bytes() not in {b"one", b"two"}:
            fail("concurrent writer left a partial file")
        if tuple(target.parent.glob(".hard-eng-*")):
            fail("concurrent writer leaked a temporary file")


def check_safe_file_cli() -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-safe-cli-") as directory:
        root = Path(directory).resolve()
        target = root / "state/receipt.txt"
        command = [sys.executable, str(SETUP / "safe-file-cli.py"), "--path", str(target), "--mode", "600"]
        created = subprocess.run(command, input=b"first\n", capture_output=True, timeout=10, check=False)
        replaced = subprocess.run(command, input=b"second\n", capture_output=True, timeout=10, check=False)
        if created.returncode or replaced.returncode:
            fail("safe-file CLI could not create and replace managed state")
        if target.read_bytes() != b"second\n" or target.stat().st_mode & 0o777 != 0o600:
            fail("safe-file CLI changed bytes or mode during publication")
        if tuple(target.parent.glob(".hard-eng-*")):
            fail("safe-file CLI leaked a temporary file")
        outside = root / "outside.txt"
        outside.write_bytes(b"outside")
        linked = root / "linked.txt"
        linked.symlink_to(outside)
        hostile = subprocess.run(
            [*command[:3], str(linked), *command[4:]],
            input=b"replacement",
            capture_output=True,
            timeout=10,
            check=False,
        )
        if hostile.returncode == 0 or outside.read_bytes() != b"outside":
            fail("safe-file CLI followed a hostile final symlink")


def main() -> int:
    check_json_preservation()
    check_structural_marker()
    check_no_follow()
    check_hostile_temp()
    check_directory_lock()
    check_hostile_consume_claim()
    check_concurrent_cas()
    check_safe_file_cli()
    print("setup-safe-writer-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

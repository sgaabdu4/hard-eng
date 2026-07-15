#!/usr/bin/env python3
"""Regression checks for bounded command ownership and cleanup."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "skills/deterministic-checks/scripts/bounded_run.py"


def fail(message: str) -> None:
    raise SystemExit(f"bounded-run-regressions: {message}")


def alive(pid: int) -> bool:
    result = subprocess.run(
        ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False
    )
    return result.returncode == 0 and bool(result.stdout.strip()) and not result.stdout.lstrip().startswith("Z")


def require_gone(pid: int, label: str) -> None:
    deadline = time.monotonic() + 3
    while alive(pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    if alive(pid):
        fail(f"{label} survived owner exit: pid={pid}")


def child_command(pid_path: Path, *, parent_wait: float) -> list[str]:
    source = (
        "import pathlib,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
        f"time.sleep({parent_wait})"
    )
    return [sys.executable, "-c", source, str(pid_path)]


def wait_pid(path: Path) -> int:
    deadline = time.monotonic() + 3
    while not path.is_file() and time.monotonic() < deadline:
        time.sleep(0.02)
    if not path.is_file():
        fail("fixture did not expose descendant pid")
    return int(path.read_text(encoding="utf-8"))


def check_timeout(root: Path) -> None:
    pid_path = root / "timeout.pid"
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "0.2", "--grace", "0.1", "--", *child_command(pid_path, parent_wait=60)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 124 or "TIMEOUT" not in result.stderr:
        fail("deadline did not fail explicitly with exit 124")
    require_gone(wait_pid(pid_path), "timed-out descendant")


def check_completed_parent(root: Path) -> None:
    pid_path = root / "completed.pid"
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "5", "--grace", "0.1", "--", *child_command(pid_path, parent_wait=0.05)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 125 or "BACKGROUND" not in result.stderr:
        fail("background descendant did not fail the command explicitly")
    require_gone(wait_pid(pid_path), "background descendant")


def check_terminal_loss(root: Path) -> None:
    pid_path = root / "hangup.pid"
    owner = subprocess.Popen(
        [sys.executable, str(RUNNER), "--timeout", "60", "--grace", "0.1", "--", *child_command(pid_path, parent_wait=60)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    descendant = wait_pid(pid_path)
    owner.send_signal(signal.SIGHUP)
    if owner.wait(timeout=3) != 128 + signal.SIGHUP:
        fail("terminal hangup status was not preserved")
    require_gone(descendant, "hangup descendant")


def check_status() -> None:
    result = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "2", "--", sys.executable, "-c", "raise SystemExit(7)"],
        check=False,
    )
    if result.returncode != 7:
        fail("child failure status was not preserved")


def check_wiring() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/deterministic-checks/SKILL.md").read_text(encoding="utf-8")
    if "$deterministic-checks` bounded runner + explicit whole-run timeout" not in agents:
        fail("global project-command route is missing")
    for anchor in ("bounded_run.py", "TERM → grace → KILL", "raw unbounded project command = `FAIL`"):
        if anchor not in skill:
            fail(f"deterministic-checks contract missing: {anchor}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bounded-run-") as temporary:
        root = Path(temporary)
        check_timeout(root)
        check_completed_parent(root)
        check_terminal_loss(root)
    check_status()
    check_wiring()
    print("bounded-run-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

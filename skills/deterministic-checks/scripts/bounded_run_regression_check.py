#!/usr/bin/env python3
"""Regression checks for bounded command ownership and cleanup."""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[3]
RUNNER = ROOT / "skills/deterministic-checks/scripts/bounded_run.py"
sys.path.insert(0, str(RUNNER.parent))
from bounded_run import CAPTURE_LIMIT_BYTES, INPUT_LIMIT_BYTES, OUTPUT_LIMIT_EXIT, run_captured


def fail(message: str) -> NoReturn:
    raise SystemExit(f"bounded-run-regressions: {message}")


def alive(pid: int) -> bool:
    result = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True, check=False)
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


def stubborn_child_command(pid_path: Path) -> list[str]:
    source = (
        "import pathlib,signal,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c',"
        "'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
        "time.sleep(60)']);"
        "pathlib.Path(sys.argv[1]).write_text(str(p.pid));"
        "time.sleep(60)"
    )
    return [sys.executable, "-c", source, str(pid_path)]


def receipt_args(root: Path, name: str) -> tuple[list[str], Path, str]:
    path = (root / f"{name}.receipt.json").resolve()
    token = name.encode().hex().ljust(64, "0")[:64]
    return ["--terminal-receipt", str(path), "--terminal-token", token], path, token


def require_receipt(path: Path, token: str, label: str) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        fail(f"{label} lacks a valid terminal receipt: {error}")
    if payload != {"terminal": True, "token": token}:
        fail(f"{label} emitted an invalid terminal receipt")


def wait_pid(path: Path) -> int:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return int(value)
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(0.02)
    fail("fixture did not expose a complete descendant pid")


def check_pid_readiness(root: Path) -> None:
    pid_path = root / "delayed.pid"
    pid_path.write_text("", encoding="utf-8")
    writer = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import pathlib,sys,time; time.sleep(0.1); pathlib.Path(sys.argv[1]).write_text('123')",
            str(pid_path),
        ]
    )
    if wait_pid(pid_path) != 123:
        fail("partial pid readiness was accepted")
    if writer.wait(timeout=2):
        fail("pid readiness writer failed")


def check_timeout(root: Path) -> None:
    pid_path = root / "timeout.pid"
    receipt, receipt_path, token = receipt_args(root, "timeout")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "1",
            "--grace",
            "0.1",
            *receipt,
            "--",
            *stubborn_child_command(pid_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 124 or "TIMEOUT" not in result.stderr:
        fail("deadline did not fail explicitly with exit 124")
    require_gone(wait_pid(pid_path), "timed-out descendant")
    require_receipt(receipt_path, token, "timed-out command")


def check_completed_parent(root: Path) -> None:
    pid_path = root / "completed.pid"
    receipt, receipt_path, token = receipt_args(root, "completed")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "5",
            "--grace",
            "0.1",
            *receipt,
            "--",
            *child_command(pid_path, parent_wait=0.05),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 125 or "BACKGROUND" not in result.stderr:
        fail("background descendant did not fail the command explicitly")
    require_gone(wait_pid(pid_path), "background descendant")
    require_receipt(receipt_path, token, "background-descendant command")


def check_terminal_loss(root: Path) -> None:
    pid_path = root / "hangup.pid"
    receipt, receipt_path, token = receipt_args(root, "hangup")
    owner = subprocess.Popen(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "60",
            "--grace",
            "0.1",
            *receipt,
            "--",
            *stubborn_child_command(pid_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    descendant = wait_pid(pid_path)
    owner.send_signal(signal.SIGHUP)
    if owner.wait(timeout=3) != 128 + signal.SIGHUP:
        fail("terminal hangup status was not preserved")
    require_gone(descendant, "hangup descendant")
    require_receipt(receipt_path, token, "hangup command")


def check_sigkill_has_no_receipt(root: Path) -> None:
    state_path = root / "sigkill.json"
    receipt, receipt_path, _token = receipt_args(root, "sigkill")
    source = (
        "import json,os,pathlib,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);"
        "pathlib.Path(sys.argv[1]).write_text(json.dumps("
        "{'group':os.getpid(),'descendant':p.pid}));"
        "time.sleep(60)"
    )
    owner = subprocess.Popen(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "60",
            "--grace",
            "0.1",
            *receipt,
            "--",
            sys.executable,
            "-c",
            source,
            str(state_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 3
    state: dict[str, int] | None = None
    while time.monotonic() < deadline:
        try:
            parsed = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(parsed.get("group"), int) and isinstance(parsed.get("descendant"), int):
                state = parsed
                break
        except (FileNotFoundError, ValueError):
            pass
        time.sleep(0.02)
    if state is None:
        owner.kill()
        fail("SIGKILL fixture did not expose its process group")
    owner.kill()
    if owner.wait(timeout=3) != -signal.SIGKILL:
        fail("SIGKILL owner status was not preserved")
    if receipt_path.exists():
        fail("unhandled SIGKILL forged a terminal receipt")
    try:
        os.killpg(state["group"], signal.SIGKILL)
    except ProcessLookupError:
        pass
    require_gone(state["descendant"], "manually cleaned SIGKILL descendant")


def check_launch_failure_receipt(root: Path) -> None:
    missing_args, missing_receipt, missing_token = receipt_args(root, "missing")
    missing = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "2", *missing_args, "--", str(root / "missing-command")],
        capture_output=True,
        text=True,
        check=False,
    )
    if missing.returncode != 127 or "command not found" not in missing.stderr:
        fail("missing command launch failure was not preserved")
    require_receipt(missing_receipt, missing_token, "missing command")

    blocked_command = root / "non-executable"
    blocked_command.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    blocked_command.chmod(0o600)
    denied_args, denied_receipt, denied_token = receipt_args(root, "denied")
    denied = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "2", *denied_args, "--", str(blocked_command)],
        capture_output=True,
        text=True,
        check=False,
    )
    if denied.returncode != 126 or "launch failed" not in denied.stderr:
        fail("pre-spawn permission failure was not preserved")
    require_receipt(denied_receipt, denied_token, "permission-denied command")

    identity_args, identity_receipt, identity_token = receipt_args(root, "identity")
    identity = subprocess.run(
        [sys.executable, str(RUNNER), "--timeout", "2", *identity_args, "--", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    if identity.returncode != 126 or "executable identity failed" not in identity.stderr:
        fail("unhashable executable identity did not fail closed")
    if "@unhashed" in identity.stderr:
        fail("unhashable executable emitted a normal proof identity")
    require_receipt(identity_receipt, identity_token, "unhashable command")


def check_status() -> None:
    with tempfile.TemporaryDirectory(prefix="bounded-status-") as temporary:
        root = Path(temporary)
        receipt, receipt_path, token = receipt_args(root, "status")
        result = subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--timeout",
                "2",
                *receipt,
                "--",
                sys.executable,
                "-c",
                "raise SystemExit(7)",
            ],
            check=False,
        )
        if result.returncode != 7:
            fail("child failure status was not preserved")
        require_receipt(receipt_path, token, "failed command")


def check_cwd(root: Path) -> None:
    probe = "import os,sys;sys.exit(0 if os.path.realpath(os.getcwd())==os.path.realpath(sys.argv[1]) else 1)"
    bound = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "5",
            "--cwd",
            str(root),
            "--",
            sys.executable,
            "-c",
            probe,
            str(root),
        ],
        check=False,
    )
    if bound.returncode != 0:
        fail("--cwd did not bind the command working directory")
    missing = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--timeout",
            "5",
            "--cwd",
            str(root / "absent"),
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if missing.returncode == 0 or "cwd" not in missing.stderr:
        fail("missing --cwd directory was accepted")


def receipt_digest(stderr: str) -> str:
    match = re.search(r"argv_sha256=([0-9a-f]{64})", stderr)
    if match is None:
        fail("bounded receipt omitted the argv digest")
    return match.group(1)


def check_safe_argv_receipt() -> None:
    secret = "super-secret-token-value"
    alternate_secret = "another-secret-token-value"
    signed_url = "https://example.invalid/download?X-Amz-Signature=signature-value&X-Amz-Credential=credential-value"
    alternate_url = signed_url.replace("signature-value", "different-signature")

    def invoke(token: str, url: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), "--timeout", "5", "--", sys.executable, "-c", "pass", "--token", token, url],
            capture_output=True,
            text=True,
            check=False,
        )

    first = invoke(secret, signed_url)
    second = invoke(alternate_secret, alternate_url)
    if first.returncode != 0 or second.returncode != 0:
        fail("safe argv receipt fixture did not complete")
    if "argv_count=6" not in first.stderr:
        fail("safe argv receipt omitted the argument count")
    if receipt_digest(first.stderr) != receipt_digest(second.stderr):
        fail("redacted secret and signed URL values changed the argv identity")
    for forbidden in (secret, alternate_secret, signed_url, alternate_url):
        if forbidden in first.stderr or forbidden in second.stderr:
            fail("bounded receipt leaked a secret or signed URL argument")


def check_capture_api(root: Path) -> None:
    result = run_captured(
        [sys.executable, "-c", "import sys; print('captured stdout'); print('captured stderr', file=sys.stderr)"],
        timeout=5,
        grace=0.1,
        cwd=str(root),
        env=os.environ.copy(),
    )
    if result.returncode != 0 or not result.terminal:
        fail("captured bounded API did not complete")
    if result.stdout != b"captured stdout\n" or result.stderr != b"captured stderr\n":
        fail("captured bounded API lost stdout or stderr")
    input_result = run_captured(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
        timeout=5,
        grace=0.1,
        cwd=str(root),
        env=os.environ.copy(),
        input_data=b"bounded input\n",
    )
    if input_result.returncode != 0 or input_result.stdout != b"bounded input\n":
        fail("captured bounded API lost its bounded input")
    input_path = root / "bounded-input.bin"
    input_path.write_bytes(b"descriptor input\n")
    descriptor = os.open(input_path, os.O_RDONLY)
    try:
        descriptor_result = run_captured(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(sys.stdin.buffer.read())"],
            timeout=5,
            grace=0.1,
            cwd=str(root),
            env=os.environ.copy(),
            stdin_fd=descriptor,
        )
    finally:
        os.close(descriptor)
    if descriptor_result.returncode != 0 or descriptor_result.stdout != b"descriptor input\n":
        fail("captured bounded API lost descriptor input")
    try:
        run_captured([sys.executable, "-c", "pass"], timeout=5, input_data=b"x" * (INPUT_LIMIT_BYTES + 1))
    except ValueError:
        pass
    else:
        fail("captured bounded API accepted oversized input")
    pid_path = root / "captured-timeout.pid"
    timed_out = run_captured(
        stubborn_child_command(pid_path), timeout=1, grace=0.1, cwd=str(root), env=os.environ.copy()
    )
    if timed_out.returncode != 124 or not timed_out.terminal:
        fail("captured bounded API did not enforce its deadline")
    require_gone(wait_pid(pid_path), "captured API descendant")

    limited = run_captured(
        [sys.executable, "-c", f"import sys; sys.stdout.buffer.write(b'x' * {CAPTURE_LIMIT_BYTES + 1024})"],
        timeout=5,
        grace=0.1,
        cwd=str(root),
        env=os.environ.copy(),
    )
    if limited.returncode != OUTPUT_LIMIT_EXIT or not limited.stdout_truncated:
        fail("captured bounded API did not report its output limit")
    if limited.stderr_truncated or len(limited.stdout) != CAPTURE_LIMIT_BYTES:
        fail("captured bounded API did not bound the retained output")


def check_wiring() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    skill = (ROOT / "skills/deterministic-checks/SKILL.md").read_text(encoding="utf-8")
    if "deterministic-checks` bounded runner + explicit whole-run timeout" not in agents:
        fail("global project-command route is missing")
    for anchor in ("bounded_run.py", "TERM → grace → KILL", "raw unbounded project command = `FAIL`", "--cwd"):
        if anchor not in skill:
            fail(f"deterministic-checks contract missing: {anchor}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="bounded-run-") as temporary:
        root = Path(temporary)
        check_pid_readiness(root)
        check_timeout(root)
        check_completed_parent(root)
        check_terminal_loss(root)
        check_sigkill_has_no_receipt(root)
        check_launch_failure_receipt(root)
        check_cwd(root)
        check_capture_api(root)
    check_status()
    check_wiring()
    check_safe_argv_receipt()
    print("bounded-run-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

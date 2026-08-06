#!/usr/bin/env python3
"""Run one command with a deadline and process-group cleanup."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import secrets
import shlex
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

TIMEOUT_EXIT = 124
BACKGROUND_EXIT = 125
TERMINALITY_EXIT = 126
TOKEN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True)
class RunResult:
    returncode: int
    terminal: bool


class InterruptedRun(Exception):
    """Handled owner signal with process-group terminality evidence."""


def group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_group(process: subprocess.Popen[bytes], grace: float) -> tuple[bool, bool]:
    process_group = process.pid
    if not group_exists(process_group):
        process.poll()
        return False, True
    existed = True
    try:
        os.killpg(process_group, signal.SIGTERM)
    except (PermissionError, ProcessLookupError):
        return existed, not group_exists(process_group)
    deadline = time.monotonic() + grace
    while group_exists(process_group) and time.monotonic() < deadline:
        process.poll()
        time.sleep(0.02)
    if group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except (PermissionError, ProcessLookupError):
            pass
        deadline = time.monotonic() + grace
        while group_exists(process_group) and time.monotonic() < deadline:
            process.poll()
            time.sleep(0.02)
    process.poll()
    return existed, not group_exists(process_group)


def run(
    command: Sequence[str],
    timeout: float,
    grace: float,
    cwd: str | None = None,
) -> RunResult:
    process = subprocess.Popen(command, start_new_session=True, cwd=cwd)
    previous: dict[signal.Signals, signal._HANDLER] = {}
    stopped: tuple[bool, bool] | None = None

    def stop_once() -> tuple[bool, bool]:
        nonlocal stopped
        if stopped is None:
            stopped = stop_group(process, grace)
        return stopped

    def interrupted(signum: int, _frame: object) -> None:
        for current in handled:
            signal.signal(current, signal.SIG_IGN)
        _existed, terminal = stop_once()
        if not terminal:
            print(
                "bounded-run: process group terminality could not be proven",
                file=sys.stderr,
            )
        raise InterruptedRun(signum, terminal)

    handled = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    for current in handled:
        previous[current] = signal.signal(current, interrupted)
    try:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            _existed, terminal = stop_once()
            if not terminal:
                print(
                    "bounded-run: TIMEOUT and process group terminality could not be proven",
                    file=sys.stderr,
                )
                return RunResult(TERMINALITY_EXIT, False)
            print(
                f"bounded-run: TIMEOUT after {timeout:g}s; command group terminated",
                file=sys.stderr,
            )
            return RunResult(TIMEOUT_EXIT, True)
        existed, terminal = stop_once()
        if not terminal:
            print(
                "bounded-run: process group terminality could not be proven",
                file=sys.stderr,
            )
            return RunResult(TERMINALITY_EXIT, False)
        if existed:
            print("bounded-run: BACKGROUND descendant terminated after command exit", file=sys.stderr)
            return RunResult(BACKGROUND_EXIT, True)
        return RunResult(returncode, True)
    except InterruptedRun as error:
        signum, terminal = error.args
        return RunResult(128 + signum, bool(terminal))
    finally:
        for current, handler in previous.items():
            signal.signal(current, handler)
        stop_once()


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_terminal_receipt(path: Path, token: str) -> None:
    if path.exists() or path.is_symlink():
        raise ValueError("terminal receipt target already exists")
    temporary = path.parent / (
        f".{path.name}.{os.getpid()}.{secrets.token_hex(8)}.tmp"
    )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(temporary, flags, 0o600)
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid():
            raise ValueError("terminal receipt temporary is unsafe")
        payload = json.dumps(
            {"terminal": True, "token": token},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written <= 0:
                raise OSError("cannot write terminal receipt")
            offset += written
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    try:
        os.link(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--grace", type=float, default=2.0)
    parser.add_argument("--cwd")
    parser.add_argument("--terminal-receipt")
    parser.add_argument("--terminal-token")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not math.isfinite(args.timeout) or not math.isfinite(args.grace) or args.timeout <= 0 or args.grace < 0:
        parser.error("timeout must be positive and grace must be non-negative")
    if args.cwd is not None and not os.path.isdir(args.cwd):
        parser.error(f"cwd is not a directory: {args.cwd}")
    if bool(args.terminal_receipt) != bool(args.terminal_token):
        parser.error("--terminal-receipt and --terminal-token must be provided together")
    if args.terminal_token and not TOKEN.fullmatch(args.terminal_token):
        parser.error("--terminal-token must be 64 lowercase hexadecimal characters")
    if args.terminal_receipt and not Path(args.terminal_receipt).is_absolute():
        parser.error("--terminal-receipt must be an absolute path")
    if not command:
        parser.error("command is required after --")
    try:
        result = run(command, args.timeout, args.grace, args.cwd)
    except FileNotFoundError as error:
        print(f"bounded-run: command not found: {error.filename}", file=sys.stderr)
        result = RunResult(127, True)
    except OSError as error:
        print(f"bounded-run: command launch failed: {error}", file=sys.stderr)
        result = RunResult(TERMINALITY_EXIT, True)
    if result.terminal and args.terminal_receipt:
        try:
            write_terminal_receipt(
                Path(args.terminal_receipt),
                args.terminal_token,
            )
        except (OSError, ValueError) as error:
            print(f"bounded-run: terminal receipt failed: {error}", file=sys.stderr)
            return TERMINALITY_EXIT
    executable = shutil.which(command[0]) or command[0]
    cwd = os.path.abspath(args.cwd) if args.cwd else os.getcwd()
    print(
        f"bounded-run: receipt exe={executable} cwd={cwd} argv={shlex.join(command)} exit={result.returncode}",
        file=sys.stderr,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

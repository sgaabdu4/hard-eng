#!/usr/bin/env python3
"""Run one command with a deadline and process-group cleanup."""
from __future__ import annotations

import argparse
import math
import os
import signal
import subprocess
import sys
import time
from collections.abc import Sequence

TIMEOUT_EXIT = 124
BACKGROUND_EXIT = 125


def group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_group(process: subprocess.Popen[bytes], grace: float) -> bool:
    process_group = process.pid
    if not group_exists(process_group):
        return False
    try:
        os.killpg(process_group, signal.SIGTERM)
    except (PermissionError, ProcessLookupError):
        return True
    deadline = time.monotonic() + grace
    while group_exists(process_group) and time.monotonic() < deadline:
        time.sleep(0.02)
    if group_exists(process_group):
        try:
            os.killpg(process_group, signal.SIGKILL)
        except (PermissionError, ProcessLookupError):
            pass
    try:
        process.wait(timeout=max(grace, 0.1))
    except subprocess.TimeoutExpired:
        pass
    return True


def run(command: Sequence[str], timeout: float, grace: float) -> int:
    process = subprocess.Popen(command, start_new_session=True)
    previous: dict[signal.Signals, object] = {}

    def interrupted(signum: int, _frame: object) -> None:
        stop_group(process, grace)
        raise SystemExit(128 + signum)

    handled = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    for current in handled:
        previous[current] = signal.signal(current, interrupted)
    try:
        try:
            returncode = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            stop_group(process, grace)
            print(f"bounded-run: TIMEOUT after {timeout:g}s; command group terminated", file=sys.stderr)
            return TIMEOUT_EXIT
        if stop_group(process, grace):
            print("bounded-run: BACKGROUND descendant terminated after command exit", file=sys.stderr)
            return BACKGROUND_EXIT
        return returncode
    finally:
        for current, handler in previous.items():
            signal.signal(current, handler)
        stop_group(process, grace)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--grace", type=float, default=2.0)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not math.isfinite(args.timeout) or not math.isfinite(args.grace) or args.timeout <= 0 or args.grace < 0:
        parser.error("timeout must be positive and grace must be non-negative")
    if not command:
        parser.error("command is required after --")
    try:
        return run(command, args.timeout, args.grace)
    except FileNotFoundError as error:
        print(f"bounded-run: command not found: {error.filename}", file=sys.stderr)
        return 127


if __name__ == "__main__":
    raise SystemExit(main())

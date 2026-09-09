#!/usr/bin/env python3
"""Run one full Dart Decimate gate for an exact Dart package owner."""

from __future__ import annotations

import argparse
import math
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bounded_run import TIMEOUT_EXIT, run_captured
from bounded_run import run as run_bounded_process
from git_env import git_env
from source_tree_coordination import (
    CoordinationError,
    consume_terminal_receipt,
    remaining,
    source_tree_lock,
    terminal_receipt_spec,
    tree_fingerprint,
    validate_external_npx,
)

BOUNDED = SCRIPT_DIR / "bounded_run.py"


def error(message: str) -> int:
    print(f"Dart Decimate gate: {message}", file=sys.stderr)
    return 2


def git(package: Path, *args: str, timeout: float | None = None) -> subprocess.CompletedProcess[str]:
    command = ["git", "-C", str(package), *args]
    captured = run_captured(command, timeout or 20, env=git_env())
    if captured.returncode == TIMEOUT_EXIT:
        raise TimeoutError("Git command deadline exhausted")
    return subprocess.CompletedProcess(
        command,
        captured.returncode,
        captured.stdout.decode("utf-8", "replace"),
        captured.stderr.decode("utf-8", "replace"),
    )


def repository_root(package: Path, deadline: float) -> Path | None:
    result = git(package, "rev-parse", "--show-toplevel", timeout=remaining(deadline, "during repository discovery"))
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=".", help="Dart package containing pubspec.yaml")
    parser.add_argument("--timeout", type=float, required=True)
    args = parser.parse_args()

    if not math.isfinite(args.timeout) or args.timeout <= 0:
        return error("--timeout must be finite and positive")
    deadline = time.monotonic() + args.timeout
    package = Path(args.package).expanduser().resolve()
    if not package.is_dir() or not (package / "pubspec.yaml").is_file():
        return error("--package must be a Dart package directory")
    try:
        root = repository_root(package, deadline)
    except TimeoutError:
        return error("whole-run timeout exhausted during repository discovery")
    if root is None:
        return error("package is not inside a Git repository")
    try:
        relative_package = package.relative_to(root)
    except ValueError:
        return error("package resolves outside the Git repository")

    command = ["npx", "--yes", "dart-decimate@latest", "json", str(root)]
    if relative_package != Path("."):
        command.extend(["--workspace", relative_package.as_posix()])
    try:
        with source_tree_lock(root, exclusive=False, deadline=deadline):
            validate_external_npx(root, deadline=deadline)
            fingerprint_started = time.monotonic()
            before = tree_fingerprint(root, deadline=deadline)
            fingerprint_headroom = max(0.05, (time.monotonic() - fingerprint_started) * 2)
            budget = remaining(deadline, "before Dart Decimate")
            grace = min(2.0, max(0.1, budget * 0.02))
            launch_headroom = min(1.0, max(0.1, budget * 0.01))
            command_timeout = budget - (2 * grace) - fingerprint_headroom - launch_headroom
            if command_timeout <= 0:
                raise CoordinationError("whole-run timeout has no command and shutdown headroom")
            receipt_path, receipt_token = terminal_receipt_spec(root)
            completed = run_bounded_process(
                [
                    sys.executable,
                    str(BOUNDED),
                    "--timeout",
                    str(command_timeout),
                    "--grace",
                    str(grace),
                    "--terminal-receipt",
                    str(receipt_path),
                    "--terminal-token",
                    receipt_token,
                    "--cwd",
                    str(root),
                    "--",
                    *command,
                ],
                command_timeout + (2 * grace) + 5,
                grace=2,
                env=git_env(),
            )
            consume_terminal_receipt(receipt_path, receipt_token)
            if tree_fingerprint(root, deadline=deadline) != before:
                raise CoordinationError("Dart Decimate mutated the repository tree")
    except (CoordinationError, OSError, subprocess.SubprocessError) as caught:
        return error(str(caught))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

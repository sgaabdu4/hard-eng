#!/usr/bin/env python3
"""Run one command with a deadline and process-group cleanup."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Mapping

TIMEOUT_EXIT = 124
BACKGROUND_EXIT = 125
TERMINALITY_EXIT = 126
OUTPUT_LIMIT_EXIT = 127
CAPTURE_LIMIT_BYTES = 4 * 1024 * 1024
INPUT_LIMIT_BYTES = 64 * 1024
TOKEN = re.compile(r"[0-9a-f]{64}")
SENSITIVE_OPTION = re.compile(
    r"^--?[A-Za-z0-9_.-]*(?:token|secret|password|passwd|api[-_]?key|"
    r"auth(?:orization)?|cookie|credential|private[-_]?key|signature|sig)"
    r"(?:[A-Za-z0-9_.-]*)?(?:=|$)",
    re.IGNORECASE,
)
SENSITIVE_INLINE = re.compile(
    r"(?:authorization|bearer|token|secret|password|passwd|api[-_]?key|"
    r"credential|signature|sig)\s*[:=]",
    re.IGNORECASE,
)
SIGNED_URL = re.compile(
    r"https?://[^\s]+[?&](?:token|sig|signature|x-amz-signature|"
    r"x-goog-signature|access_token)=[^\s]+",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RunResult:
    returncode: int
    terminal: bool


@dataclass(frozen=True)
class CapturedRunResult(RunResult):
    """Bounded result with concurrently drained stdout and stderr."""

    stdout: bytes
    stderr: bytes
    stdout_truncated: bool
    stderr_truncated: bool


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


def _drain(
    stream: BinaryIO,
    chunks: list[bytes],
    truncated: list[bool],
) -> None:
    remaining = CAPTURE_LIMIT_BYTES
    try:
        while True:
            chunk = stream.read(65536)
            if not chunk:
                return
            keep = min(len(chunk), remaining)
            if keep:
                chunks.append(chunk[:keep])
                remaining -= keep
            if keep < len(chunk):
                truncated[0] = True
    except (OSError, ValueError):
        return


def _feed(stream: BinaryIO, payload: bytes) -> None:
    try:
        stream.write(payload)
        stream.close()
    except (BrokenPipeError, OSError, ValueError):
        try:
            stream.close()
        except (OSError, ValueError):
            pass


def _run(
    command: Sequence[str],
    timeout: float,
    grace: float,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    capture_output: bool = False,
    input_data: bytes | None = None,
    stdin_fd: int | None = None,
) -> RunResult | CapturedRunResult:
    if input_data is not None and stdin_fd is not None:
        raise ValueError("bounded input accepts bytes or a file descriptor, not both")
    if input_data is not None and len(input_data) > INPUT_LIMIT_BYTES:
        raise ValueError("bounded input exceeds the 64 KiB limit")
    process = subprocess.Popen(
        command,
        start_new_session=True,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        stdin=(subprocess.PIPE if input_data is not None else stdin_fd),
    )
    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    stdout_truncated = [False]
    stderr_truncated = [False]
    readers: list[threading.Thread] = []
    writer: threading.Thread | None = None
    if capture_output:
        assert process.stdout is not None
        assert process.stderr is not None
        readers = [
            threading.Thread(
                target=_drain,
                args=(process.stdout, stdout_chunks, stdout_truncated),
                daemon=True,
            ),
            threading.Thread(
                target=_drain,
                args=(process.stderr, stderr_chunks, stderr_truncated),
                daemon=True,
            ),
        ]
        for reader in readers:
            reader.start()
    if input_data is not None:
        assert process.stdin is not None
        writer = threading.Thread(
            target=_feed,
            args=(process.stdin, input_data),
            daemon=True,
        )
        writer.start()

    def result(returncode: int, terminal: bool) -> RunResult | CapturedRunResult:
        input_incomplete = False
        if writer is not None:
            writer.join(timeout=max(grace, 0.1))
            input_incomplete = writer.is_alive()
        if capture_output:
            for reader, truncated in zip(
                readers,
                (stdout_truncated, stderr_truncated),
                strict=True,
            ):
                reader.join(timeout=max(grace, 0.1))
                if reader.is_alive():
                    truncated[0] = True
            limited = stdout_truncated[0] or stderr_truncated[0]
            return CapturedRunResult(
                (TERMINALITY_EXIT if input_incomplete else
                 OUTPUT_LIMIT_EXIT if limited else returncode),
                terminal and not input_incomplete,
                b"".join(stdout_chunks),
                b"".join(stderr_chunks),
                stdout_truncated[0],
                stderr_truncated[0],
            )
        return RunResult(
            TERMINALITY_EXIT if input_incomplete else returncode,
            terminal and not input_incomplete,
        )

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
    install_handlers = threading.current_thread() is threading.main_thread()
    if install_handlers:
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
                return result(TERMINALITY_EXIT, False)
            print(
                f"bounded-run: TIMEOUT after {timeout:g}s; command group terminated",
                file=sys.stderr,
            )
            return result(TIMEOUT_EXIT, True)
        existed, terminal = stop_once()
        if not terminal:
            print(
                "bounded-run: process group terminality could not be proven",
                file=sys.stderr,
            )
            return result(TERMINALITY_EXIT, False)
        if existed:
            print("bounded-run: BACKGROUND descendant terminated after command exit", file=sys.stderr)
            return result(BACKGROUND_EXIT, True)
        return result(returncode, True)
    except InterruptedRun as error:
        signum, terminal = error.args
        return result(128 + signum, bool(terminal))
    finally:
        if install_handlers:
            for current, handler in previous.items():
                signal.signal(current, handler)
        stop_once()


def run(
    command: Sequence[str],
    timeout: float,
    grace: float,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
) -> RunResult:
    result = _run(command, timeout, grace, cwd, env, capture_output=False)
    assert isinstance(result, RunResult)
    return result


def run_captured(
    command: Sequence[str],
    timeout: float,
    grace: float = 2.0,
    cwd: str | None = None,
    env: Mapping[str, str] | None = None,
    input_data: bytes | None = None,
    stdin_fd: int | None = None,
) -> CapturedRunResult:
    """Run a command with process-group cleanup while capturing both streams."""
    result = _run(
        command, timeout, grace, cwd, env,
        capture_output=True, input_data=input_data, stdin_fd=stdin_fd,
    )
    assert isinstance(result, CapturedRunResult)
    return result


def _redacted_argv(command: Sequence[str]) -> tuple[int, str]:
    redacted: list[str] = []
    redact_next = False
    for item in command:
        value = os.fsdecode(item)
        if redact_next:
            redacted.append("<redacted>")
            redact_next = False
            continue
        if SENSITIVE_OPTION.match(value):
            redacted.append("<redacted-option>")
            if "=" not in value:
                redact_next = True
            continue
        if SIGNED_URL.search(value) or SENSITIVE_INLINE.search(value):
            redacted.append("<redacted>")
            continue
        redacted.append(value)
    payload = "\0".join(redacted).encode("utf-8", "surrogateescape")
    return len(command), hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _executable_identity(command: str) -> str:
    executable = shutil.which(command)
    if executable is None:
        candidate = Path(command)
        if not candidate.exists():
            raise FileNotFoundError(command)
        executable = command
    resolved = Path(executable).resolve(strict=True)
    digest = _file_sha256(resolved)
    return f"{resolved}@sha256:{digest}"


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
    result: RunResult | None = None
    try:
        executable = _executable_identity(command[0])
    except FileNotFoundError:
        print(f"bounded-run: command not found: {command[0]}", file=sys.stderr)
        executable = f"{command[0]}@missing"
        result = RunResult(127, True)
    except (OSError, RuntimeError) as error:
        print(f"bounded-run: executable identity failed: {error}", file=sys.stderr)
        executable = f"{command[0]}@identity-failed"
        result = RunResult(TERMINALITY_EXIT, True)
    if result is None:
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
    cwd = os.path.abspath(args.cwd) if args.cwd else os.getcwd()
    argv_count, argv_digest = _redacted_argv(command)
    print(
        f"bounded-run: receipt exe={executable} cwd={cwd} argv_count={argv_count} "
        f"argv_sha256={argv_digest} exit={result.returncode}",
        file=sys.stderr,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

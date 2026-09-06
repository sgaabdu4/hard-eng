#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of bounded_run.py (part 2)."""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bounded_run
from git_env_survivors_regression_check import make_checker

fail, require = make_checker("bounded-run-survivors-2")

TOKEN = "a" * 64


def ignoring_sigterm(seconds: float) -> list[str]:
    source = f"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep({seconds})"
    return [sys.executable, "-c", source]


# ------------------------------------------------------------------------------- main


def capture_exit(argv: list[str]):
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            bounded_run.main(argv)
        except SystemExit as exit_info:
            return exit_info.code, out.getvalue(), err.getvalue()
    fail(f"expected SystemExit for argv={argv!r}")


def run_main(argv: list[str]):
    import contextlib
    import io

    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bounded_run.main(argv)
    return code, out.getvalue(), err.getvalue()


def check_main_timeout_is_required() -> None:
    try:
        bounded_run.main(["--", "true"])
    except SystemExit as exit_info:
        require(exit_info.code == 2, "missing --timeout must exit status 2")
    else:
        fail("missing --timeout must raise SystemExit")


def check_main_help_includes_the_module_description() -> None:
    code, out, _err = capture_exit(["--help"])
    require(code == 0, "...")
    doc = bounded_run.__doc__
    if doc is None:
        fail("bounded_run.py must declare a module docstring")
    require(doc.strip() in out, "the parser description must surface the module docstring")


def check_main_rejects_zero_timeout_with_exact_message() -> None:
    code, _out, err = capture_exit(["--timeout", "0", "--", "true"])
    require(code == 2, "...")
    require(
        "timeout must be positive and grace must be non-negative" in err and "XX" not in err,
        f"unexpected stderr: {err!r}",
    )


def check_main_accepts_zero_grace() -> None:
    code, _out, _err = run_main(["--timeout", "5", "--grace", "0", "--", "true"])
    require(code == 0, f"grace of exactly zero must be accepted, exit was {code}")


def check_main_rejects_non_finite_timeout() -> None:
    code, _out, _err = capture_exit(["--timeout", "inf", "--", "true"])
    require(code == 2, "a non-finite timeout must be rejected")


def check_main_grace_default_is_two_seconds() -> None:
    started = time.monotonic()
    code, _out, _err = run_main(["--timeout", "0.5", "--", *ignoring_sigterm(30)])
    elapsed = time.monotonic() - started
    require(code == bounded_run.TIMEOUT_EXIT, "...")
    require(elapsed < 2.7, f"default grace appears longer than 2.0s: {elapsed:.2f}s")


def check_main_argv_is_actually_used() -> None:
    code, _out, _err = run_main(["--timeout", "5", "--", "true"])
    require(code == 0, "main() must parse the argv it was given, not the process argv")


def check_main_cwd_must_be_a_directory() -> None:
    code, _out, err = capture_exit(["--timeout", "5", "--cwd", "/no/such/directory-xyz", "--", "true"])
    require(code == 2, "...")
    require("cwd is not a directory: /no/such/directory-xyz" in err, f"unexpected stderr: {err!r}")


def check_main_receipt_and_token_must_be_paired() -> None:
    code, _out, err = capture_exit(["--timeout", "5", "--terminal-receipt", "/tmp/x", "--", "true"])
    require(code == 2, "...")
    require(
        "--terminal-receipt and --terminal-token must be provided together" in err and "XX" not in err,
        f"unexpected stderr: {err!r}",
    )


def check_main_terminal_token_format_is_enforced() -> None:
    with tempfile.TemporaryDirectory(prefix="main-token-") as workspace:
        receipt = Path(workspace) / "r.json"
        code, _out, err = capture_exit(
            ["--timeout", "5", "--terminal-receipt", str(receipt), "--terminal-token", "not-hex", "--", "true"]
        )
        require(code == 2, "...")
        require(
            "--terminal-token must be 64 lowercase hexadecimal characters" in err and "XX" not in err,
            f"unexpected stderr: {err!r}",
        )


def check_main_receipt_path_must_be_absolute() -> None:
    code, _out, err = capture_exit(
        ["--timeout", "5", "--terminal-receipt", "relative.json", "--terminal-token", TOKEN, "--", "true"]
    )
    require(code == 2, "...")
    require("--terminal-receipt must be an absolute path" in err and "XX" not in err, f"unexpected stderr: {err!r}")


def check_main_command_is_required() -> None:
    code, _out, err = capture_exit(["--timeout", "5", "--"])
    require(code == 2, "...")
    require("command is required after --" in err and "XX" not in err, f"unexpected stderr: {err!r}")


def install_run_spy() -> tuple[list[object], object]:
    calls: list[object] = []
    original_run = bounded_run.run

    def spy_run(*a, **kw):
        calls.append((a, kw))
        return original_run(*a, **kw)

    bounded_run.__dict__["run"] = spy_run
    return calls, original_run


def check_main_missing_command_reports_127_with_receipt() -> None:
    with tempfile.TemporaryDirectory(prefix="main-missing-") as workspace:
        receipt = Path(workspace) / "r.json"
        missing = "totally-nonexistent-cmd-xyz"
        calls, original_run = install_run_spy()
        try:
            code, _out, err = run_main(
                ["--timeout", "5", "--terminal-receipt", str(receipt), "--terminal-token", TOKEN, "--", missing]
            )
        finally:
            bounded_run.__dict__["run"] = original_run
        require(code == 127, f"a missing command must return 127, got {code}")
        require(f"command not found: {missing}" in err, f"unexpected stderr: {err!r}")
        require(f"exe={missing}@missing" in err, f"receipt line must name the missing executable: {err!r}")
        require(receipt.exists(), "a missing command is still a terminal outcome and must publish a receipt")
        require(
            not calls,
            f"an identity failure that already resolved a result must never fall through to run(), got {calls!r}",
        )


def check_main_run_launch_missing_reports_via_second_handler() -> None:
    with tempfile.TemporaryDirectory(prefix="main-badshebang-") as workspace:
        target = Path(workspace) / "bad-shebang-cmd"
        target.write_text("#!/nonexistent-interpreter-xyz\necho hi\n", encoding="utf-8")
        target.chmod(0o755)
        receipt = Path(workspace) / "r.json"
        code, _out, err = run_main(
            ["--timeout", "5", "--terminal-receipt", str(receipt), "--terminal-token", TOKEN, "--", str(target)]
        )
        require(code == 127, f"a launch-time missing interpreter must return 127, got {code}")
        require(f"bounded-run: command not found: {target}" in err and "XX" not in err, f"unexpected stderr: {err!r}")
        require(receipt.exists(), "a launch-time FileNotFoundError is still terminal and must publish a receipt")


def check_main_unreadable_executable_reports_terminality_exit() -> None:
    with tempfile.TemporaryDirectory(prefix="main-unreadable-") as workspace:
        target = Path(workspace) / "unreadable-command"
        target.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        target.chmod(0o000)
        receipt = Path(workspace) / "r.json"
        calls, original_run = install_run_spy()
        try:
            code, _out, err = run_main(
                ["--timeout", "5", "--terminal-receipt", str(receipt), "--terminal-token", TOKEN, "--", str(target)]
            )
        finally:
            target.chmod(0o600)
            bounded_run.__dict__["run"] = original_run
        require(code == bounded_run.TERMINALITY_EXIT, f"an unreadable executable must fail closed, got {code}")
        require("executable identity failed" in err, f"unexpected stderr: {err!r}")
        require(f"exe={target}@identity-failed" in err, f"receipt line must name the failure: {err!r}")
        require(receipt.exists(), "an identity failure is terminal and must publish a receipt")
        require(
            not calls,
            f"an identity failure that already resolved a result must never fall through to run(), got {calls!r}",
        )


def check_main_receipt_write_failure_is_reported() -> None:
    with tempfile.TemporaryDirectory(prefix="main-receipt-fail-") as workspace:
        receipt = Path(workspace) / "r.json"
        receipt.write_text("{}", encoding="utf-8")
        code, _out, err = run_main(
            ["--timeout", "5", "--terminal-receipt", str(receipt), "--terminal-token", TOKEN, "--", "true"]
        )
        require(code == bounded_run.TERMINALITY_EXIT, f"a pre-existing receipt target must fail closed, got {code}")
        require("terminal receipt failed: terminal receipt target already exists" in err, f"unexpected stderr: {err!r}")


def check_main_final_receipt_names_the_real_cwd() -> None:
    code, _out, err = run_main(["--timeout", "5", "--", "true"])
    require(code == 0, "...")
    require(f"cwd={os.getcwd()}" in err, f"the success receipt must name the real cwd, got: {err!r}")


# ------------------------------------------------------------------- write_terminal_receipt


def check_write_terminal_receipt_rejects_a_dangling_symlink() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-symlink-") as workspace:
        link = Path(workspace) / "receipt-link"
        link.symlink_to(Path(workspace) / "missing-target")
        try:
            bounded_run.write_terminal_receipt(link, TOKEN)
        except ValueError as error:
            require(error.args == ("terminal receipt target already exists",), f"unexpected message: {error.args!r}")
        else:
            fail("a dangling symlink target must be rejected before any write is attempted")


def check_write_terminal_receipt_rejects_unsafe_temporary_exact_message() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-unsafe-") as workspace:
        receipt = Path(workspace) / "receipt.json"

        class FakeStat:
            st_mode = 0
            st_uid = os.getuid()

        original_fstat = bounded_run.os.fstat

        def spy_fstat(fd):
            return FakeStat()

        bounded_run.os.fstat = spy_fstat
        try:
            try:
                bounded_run.write_terminal_receipt(receipt, TOKEN)
            except ValueError as error:
                require(error.args == ("terminal receipt temporary is unsafe",), f"unexpected message: {error.args!r}")
            else:
                fail("an unsafe temporary (not a regular file) must be rejected")
        finally:
            bounded_run.os.fstat = original_fstat
        require(not receipt.exists(), "an unsafe temporary must never be linked into place")


def check_write_terminal_receipt_temp_suffix_uses_8_random_bytes() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-tokenhex-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        calls: list[object] = []
        original_token_hex = bounded_run.secrets.token_hex

        def spy_token_hex(nbytes=None):
            calls.append(nbytes)
            return original_token_hex(nbytes)

        bounded_run.secrets.token_hex = spy_token_hex
        try:
            bounded_run.write_terminal_receipt(receipt, TOKEN)
        finally:
            bounded_run.secrets.token_hex = original_token_hex
        require(calls == [8], f"expected secrets.token_hex(8) exactly once, got {calls!r}")


def check_write_terminal_receipt_unlinks_temporary_with_missing_ok_true() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-unlink-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        captured: list[object] = []
        original_unlink = bounded_run.Path.unlink

        def spy_unlink(self, *a, **kw):
            captured.append(kw.get("missing_ok", a[0] if a else False))
            return original_unlink(self, *a, **kw)

        bounded_run.Path.unlink = spy_unlink
        try:
            bounded_run.write_terminal_receipt(receipt, TOKEN)
        finally:
            bounded_run.Path.unlink = original_unlink
        require(captured == [True], f"expected the temporary cleanup to use unlink(missing_ok=True), got {captured!r}")


def check_write_terminal_receipt_open_flags_and_mode_are_exact() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-flags-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        captured: list[tuple[int, int]] = []
        original_open = bounded_run.os.open

        def spy_open(path, flags, mode=0o777, *args, **kwargs):
            if flags & os.O_CREAT:
                captured.append((flags, mode))
            return original_open(path, flags, mode, *args, **kwargs)

        bounded_run.os.open = spy_open
        try:
            bounded_run.write_terminal_receipt(receipt, TOKEN)
        finally:
            bounded_run.os.open = original_open
        require(len(captured) == 1, f"expected exactly one O_CREAT os.open call, saw {len(captured)}")
        flags, mode = captured[0]
        required = os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC | os.O_NOFOLLOW
        require(flags & required == required, f"open flags {oct(flags)} are missing required safety bits")
        require(mode == 0o600, f"the temporary file must be created with mode 0600, got {oct(mode)}")


def check_write_terminal_receipt_json_payload_is_compact() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-json-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        bounded_run.write_terminal_receipt(receipt, TOKEN)
        raw = receipt.read_bytes()
        require(raw == ('{"terminal":true,"token":"' + TOKEN + '"}').encode(), f"unexpected payload bytes: {raw!r}")


def check_write_terminal_receipt_treats_a_zero_byte_write_as_failure() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-zerowrite-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        original_write = bounded_run.os.write
        calls: list[bytes] = []

        def spy_write(fd, data):
            calls.append(data)
            if len(calls) == 1:
                return 0
            return original_write(fd, data)

        bounded_run.os.write = spy_write
        try:
            try:
                bounded_run.write_terminal_receipt(receipt, TOKEN)
            except OSError as error:
                require(error.args == ("cannot write terminal receipt",), f"unexpected message: {error.args!r}")
            else:
                fail("a zero-byte write must be treated as a failure, not silently retried forever")
        finally:
            bounded_run.os.write = original_write
        require(not receipt.exists(), "a failed write must never publish a receipt")


def check_write_terminal_receipt_tolerates_a_positive_partial_write() -> None:
    with tempfile.TemporaryDirectory(prefix="wtr-partialwrite-") as workspace:
        receipt = Path(workspace) / "receipt.json"
        original_write = bounded_run.os.write
        state = {"split": False}

        def spy_write(fd, data):
            if not state["split"]:
                state["split"] = True
                return original_write(fd, data[:1])
            return original_write(fd, data)

        bounded_run.os.write = spy_write
        try:
            bounded_run.write_terminal_receipt(receipt, TOKEN)
        finally:
            bounded_run.os.write = original_write
        require(receipt.exists(), "a legitimate short write must not be treated as a failure")


def main() -> int:
    check_main_timeout_is_required()
    check_main_help_includes_the_module_description()
    check_main_rejects_zero_timeout_with_exact_message()
    check_main_accepts_zero_grace()
    check_main_rejects_non_finite_timeout()
    check_main_grace_default_is_two_seconds()
    check_main_argv_is_actually_used()
    check_main_cwd_must_be_a_directory()
    check_main_receipt_and_token_must_be_paired()
    check_main_terminal_token_format_is_enforced()
    check_main_receipt_path_must_be_absolute()
    check_main_command_is_required()
    check_main_missing_command_reports_127_with_receipt()
    check_main_run_launch_missing_reports_via_second_handler()
    check_main_unreadable_executable_reports_terminality_exit()
    check_main_receipt_write_failure_is_reported()
    check_main_final_receipt_names_the_real_cwd()
    check_write_terminal_receipt_rejects_a_dangling_symlink()
    check_write_terminal_receipt_rejects_unsafe_temporary_exact_message()
    check_write_terminal_receipt_temp_suffix_uses_8_random_bytes()
    check_write_terminal_receipt_unlinks_temporary_with_missing_ok_true()
    check_write_terminal_receipt_open_flags_and_mode_are_exact()
    check_write_terminal_receipt_json_payload_is_compact()
    check_write_terminal_receipt_treats_a_zero_byte_write_as_failure()
    check_write_terminal_receipt_tolerates_a_positive_partial_write()
    print("bounded-run-survivors-2: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

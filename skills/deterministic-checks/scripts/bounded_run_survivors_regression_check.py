#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of bounded_run.py."""

from __future__ import annotations

import contextlib
import hashlib
import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import TracebackType
from typing import IO, Any, Self, cast

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bounded_run
import bounded_run_regression_check as bounded_run_base
from bounded_run import CapturedRunResult, RunResult
from regression_fixture import checker

fail, require = checker("bounded-run-survivors")

wait_pid = bounded_run_base.wait_pid

TOKEN = "a" * 64


class _FakeProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid

    def poll(self) -> None:
        return None


def sleeper(seconds: float) -> list[str]:
    return [sys.executable, "-c", f"import time; time.sleep({seconds})"]


def ignoring_sigterm(seconds: float) -> list[str]:
    source = f"import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep({seconds})"
    return [sys.executable, "-c", source]


def leaves_a_grandchild(pid_path: Path) -> list[str]:
    source = (
        "import pathlib,subprocess,sys,time;"
        "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']);"
        f"pathlib.Path({str(pid_path)!r}).write_text(str(p.pid));"
    )
    return [sys.executable, "-c", source]


# ---------------------------------------------------------------- group_exists


def check_group_exists_probe_sends_no_real_signal() -> None:
    with tempfile.TemporaryDirectory(prefix="group-probe-") as workspace:
        marker = Path(workspace) / "hup-received"
        source = (
            "import pathlib,signal,sys,time;"
            f"signal.signal(signal.SIGHUP, lambda *a: pathlib.Path({str(marker)!r}).write_text('hup'));"
            "time.sleep(5)"
        )
        child = subprocess.Popen([sys.executable, "-c", source], start_new_session=True)
        try:
            time.sleep(0.3)
            require(bounded_run.group_exists(child.pid) is True, "an existing group must report as existing")
            time.sleep(0.2)
            require(not marker.exists(), "the existence probe must not deliver a real signal")
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait(timeout=3)


def check_group_exists_permission_denied_still_means_it_exists() -> None:
    require(bounded_run.group_exists(1) is True, "a permission-denied group must still report as existing")


# ------------------------------------------------------------------ stop_group


def check_stop_group_returns_quickly_once_sigterm_succeeds() -> None:
    process = subprocess.Popen(sleeper(30), start_new_session=True)
    started = time.monotonic()
    existed, terminal = bounded_run.stop_group(process, 2.0)
    elapsed = time.monotonic() - started
    require(existed is True, "a live group must report existed=True")
    require(terminal is True, "a group that dies to SIGTERM must be proven terminal")
    require(elapsed < 1.0, f"stop_group waited {elapsed:.2f}s for a process that died immediately")
    process.wait(timeout=5)


def check_stop_group_waits_the_full_grace_before_escalating() -> None:
    process = subprocess.Popen(ignoring_sigterm(30), start_new_session=True)
    time.sleep(0.15)
    started = time.monotonic()
    existed, terminal = bounded_run.stop_group(process, 0.4)
    elapsed = time.monotonic() - started
    require(existed is True, "...")
    require(terminal is True, "SIGKILL must eventually prove the group terminal")
    require(elapsed >= 0.35, f"stop_group escalated to SIGKILL after only {elapsed:.2f}s; grace was skipped")
    process.wait(timeout=5)


def check_stop_group_reports_permission_denied_group_as_not_terminal() -> None:
    existed, terminal = bounded_run.stop_group(cast("subprocess.Popen[bytes]", _FakeProcess(1)), 0.1)
    require(existed is True, "a permission-denied SIGTERM target still existed beforehand")
    require(terminal is False, "a group we cannot signal must never be reported terminal")


# --------------------------------------------------------------- _file_sha256


def check_file_sha256_matches_full_content_digest() -> None:
    with tempfile.TemporaryDirectory(prefix="sha256-") as workspace:
        target = Path(workspace) / "payload.bin"
        content = b"bounded-run-fixture-content" * 5000
        target.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        require(bounded_run._file_sha256(target) == expected, "digest must equal the true content hash")


def check_file_sha256_reads_in_exactly_one_mib_chunks() -> None:
    with tempfile.TemporaryDirectory(prefix="sha256-chunk-") as workspace:
        target = Path(workspace) / "payload.bin"
        target.write_bytes(b"x" * 10)
        sizes: list[int] = []

        class SpyStream:
            def __init__(self, real: IO[bytes]) -> None:
                self._real = real

            def read(self, size: int = -1, /) -> bytes:
                sizes.append(size)
                return self._real.read(size)

            def __enter__(self) -> Self:
                return self

            def __exit__(
                self,
                exc_type: type[BaseException] | None,
                exc_value: BaseException | None,
                exc_tb: TracebackType | None,
            ) -> None:
                self._real.__exit__(exc_type, exc_value, exc_tb)

        original_open = bounded_run.Path.open

        def spy_open(self, *a, **kw):
            return SpyStream(original_open(self, *a, **kw))

        bounded_run.Path.open = cast(Any, spy_open)
        try:
            bounded_run._file_sha256(target)
        finally:
            bounded_run.Path.open = original_open
        require(
            bool(sizes) and sizes[0] == 1024 * 1024, f"expected the first read to request exactly 1 MiB, got {sizes!r}"
        )


# ----------------------------------------------------------------- _fsync_directory


def check_fsync_directory_rejects_a_non_directory_target() -> None:
    with tempfile.NamedTemporaryFile() as handle:
        try:
            bounded_run._fsync_directory(Path(handle.name))
        except OSError:
            pass
        else:
            fail("fsync_directory must refuse a target that is not a directory")


# ------------------------------------------------------------ _executable_identity


def prepend_interpreter_to_path() -> tuple[str, str]:
    name = os.path.basename(sys.executable)
    interpreter_dir = os.path.dirname(sys.executable)
    previous_path = os.environ.get("PATH", "")
    os.environ["PATH"] = os.pathsep.join([interpreter_dir, previous_path])
    return name, previous_path


def check_executable_identity_resolves_via_path_lookup() -> None:
    import shutil

    name, previous_path = prepend_interpreter_to_path()
    try:
        found = shutil.which(name)
        if found is None:
            fail("fixture assumption: the interpreter must be discoverable on PATH")
        with tempfile.TemporaryDirectory(prefix="exe-identity-") as workspace:
            previous_cwd = Path.cwd()
            os.chdir(workspace)
            try:
                identity = bounded_run._executable_identity(name)
            finally:
                os.chdir(previous_cwd)
    finally:
        os.environ["PATH"] = previous_path
    expected_resolved = str(Path(found).resolve(strict=True))
    require(
        identity.startswith(expected_resolved + "@sha256:"),
        f"expected identity rooted at {expected_resolved!r}, got {identity!r}",
    )


def check_executable_identity_missing_command_names_it_in_the_error() -> None:
    missing = "definitely-not-a-real-command-xyz"
    try:
        bounded_run._executable_identity(missing)
    except FileNotFoundError as error:
        require(error.args == (missing,), f"expected FileNotFoundError({missing!r}), got args={error.args!r}")
    else:
        fail("a missing command must raise FileNotFoundError")


def check_executable_identity_resolves_with_strict_true() -> None:
    import shutil

    name, previous_path = prepend_interpreter_to_path()
    captured: list[object] = []
    original_resolve = bounded_run.Path.resolve

    def spy_resolve(self, *a, **kw):
        captured.append(kw.get("strict", a[0] if a else False))
        return original_resolve(self, *a, **kw)

    bounded_run.Path.resolve = spy_resolve
    try:
        require(shutil.which(name) is not None, "fixture assumption: the interpreter must be discoverable on PATH")
        bounded_run._executable_identity(name)
    finally:
        bounded_run.Path.resolve = original_resolve
        os.environ["PATH"] = previous_path
    require(captured == [True], f"_executable_identity must resolve with strict=True exactly once, got {captured!r}")


# -------------------------------------------------------------------- _redacted_argv


def digest_of(*parts: str) -> str:
    payload = "\0".join(parts).encode("utf-8", "surrogateescape")
    return hashlib.sha256(payload).hexdigest()


def check_redacted_argv_passthrough_for_plain_arguments() -> None:
    result = bounded_run._redacted_argv(["git", "status"])
    require(result == (2, digest_of("git", "status")), f"unexpected redaction of plain arguments: {result!r}")


def check_redacted_argv_option_flag_consumes_and_resets() -> None:
    command = ["git", "--token", "secret1", "trailing1", "trailing2"]
    expected = (5, digest_of("git", "<redacted-option>", "<redacted>", "trailing1", "trailing2"))
    require(
        bounded_run._redacted_argv(command) == expected,
        "the flagged value must be redacted and processing must continue",
    )


def check_redacted_argv_embedded_equals_does_not_flag_the_next_value() -> None:
    command = ["--token=embedded-secret", "harmless"]
    expected = (2, digest_of("<redacted-option>", "harmless"))
    require(
        bounded_run._redacted_argv(command) == expected, "an inline --opt=value must not redact the following argument"
    )


def check_redacted_argv_inline_pattern_redacts_without_matching_signed_url() -> None:
    command = ["plainarg1", "Authorization: secretvalue", "trailing"]
    expected = (3, digest_of("plainarg1", "<redacted>", "trailing"))
    require(
        bounded_run._redacted_argv(command) == expected,
        "inline sensitive text must be redacted via SENSITIVE_INLINE alone",
    )


def check_redacted_argv_invalid_utf8_round_trips_via_surrogateescape() -> None:
    raw = b"\xff\xfe"
    decoded = os.fsdecode(raw)
    expected = (1, digest_of(decoded))
    require(
        bounded_run._redacted_argv(cast("list[str]", [raw])) == expected,
        "surrogate-escaped bytes must hash cleanly, not crash",
    )


# ------------------------------------------------------------------------------ run


def check_run_returns_a_plain_run_result_type() -> None:
    result = bounded_run.run([sys.executable, "-c", "pass"], 5, 0.5)
    require(type(result) is RunResult, f"run() must return exactly RunResult, got {type(result)!r}")


def check_run_propagates_a_custom_environment() -> None:
    with tempfile.TemporaryDirectory(prefix="run-env-") as workspace:
        marker = Path(workspace) / "seen"
        script = (
            "import os,pathlib,sys;"
            f"pathlib.Path({str(marker)!r}).write_text(os.environ.get('BOUNDED_RUN_MARKER','absent'))"
        )
        env = {"BOUNDED_RUN_MARKER": "present", "PATH": os.environ.get("PATH", "")}
        result = bounded_run.run([sys.executable, "-c", script], 5, 0.5, env=env)
        require(result.returncode == 0, "env-propagation fixture must exit cleanly")
        require(marker.read_text(encoding="utf-8") == "present", "run() must forward its env argument to the child")


# ------------------------------------------------------------------------------ _run


def check_run_default_capture_output_is_false() -> None:
    result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5)
    require(type(result) is RunResult, f"omitting capture_output must default to no capture, got {type(result)!r}")


def check_run_captures_stdout_and_stderr_exactly() -> None:
    script = "import sys;sys.stdout.write('out-text');sys.stderr.write('err-text')"
    result = bounded_run._run([sys.executable, "-c", script], 5, 0.5, capture_output=True)
    expected = CapturedRunResult(0, True, b"out-text", b"err-text", False, False)
    require(result == expected, f"expected {expected!r}, got {result!r}")


def check_run_output_chunks_join_without_a_separator() -> None:
    original_drain = bounded_run._drain

    def fake_drain(stream, chunks, truncated):
        chunks.append(b"AAA")
        chunks.append(b"BBB")

    bounded_run.__dict__["_drain"] = fake_drain
    try:
        result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, capture_output=True)
    finally:
        bounded_run.__dict__["_drain"] = original_drain
    expected = CapturedRunResult(0, True, b"AAABBB", b"AAABBB", False, False)
    require(result == expected, f"multi-chunk output must join with no separator, got {result!r}")


def check_run_without_capture_returns_plain_result() -> None:
    result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, capture_output=False)
    require(result == RunResult(0, True), f"expected RunResult(0, True), got {result!r}")


def check_run_input_data_round_trips_through_stdin() -> None:
    script = "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"
    payload = b"bounded-run stdin payload\n"
    result = bounded_run._run([sys.executable, "-c", script], 5, 0.5, capture_output=True, input_data=payload)
    expected = CapturedRunResult(0, True, payload, b"", False, False)
    require(result == expected, f"input_data must round-trip through stdin, got {result!r}")


def check_run_stdin_fd_round_trips_through_stdin() -> None:
    with tempfile.TemporaryDirectory(prefix="run-stdinfd-") as workspace:
        payload = b"descriptor payload\n"
        source = Path(workspace) / "in.bin"
        source.write_bytes(payload)
        descriptor = os.open(source, os.O_RDONLY)
        try:
            script = "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"
            result = bounded_run._run([sys.executable, "-c", script], 5, 0.5, capture_output=True, stdin_fd=descriptor)
        finally:
            os.close(descriptor)
        expected = CapturedRunResult(0, True, payload, b"", False, False)
        require(result == expected, f"stdin_fd must round-trip through stdin, got {result!r}")


def check_run_rejects_both_input_data_and_stdin_fd() -> None:
    try:
        bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, input_data=b"x", stdin_fd=0)
    except ValueError as error:
        require(
            error.args == ("bounded input accepts bytes or a file descriptor, not both",),
            f"unexpected message: {error.args!r}",
        )
    else:
        fail("providing both input_data and stdin_fd must raise ValueError")


def check_run_accepts_input_data_alone() -> None:
    result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, input_data=b"only-data")
    require(result == RunResult(0, True), "input_data alone must not raise")


def check_run_accepts_stdin_fd_alone() -> None:
    result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, stdin_fd=os.open(os.devnull, os.O_RDONLY))
    require(result == RunResult(0, True), "stdin_fd alone must not raise")


def check_run_input_limit_boundary() -> None:
    at_limit = b"x" * bounded_run.INPUT_LIMIT_BYTES
    result = bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, input_data=at_limit)
    require(result == RunResult(0, True), "input exactly at the 64 KiB limit must be accepted")
    try:
        bounded_run._run([sys.executable, "-c", "pass"], 5, 0.5, input_data=at_limit + b"x")
    except ValueError as error:
        require(error.args == ("bounded input exceeds the 64 KiB limit",), f"unexpected message: {error.args!r}")
    else:
        fail("input one byte over the limit must raise ValueError")


def check_run_timeout_kills_and_reports_terminality_could_not_be_proven_false_case() -> None:
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        result = bounded_run._run(ignoring_sigterm(30), 0.3, 0.0)
    require(
        result == RunResult(bounded_run.TERMINALITY_EXIT, False), f"expected an unproven timeout result, got {result!r}"
    )
    require(
        captured.getvalue() == "bounded-run: TIMEOUT and process group terminality could not be proven\n",
        f"unexpected stderr: {captured.getvalue()!r}",
    )


def check_run_timeout_with_generous_grace_reports_clean_timeout() -> None:
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        result = bounded_run._run(ignoring_sigterm(30), 0.3, 1.0)
    require(result == RunResult(bounded_run.TIMEOUT_EXIT, True), f"expected a clean TIMEOUT result, got {result!r}")
    require(
        captured.getvalue() == "bounded-run: TIMEOUT after 0.3s; command group terminated\n",
        f"unexpected stderr: {captured.getvalue()!r}",
    )


def check_run_background_descendant_is_reported() -> None:
    with tempfile.TemporaryDirectory(prefix="run-bg-") as workspace:
        pid_path = Path(workspace) / "pid"
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            result = bounded_run._run(leaves_a_grandchild(pid_path), 5, 0.3)
        require(result == RunResult(bounded_run.BACKGROUND_EXIT, True), f"expected BACKGROUND result, got {result!r}")
        require(
            captured.getvalue() == "bounded-run: BACKGROUND descendant terminated after command exit\n",
            f"unexpected stderr: {captured.getvalue()!r}",
        )
        descendant = wait_pid(pid_path)
        try:
            os.killpg(descendant, signal.SIGKILL)
        except ProcessLookupError:
            pass


def check_run_normal_completion_with_zero_grace_can_be_unproven() -> None:
    with tempfile.TemporaryDirectory(prefix="run-unproven-") as workspace:
        pid_path = Path(workspace) / "pid"
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            result = bounded_run._run(leaves_a_grandchild(pid_path), 5, 0.0)
        require(
            result == RunResult(bounded_run.TERMINALITY_EXIT, False),
            f"expected an unproven cleanup result, got {result!r}",
        )
        require(
            captured.getvalue() == "bounded-run: process group terminality could not be proven\n",
            f"unexpected stderr: {captured.getvalue()!r}",
        )
        descendant = wait_pid(pid_path)
        try:
            os.killpg(descendant, signal.SIGKILL)
        except ProcessLookupError:
            pass


def check_run_output_truncation_is_reported_precisely() -> None:
    oversize = bounded_run.CAPTURE_LIMIT_BYTES + 4096
    script = f"import sys;sys.stdout.buffer.write(b'x' * {oversize})"
    result = bounded_run._run([sys.executable, "-c", script], 10, 0.5, capture_output=True)
    assert isinstance(result, CapturedRunResult)
    require(result.returncode == bounded_run.OUTPUT_LIMIT_EXIT, f"expected OUTPUT_LIMIT_EXIT, got {result.returncode}")
    require(result.stdout_truncated is True, "oversized stdout must be marked truncated")
    require(result.stderr_truncated is False, "stderr was never written and must not be marked truncated")
    require(len(result.stdout) == bounded_run.CAPTURE_LIMIT_BYTES, "retained stdout must be bounded to the exact cap")


def _send_signal_soon(pid: int, sig: int, delay: float = 0.15) -> None:
    def fire() -> None:
        time.sleep(delay)
        os.kill(pid, sig)

    thread = threading.Thread(target=fire, daemon=True)
    thread.start()


def check_run_interrupted_by_signal_returns_terminal_true() -> None:
    process_holder: dict[str, subprocess.Popen] = {}
    original_popen = subprocess.Popen

    def spy_popen(*args, **kwargs):
        process = original_popen(*args, **kwargs)
        process_holder["p"] = process
        return process

    subprocess.Popen = spy_popen
    try:
        _send_signal_soon(os.getpid(), signal.SIGTERM, 0.2)
        result = bounded_run._run(sleeper(30), 5, 1.0)
    finally:
        subprocess.Popen = original_popen
    expected = RunResult(128 + signal.SIGTERM, True)
    require(result == expected, f"expected {expected!r}, got {result!r}")


def check_run_interrupted_by_signal_when_group_cannot_be_proven_gone() -> None:
    captured = io.StringIO()
    with contextlib.redirect_stderr(captured):
        _send_signal_soon(os.getpid(), signal.SIGTERM, 0.2)
        result = bounded_run._run(ignoring_sigterm(30), 5, 0.0)
    expected = RunResult(128 + signal.SIGTERM, False)
    require(result == expected, f"expected {expected!r}, got {result!r}")
    require(
        captured.getvalue() == "bounded-run: process group terminality could not be proven\n",
        f"unexpected stderr: {captured.getvalue()!r}",
    )


def check_run_env_none_default_reaches_the_child() -> None:
    with tempfile.TemporaryDirectory(prefix="run-env2-") as workspace:
        marker = Path(workspace) / "seen"
        script = (
            "import os,pathlib;"
            f"pathlib.Path({str(marker)!r}).write_text('PATH' in os.environ and str('MARKER' in os.environ))"
        )
        env = {"PATH": os.environ.get("PATH", "")}
        result = bounded_run._run([sys.executable, "-c", script], 5, 0.5, env=env)
        require(result == RunResult(0, True), "...")
        require(marker.read_text(encoding="utf-8") == "False", "a custom env without MARKER must not see one")


def check_run_result_closure_uses_correct_thread_bookkeeping() -> None:
    original_thread_cls = bounded_run.threading.Thread

    class SpyThread(original_thread_cls):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            self.join_calls: list[float | None] = []
            created.append(self)

        def join(self, timeout=None):
            self.join_calls.append(timeout)
            super().join(timeout)

        def is_alive(self) -> bool:
            return True

    created: list[SpyThread] = []
    bounded_run.threading.Thread = SpyThread
    try:
        script = "import sys;sys.stdin.buffer.read();sys.stdout.write('x');sys.stderr.write('y')"
        result = bounded_run._run([sys.executable, "-c", script], 5, 0.37, capture_output=True, input_data=b"z")
    finally:
        bounded_run.threading.Thread = original_thread_cls
    require(len(created) == 3, f"expected 2 readers + 1 writer thread, got {len(created)}")
    require(
        all(t.daemon for t in created),
        f"every _run background thread must be a daemon, got {[t.daemon for t in created]!r}",
    )
    expected_join = max(0.37, 0.1)
    require(
        all(t.join_calls == [expected_join] for t in created),
        f"expected every thread joined with timeout={expected_join} exactly once, got {[t.join_calls for t in created]!r}",
    )
    expected = CapturedRunResult(bounded_run.TERMINALITY_EXIT, False, b"x", b"y", True, True)
    require(
        result == expected,
        f"forcing every background thread to report still-alive must yield {expected!r}, got {result!r}",
    )


def check_run_stdin_wiring_matches_the_actual_data_source() -> None:
    with tempfile.TemporaryDirectory(prefix="run-stdinwire-") as workspace:
        source = Path(workspace) / "descriptor-source.bin"
        source.write_bytes(b"from-descriptor")
        descriptor = os.open(source, os.O_RDONLY)
        try:
            script = "import sys;sys.stdout.buffer.write(sys.stdin.buffer.read())"
            with_data = bounded_run._run(
                [sys.executable, "-c", script], 5, 0.5, capture_output=True, input_data=b"from-bytes"
            )
        finally:
            os.close(descriptor)
        require(
            with_data == CapturedRunResult(0, True, b"from-bytes", b"", False, False),
            f"input_data must take priority over stdin_fd wiring, got {with_data!r}",
        )


def main() -> int:
    check_group_exists_probe_sends_no_real_signal()
    check_group_exists_permission_denied_still_means_it_exists()
    check_stop_group_returns_quickly_once_sigterm_succeeds()
    check_stop_group_waits_the_full_grace_before_escalating()
    check_stop_group_reports_permission_denied_group_as_not_terminal()
    check_file_sha256_matches_full_content_digest()
    check_file_sha256_reads_in_exactly_one_mib_chunks()
    check_fsync_directory_rejects_a_non_directory_target()
    check_executable_identity_resolves_via_path_lookup()
    check_executable_identity_resolves_with_strict_true()
    check_executable_identity_missing_command_names_it_in_the_error()
    check_redacted_argv_passthrough_for_plain_arguments()
    check_redacted_argv_option_flag_consumes_and_resets()
    check_redacted_argv_embedded_equals_does_not_flag_the_next_value()
    check_redacted_argv_inline_pattern_redacts_without_matching_signed_url()
    check_redacted_argv_invalid_utf8_round_trips_via_surrogateescape()
    check_run_returns_a_plain_run_result_type()
    check_run_propagates_a_custom_environment()
    check_run_default_capture_output_is_false()
    check_run_captures_stdout_and_stderr_exactly()
    check_run_output_chunks_join_without_a_separator()
    check_run_without_capture_returns_plain_result()
    check_run_input_data_round_trips_through_stdin()
    check_run_stdin_fd_round_trips_through_stdin()
    check_run_rejects_both_input_data_and_stdin_fd()
    check_run_accepts_input_data_alone()
    check_run_accepts_stdin_fd_alone()
    check_run_input_limit_boundary()
    check_run_timeout_kills_and_reports_terminality_could_not_be_proven_false_case()
    check_run_timeout_with_generous_grace_reports_clean_timeout()
    check_run_background_descendant_is_reported()
    check_run_normal_completion_with_zero_grace_can_be_unproven()
    check_run_output_truncation_is_reported_precisely()
    check_run_interrupted_by_signal_returns_terminal_true()
    check_run_interrupted_by_signal_when_group_cannot_be_proven_gone()
    check_run_env_none_default_reaches_the_child()
    check_run_result_closure_uses_correct_thread_bookkeeping()
    check_run_stdin_wiring_matches_the_actual_data_source()
    print("bounded-run-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Regression checks that kill the surviving mutants of dart_decimate_gate.py."""

from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Literal, Self

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regression_fixture import checker

fail, require = checker("dart-decimate-gate-survivors")

import dart_decimate_gate


def load_gate() -> Any:
    return dart_decimate_gate


class FakeCaptured:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def check_git(module: Any) -> None:
    calls: list[tuple[list[str], Any]] = []

    def spy(command: list[str], timeout: Any, env: Any = None) -> FakeCaptured:
        calls.append((command, timeout))
        return FakeCaptured(0, b"out-data", b"err-data")

    original = module.run_captured
    module.run_captured = spy
    try:
        result = module.git(Path("/pkg"), "status")
        require(calls[-1][1] == 20, f"default git timeout drifted: {calls[-1][1]!r}")
        require(result.args == ["git", "-C", "/pkg", "status"], f"git command args drifted: {result.args!r}")
        require(result.returncode == 0, "git result lost its return code")
        require(result.stdout == "out-data", f"git result lost its stdout: {result.stdout!r}")
        require(result.stderr == "err-data", f"git result lost its stderr: {result.stderr!r}")

        module.git(Path("/pkg"), "status", timeout=5)
        require(calls[-1][1] == 5, f"explicit git timeout drifted: {calls[-1][1]!r}")

        module.run_captured = lambda *a, **k: FakeCaptured(module.TIMEOUT_EXIT)
        try:
            module.git(Path("/pkg"), "status")
        except TimeoutError as error:
            require(str(error) == "Git command deadline exhausted", f"unexpected timeout message: {error}")
        else:
            fail("git did not raise TimeoutError on deadline exhaustion")

        module.run_captured = lambda *a, **k: FakeCaptured(0, b"\xff\xfe", b"")
        result3 = module.git(Path("/pkg"), "status")
        require(result3.stdout == "��", f"git result mis-decoded invalid utf-8: {result3.stdout!r}")
    finally:
        module.run_captured = original


def check_repository_root(module: Any) -> None:
    calls: list[tuple[Any, Any]] = []
    remaining_calls: list[tuple[Any, Any]] = []

    class GitResult:
        def __init__(self, returncode: int, stdout: str) -> None:
            self.returncode = returncode
            self.stdout = stdout

    def fake_git(package: Any, *args: Any, timeout: Any = None) -> GitResult:
        calls.append((args, timeout))
        return GitResult(0, "/repo/root\n")

    def fake_remaining(deadline: Any, label: str) -> float:
        remaining_calls.append((deadline, label))
        return 99.0

    original_git, original_remaining = module.git, module.remaining
    module.git, module.remaining = fake_git, fake_remaining
    try:
        deadline_sentinel = object()
        result = module.repository_root(Path("/pkg"), deadline_sentinel)
        require(
            remaining_calls == [(deadline_sentinel, "during repository discovery")],
            f"remaining() call inside repository_root drifted: {remaining_calls}",
        )
        require(calls[-1][1] == 99.0, f"repository_root did not forward the computed timeout: {calls[-1]}")
        require(result == Path("/repo/root").resolve(), f"repository_root mis-parsed the toplevel path: {result!r}")

        def fake_git_fail(package: Any, *args: Any, timeout: Any = None) -> GitResult:
            return GitResult(1, "")

        module.git = fake_git_fail
        require(
            module.repository_root(Path("/pkg"), deadline_sentinel) is None,
            "repository_root did not report a non-zero git exit as None",
        )
    finally:
        module.git, module.remaining = original_git, original_remaining


def run_main(module: Any, argv: list[str], script: str = "dart_decimate_gate.py") -> tuple[int, str, str]:
    old_argv = sys.argv
    sys.argv = [script, *argv]
    stdout, stderr = io.StringIO(), io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main()
    finally:
        sys.argv = old_argv
    return code, stdout.getvalue(), stderr.getvalue()


def check_main_early_exits(module: Any) -> None:
    with tempfile.TemporaryDirectory(prefix="dart-decimate-early-") as temporary:
        root = Path(temporary).resolve()
        (root / "pubspec.yaml").write_text("name: pkg\n", encoding="utf-8")

        stderr = io.StringIO()
        old_argv = sys.argv
        sys.argv = ["dart_decimate_gate.py", "--package", str(root)]
        try:
            with contextlib.redirect_stderr(stderr):
                module.main()
        except SystemExit as exc:
            require(exc.code == 2, f"--timeout stopped being required: {exc.code}")
        else:
            fail("--timeout stopped being required by the parser")
        finally:
            sys.argv = old_argv

        for bad in ("nan", "-1", "0"):
            code, _out, err = run_main(module, ["--package", str(root), "--timeout", bad])
            require(code == 2, f"--timeout {bad} should be rejected")
            require(
                err.strip() == "Dart Decimate gate: --timeout must be finite and positive",
                f"unexpected message for --timeout {bad}: {err.strip()!r}",
            )

        code, _out, err = run_main(module, ["--package", str(root), "--timeout", "1"])
        require(
            err.strip() == "Dart Decimate gate: package is not inside a Git repository",
            f"--timeout 1 should pass the positivity check: {err.strip()!r}",
        )

        empty_dir = Path(temporary) / "no-pubspec"
        empty_dir.mkdir()
        code, _out, err = run_main(module, ["--package", str(empty_dir), "--timeout", "10"])
        require(
            err.strip() == "Dart Decimate gate: --package must be a Dart package directory",
            f"missing pubspec.yaml should fail: {err.strip()!r}",
        )

        old_cwd = Path.cwd()
        os.chdir(root)
        try:
            code, _out, err = run_main(module, ["--timeout", "1"])
        finally:
            os.chdir(old_cwd)
        require(
            err.strip() == "Dart Decimate gate: package is not inside a Git repository",
            f"the default --package should resolve to the current directory: {err.strip()!r}",
        )

        original_repository_root = module.repository_root

        def raise_timeout(package: Any, deadline: Any) -> None:
            raise TimeoutError("x")

        module.repository_root = raise_timeout
        try:
            code, _out, err = run_main(module, ["--package", str(root), "--timeout", "10"])
        finally:
            module.repository_root = original_repository_root
        require(
            err.strip() == "Dart Decimate gate: whole-run timeout exhausted during repository discovery",
            f"unexpected message on repository-discovery timeout: {err.strip()!r}",
        )

        module.repository_root = lambda package, deadline: None
        try:
            code, _out, err = run_main(module, ["--package", str(root), "--timeout", "10"])
        finally:
            module.repository_root = original_repository_root
        require(
            err.strip() == "Dart Decimate gate: package is not inside a Git repository",
            f"unexpected message when repository_root is None: {err.strip()!r}",
        )

        sibling = Path(temporary) / "sibling"
        sibling.mkdir()
        module.repository_root = lambda package, deadline: sibling.resolve()
        try:
            code, _out, err = run_main(module, ["--package", str(root), "--timeout", "10"])
        finally:
            module.repository_root = original_repository_root
        require(
            err.strip() == "Dart Decimate gate: package resolves outside the Git repository",
            f"unexpected message when the package is outside the resolved root: {err.strip()!r}",
        )


class Rig:
    def __init__(self, module: Any, package: Path) -> None:
        self.module = module
        self.package = package
        self.calls: dict[str, list[Any]] = {
            "source_tree_lock": [],
            "validate_external_npx": [],
            "tree_fingerprint": [],
            "remaining": [],
            "consume_terminal_receipt": [],
            "run_bounded_process": [],
        }
        self.repository_root_result: Path = package
        self.fingerprint_values: list[str] = ["HASH", "HASH"]
        self.remaining_value = 1000.0
        self.bounded_returncode = 0
        self.monotonic_values: list[float] = [0.0, 0.0, 0.06]
        self._monotonic_index = 0
        self._originals: dict[str, Any] = {}

    def _fake_repository_root(self, package: Any, deadline: Any) -> Path:
        return self.repository_root_result

    def _fake_source_tree_lock(self, root: Any, *, exclusive: bool, deadline: Any, allow_poison: bool = False) -> Any:
        self.calls["source_tree_lock"].append({"root": root, "exclusive": exclusive, "deadline": deadline})

        @contextlib.contextmanager
        def cm() -> Any:
            yield Path("/fake-lock")

        return cm()

    def _fake_validate_external_npx(self, root: Any, *, deadline: Any = None) -> Path:
        self.calls["validate_external_npx"].append({"root": root, "deadline": deadline})
        return Path("/fake/npx")

    def _fake_tree_fingerprint(self, root: Any, *, deadline: Any = None) -> str:
        index = len(self.calls["tree_fingerprint"])
        self.calls["tree_fingerprint"].append({"root": root, "deadline": deadline})
        return self.fingerprint_values[min(index, len(self.fingerprint_values) - 1)]

    def _fake_remaining(self, deadline: Any, label: str) -> float:
        self.calls["remaining"].append({"deadline": deadline, "label": label})
        return self.remaining_value

    def _fake_terminal_receipt_spec(self, root: Any) -> tuple[Path, str]:
        return Path("/fake/receipt.json"), "faketoken"

    def _fake_consume_terminal_receipt(self, path: Any, token: Any) -> None:
        self.calls["consume_terminal_receipt"].append({"path": path, "token": token})

    def _fake_run_bounded_process(self, argv: list[str], timeout: float, *, grace: Any = None, env: Any = None) -> Any:
        self.calls["run_bounded_process"].append({"argv": argv, "timeout": timeout, "grace": grace})

        class Result:
            def __init__(self, returncode: int) -> None:
                self.returncode = returncode

        return Result(self.bounded_returncode)

    def _fake_monotonic(self) -> float:
        index = self._monotonic_index
        self._monotonic_index += 1
        if index >= len(self.monotonic_values):
            fail("dart_decimate_gate.main called time.monotonic() more times than the rig expected")
        return self.monotonic_values[index]

    def __enter__(self) -> Self:
        module = self.module
        self._originals = {
            "repository_root": module.repository_root,
            "source_tree_lock": module.source_tree_lock,
            "validate_external_npx": module.validate_external_npx,
            "tree_fingerprint": module.tree_fingerprint,
            "remaining": module.remaining,
            "terminal_receipt_spec": module.terminal_receipt_spec,
            "consume_terminal_receipt": module.consume_terminal_receipt,
            "run_bounded_process": module.run_bounded_process,
        }
        self._original_monotonic = time.monotonic
        module.repository_root = self._fake_repository_root
        module.source_tree_lock = self._fake_source_tree_lock
        module.validate_external_npx = self._fake_validate_external_npx
        module.tree_fingerprint = self._fake_tree_fingerprint
        module.remaining = self._fake_remaining
        module.terminal_receipt_spec = self._fake_terminal_receipt_spec
        module.consume_terminal_receipt = self._fake_consume_terminal_receipt
        module.run_bounded_process = self._fake_run_bounded_process
        self._monotonic_index = 0
        time.monotonic = self._fake_monotonic
        return self

    def __exit__(self, *exc: object) -> Literal[False]:
        module = self.module
        for name, value in self._originals.items():
            setattr(module, name, value)
        time.monotonic = self._original_monotonic
        return False


def check_main_full_run(module: Any) -> None:
    with tempfile.TemporaryDirectory(prefix="dart-decimate-full-") as temporary:
        root = Path(temporary).resolve()
        (root / "pubspec.yaml").write_text("name: pkg\n", encoding="utf-8")
        base_argv = ["--package", str(root), "--timeout", "500"]

        rig = Rig(module, root)
        with rig:
            code, _out, err = run_main(module, base_argv)
        require(code == 0, f"the fully mocked success path did not return 0: {err}")
        require(
            rig.calls["remaining"] == [{"deadline": 500.0, "label": "before Dart Decimate"}],
            f"remaining() call drifted: {rig.calls['remaining']}",
        )
        require(
            rig.calls["validate_external_npx"] == [{"root": root, "deadline": 500.0}],
            f"validate_external_npx call drifted: {rig.calls['validate_external_npx']}",
        )
        require(len(rig.calls["tree_fingerprint"]) == 2, "tree_fingerprint should be called exactly twice")
        require(
            rig.calls["tree_fingerprint"][0] == {"root": root, "deadline": 500.0},
            f"first tree_fingerprint call drifted: {rig.calls['tree_fingerprint'][0]}",
        )
        require(
            rig.calls["tree_fingerprint"][1] == {"root": root, "deadline": 500.0},
            f"second tree_fingerprint call drifted: {rig.calls['tree_fingerprint'][1]}",
        )
        require(
            rig.calls["source_tree_lock"] == [{"root": root, "exclusive": False, "deadline": 500.0}],
            f"source_tree_lock call drifted: {rig.calls['source_tree_lock']}",
        )
        require(len(rig.calls["run_bounded_process"]) == 1, "run_bounded_process should be called exactly once")
        bounded_call = rig.calls["run_bounded_process"][0]
        require(bounded_call["timeout"] == 1003.88, f"outer bounded timeout drifted: {bounded_call['timeout']!r}")
        require(bounded_call["grace"] == 2, f"outer bounded grace drifted: {bounded_call['grace']!r}")
        argv_list = bounded_call["argv"]
        require("--timeout" in argv_list, "bounded argv lost --timeout")
        inner_timeout = argv_list[argv_list.index("--timeout") + 1]
        require(inner_timeout == "994.88", f"inner command timeout drifted: {inner_timeout!r}")
        inner_grace = argv_list[argv_list.index("--grace") + 1]
        require(inner_grace == "2.0", f"inner grace drifted: {inner_grace!r}")
        tail = ["npx", "--yes", "dart-decimate@latest", "json", str(root)]
        require(argv_list[-len(tail) :] == tail, f"npx command tail drifted: {argv_list}")
        require(
            rig.calls["consume_terminal_receipt"] == [{"path": Path("/fake/receipt.json"), "token": "faketoken"}],
            "consume_terminal_receipt call drifted",
        )

        rig_zero = Rig(module, root)
        rig_zero.remaining_value = 100.0
        rig_zero.monotonic_values = [1000.0, 0.0, 47.5]
        with rig_zero:
            code_zero, _out, err_zero = run_main(module, base_argv)
        require(code_zero == 2, f"a zero command budget should fail: {err_zero}")
        require(
            err_zero.strip() == "Dart Decimate gate: whole-run timeout has no command and shutdown headroom",
            f"unexpected zero-budget message: {err_zero.strip()!r}",
        )
        require(rig_zero.calls["run_bounded_process"] == [], "run_bounded_process should not run on a zero budget")

        rig_small = Rig(module, root)
        rig_small.remaining_value = 0.36
        rig_small.monotonic_values = [1000.0, 0.0, 0.0]
        with rig_small:
            code_small, _out, err_small = run_main(module, base_argv)
        require(code_small == 0, f"a small but positive command budget should still succeed: {err_small}")

        rig_mutated = Rig(module, root)
        rig_mutated.fingerprint_values = ["HASH_BEFORE", "HASH_AFTER"]
        with rig_mutated:
            code_mutated, _out, err_mutated = run_main(module, base_argv)
        require(code_mutated == 2, f"a changed tree fingerprint should fail: {err_mutated}")
        require(
            err_mutated.strip() == "Dart Decimate gate: Dart Decimate mutated the repository tree",
            f"unexpected mutated-tree message: {err_mutated.strip()!r}",
        )


def main() -> int:
    module = load_gate()
    check_git(module)
    check_repository_root(module)
    check_main_early_exits(module)
    check_main_full_run(module)
    print("dart-decimate-gate-survivors: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

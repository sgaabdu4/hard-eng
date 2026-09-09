#!/usr/bin/env python3
"""Regression: run_script gives one result shape in child and in-process modes and leaves the process untouched."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR)]

import script_runner
from script_runner import INPROCESS_FLAG, ScriptRunnerError, run_script

PROBE = SCRIPT_DIR / "script_runner_probe.py"


def fail(label: str) -> None:
    print(f"script-runner regression: FAIL ({label})")
    raise SystemExit(1)


def require(condition: bool, label: str) -> None:
    if not condition:
        fail(label)


def with_mode(value: str | None) -> dict[str, str]:
    env = dict(os.environ)
    env.pop(INPROCESS_FLAG, None)
    if value is not None:
        env[INPROCESS_FLAG] = value
    return env


def run_mode(
    mode: str | None, *args: str, stdin: str | None = None, cwd: str | None = None
) -> script_runner.ScriptResult:
    saved = os.environ.get(INPROCESS_FLAG)
    if mode is None:
        os.environ.pop(INPROCESS_FLAG, None)
    else:
        os.environ[INPROCESS_FLAG] = mode
    try:
        return run_script(PROBE, args, env=with_mode(mode), stdin=stdin, cwd=cwd)
    finally:
        if saved is None:
            os.environ.pop(INPROCESS_FLAG, None)
        else:
            os.environ[INPROCESS_FLAG] = saved


def check_inprocess_exit_codes() -> None:
    ok = run_mode("1", "exit", "0")
    require(ok.returncode == 0 and ok.stdout == "exit 0\n", f"zero exit: {ok!r}")
    failed = run_mode("1", "exit", "3")
    require(failed.returncode == 3 and failed.stdout == "exit 3\n", f"nonzero exit: {failed!r}")
    message = run_mode("1", "die")
    require(message.returncode == 1 and message.stderr == "probe died\n", f"SystemExit message: {message!r}")
    crashed = run_mode("1", "crash")
    require(crashed.returncode == 1 and "ValueError: boom" in crashed.stderr, f"exception: {crashed!r}")


def check_stdin() -> None:
    got = run_mode("1", "echo", stdin="payload")
    require(got.returncode == 0 and got.stdout == "stdin=payload\n", f"stdin payload: {got!r}")
    empty = run_mode("1", "echo")
    require(empty.stdout == "stdin=\n", f"missing stdin reads empty: {empty!r}")


def check_state_restored(base: Path) -> None:
    before = (sys.argv[:], os.getcwd(), dict(os.environ), sys.stdin, sys.stdout, sys.stderr)
    result = run_mode("1", "mutate", cwd=str(base))
    require(result.returncode == 0, f"mutate probe: {result!r}")
    require(f"cwd={base}" in result.stdout, f"probe ran in the requested cwd: {result.stdout!r}")
    after = (sys.argv[:], os.getcwd(), dict(os.environ), sys.stdin, sys.stdout, sys.stderr)
    require(before == after, "argv, cwd, environment, and streams must be restored")
    require("PROBE_LEAK" not in os.environ, "environment change leaked")


def check_child_fallback() -> None:
    child = run_mode(None, "exit", "3")
    inproc = run_mode("1", "exit", "3")
    require(
        (child.returncode, child.stdout, child.stderr) == (inproc.returncode, inproc.stdout, inproc.stderr),
        "child and in-process results differ",
    )
    identity = run_mode(None, "pid")
    require(identity.stdout.strip() != str(os.getpid()), "child mode must use a separate process")
    piped = run_mode(None, "echo", stdin="payload")
    require(piped.stdout == "stdin=payload\n", f"child mode must pass stdin: {piped!r}")
    same = run_mode("1", "pid")
    require(same.stdout.strip() == str(os.getpid()), "in-process mode must run in this process")


def check_child_guard() -> None:
    script_runner.install_child_guard()
    try:
        subprocess.run([sys.executable, str(PROBE), "exit", "0"], check=False, capture_output=True)
    except ScriptRunnerError as error:
        require(
            "use run_script" in str(error) and "script_runner_regression_check.py" in str(error),
            f"guard message: {error}",
        )
    else:
        fail("child run of a repository script must be refused")
    allowed = subprocess.run([sys.executable, "-c", "print('ok')"], check=False, capture_output=True, text=True)
    require(allowed.stdout == "ok\n", "non-repository python command must still run")
    nested = run_mode("1", "spawn")
    require(
        nested.returncode == 0 and nested.stdout == "exit 0\n",
        f"a repository script may still spawn another: {nested!r}",
    )


def check_dotted_names() -> None:
    require(
        script_runner.dotted_name(PROBE) == "skills.deterministic-checks.scripts.script_runner_probe", "dotted name"
    )
    require(script_runner.repository_script(PROBE), "probe is a repository script")
    require(not script_runner.repository_script(Path("/tmp/other.py")), "outside path is not a repository script")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="script-runner-regression-") as directory:
        check_inprocess_exit_codes()
        check_stdin()
        check_state_restored(Path(directory).resolve())
        check_child_fallback()
        check_child_guard()
        check_dotted_names()
    print("script-runner regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

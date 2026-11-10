import json
import os
import re
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from typing import IO

import pytest
from conftest import SOURCE, gate, gone

# A test run under nohup hands down an ignored SIGHUP, which `check` keeps on purpose.
DEFAULT_SIGHUP = (
    "import os, signal, sys; signal.signal(signal.SIGHUP, signal.SIG_DFL); "
    "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])"
)
TESTS_DRIVER = """
import importlib.util, sys, threading
sys.path.insert(0, ".hooks")
spec = importlib.util.spec_from_file_location("runner", ".hooks/hard-eng.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
from gate_schedule import run_checks
from process_group import exit_when_stopped
group = {{"path": ".", "language": "python", "sources": ["main.py"]}}
exit_when_stopped()
run_checks(
    [(group, {gate!r})],
    lambda group, gate: runner.run_gate(group, gate, 60, threading.Lock(), [group], None),
    [],
)
"""
SLOW_GATE = """
import os, pathlib, time
pathlib.Path(os.environ["MARKER"]).write_text(str(os.getpid()))
time.sleep(60)
"""


def start_check(
    tmp_path: Path,
    completed_plan: str,
    shared: list[dict[str, object]],
    stdout: int | IO[str],
    driver: str | None = None,
) -> tuple[subprocess.Popen[bytes], Path]:
    marker, project = tmp_path / "gate.pid", tmp_path / "project"
    hooks = project / ".hooks"
    hooks.mkdir(parents=True)
    for source in (SOURCE / ".hooks").glob("*.py"):
        (hooks / source.name).write_bytes(source.read_bytes())
    subprocess.run(["git", "init", "-q", str(project)], check=True)
    (project / "PLAN.md").write_text(completed_plan)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (project / name).write_text((SOURCE / name).read_text())
    (project / "main.py").write_text("")
    (project / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": shared})
    )
    arguments = ["-c", driver] if driver else [str(hooks / "hard-eng.py"), "check"]
    check = subprocess.Popen(
        [sys.executable, "-c", DEFAULT_SIGHUP, *arguments],
        cwd=project,
        env={**os.environ, "MARKER": str(marker)},
        stdout=stdout,
        stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 60
    while not (marker.exists() and marker.read_text()):
        if time.monotonic() > deadline:
            check.kill()
            raise AssertionError("gate did not start")
        time.sleep(0.05)
    return check, marker


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGHUP])
def test_a_stopped_check_stops_its_gates(
    tmp_path: Path, completed_plan: str, signal_number: int
) -> None:
    slow = gate("slow", SLOW_GATE, role="custom", parallel=True)
    check, marker = start_check(tmp_path, completed_plan, [slow], subprocess.DEVNULL)
    stopped = False
    try:
        check.send_signal(signal_number)
        check.wait(timeout=30)
        stopped = gone(marker)
    finally:
        check.kill()
        if not stopped and marker.exists() and marker.read_text():
            with suppress(ProcessLookupError):
                os.kill(int(marker.read_text()), signal.SIGKILL)
    assert stopped, "the gate kept running after the check was stopped"


def test_a_stopped_check_says_that_it_was_stopped(
    tmp_path: Path, completed_plan: str
) -> None:
    slow = {
        **gate("tests", SLOW_GATE, role="tests", parallel=True),
        "command": [sys.executable, "-c", SLOW_GATE, "-n", "auto"],
        "report": {
            "type": "python-tests",
            "tests": "coverage/junit.xml",
            "coverage": "coverage/coverage.json",
        },
    }
    log = tmp_path / "check.log"
    with log.open("w") as stdout:
        check, marker = start_check(
            tmp_path, completed_plan, [], stdout, TESTS_DRIVER.format(gate=slow)
        )
        try:
            check.send_signal(signal.SIGTERM)
            check.wait(timeout=30)
        finally:
            check.kill()
            if marker.exists() and marker.read_text():
                with suppress(ProcessLookupError):
                    os.kill(int(marker.read_text()), signal.SIGKILL)
    output = log.read_text()
    assert re.search(r"^FAIL tests \(exit -9;", output, re.MULTILINE)
    assert "The check was stopped by SIGTERM" in output
    assert "ran in parallel" not in output

"""A passing test or performance command that wrote no JUnit report fails with a text that names the step."""

import threading
from pathlib import Path
from types import ModuleType
from typing import cast

import agent_hooks
import debt
import pytest
from conftest import gate
from gate_config import Gate, Group


MISSING_REPORT = (
    "The command passed but wrote no JUnit report ({report}). Make the command of this "
    "gate write its JUnit report to the `report` path that hard-eng.gates.json gives "
    "for this gate."
)


def silent_gates() -> list[tuple[Gate, str]]:
    tests = gate(
        "tests",
        "pass",
        role="tests",
        report={
            "type": "python-tests",
            "tests": "coverage/junit.xml",
            "coverage": "coverage/coverage.json",
        },
    )
    performance = gate(
        "performance",
        "pass",
        role="performance",
        report={"type": "performance-junit", "path": "coverage/performance.xml"},
    )
    return [
        (cast(Gate, tests), "coverage/junit.xml"),
        (cast(Gate, performance), "coverage/performance.xml"),
    ]


@pytest.mark.parametrize("index", [0, 1])
def test_a_missing_junit_report_names_the_report_and_the_step(
    runner: ModuleType,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    index: int,
) -> None:
    (tmp_path / "main.py").write_text("value = 1\n")
    check, report = silent_gates()[index]
    package: Group = {
        "path": ".",
        "language": "python",
        "sources": ["main.py"],
        "checks": [check],
    }
    assert runner.run_gate(package, check, 5, threading.Lock()) is True
    line = next(
        text for text in capsys.readouterr().out.splitlines() if "FAIL " in text
    )
    assert MISSING_REPORT.format(report=report) in line
    assert "[Errno" not in line
    assert agent_hooks.FAILED_COMMAND_LINE.search(line)


def test_a_missing_junit_report_is_never_recorded_as_debt(
    runner: ModuleType, tmp_path: Path
) -> None:
    check, _ = silent_gates()[1]
    package: Group = {"path": ".", "checks": [check]}
    runner.RECORDING.set()
    try:
        assert runner.run_gate(package, check, 5, threading.Lock()) is True
    finally:
        runner.RECORDING.clear()
    recorded = debt.record(tmp_path, [package], set(runner.FAILED_GATES), debt.OUTPUTS)
    assert recorded == 1
    assert "./performance" not in debt.load(tmp_path)
    assert runner.run_gate(package, check, 5, threading.Lock()) is True

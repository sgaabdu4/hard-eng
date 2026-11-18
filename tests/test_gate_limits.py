"""A gate limit follows the slowest recent passing times and widens after a stop at the limit."""

import json
import subprocess
import threading
import time
from pathlib import Path
from types import ModuleType

import debt
import gate_times
import pytest
from conftest import configure, gate, hang_one_check, pass_one_check


def init_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    monkeypatch.setattr(gate_times, "GATE_FLOOR_SECONDS", 1)


def test_one_fast_pass_does_not_shrink_the_limit_below_a_slower_recent_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    for seconds in (900, 180):
        gate_times.record_gate_time(tmp_path, "./suite", seconds)
    assert gate_times.gate_limit(tmp_path, "./suite", 5000) == 2700
    assert gate_times.gate_limit(tmp_path, "./suite", 1000) == 1000


def test_only_the_last_five_passing_times_set_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    for seconds in (900, 10, 10, 10, 10, 10):
        gate_times.record_gate_time(tmp_path, "./suite", seconds)
    assert gate_times.gate_limit(tmp_path, "./suite", 5000) == 30


def test_a_gate_that_timed_out_gets_the_full_budget_until_it_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    gate_times.record_gate_time(tmp_path, "./suite", 2)
    assert gate_times.gate_limit(tmp_path, "./suite", 100) == 6
    gate_times.record_gate_timeout(tmp_path, "./suite")
    assert gate_times.gate_limit(tmp_path, "./suite", 100) == 100
    assert gate_times.gate_limit(tmp_path, "./other", 100) == 100
    gate_times.record_gate_time(tmp_path, "./suite", 2)
    assert gate_times.gate_limit(tmp_path, "./suite", 100) == 6


def test_a_file_with_one_number_for_each_gate_still_loads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    path = tmp_path / ".git/hard-eng-gate-times.json"
    path.write_text(json.dumps({"./suite": 20.5}))
    assert gate_times.gate_limit(tmp_path, "./suite", 1000) == 61.5
    gate_times.record_gate_time(tmp_path, "./suite", 40)
    assert gate_times.gate_limit(tmp_path, "./suite", 1000) == 120


def test_a_gate_with_no_record_gets_the_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    gate_times.record_gate_time(tmp_path, "./suite", 2)
    assert gate_times.gate_limit(tmp_path, "./other", 100) == 100


def test_a_gate_stopped_at_its_limit_gets_the_full_budget_next_time(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pass_one_check(runner, tmp_path, monkeypatch)
    hang_one_check(tmp_path)
    assert runner.check(timeout=120) == 1
    assert gate_times.gate_limit(tmp_path, "./suite", 120) == 120


def pass_it(*_: object) -> bool:
    return False


def test_a_stop_at_the_limit_fails_the_check_when_the_debt_judge_calls_the_gate_a_pass(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pass_one_check(runner, tmp_path, monkeypatch)

    monkeypatch.setattr(debt, "judge", pass_it)
    hang_one_check(tmp_path)
    assert runner.check(timeout=120) == 1
    assert gate_times.gate_limit(tmp_path, "./suite", 120) == 120


def test_a_slow_start_is_not_a_stop_at_the_limit(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gate_times, "GATE_FLOOR_SECONDS", 1)
    gate_times.record_gate_time(tmp_path, "./suite", 0.1)
    prepared = runner.prepared_command

    def slow_start(*arguments: object) -> list[str]:
        time.sleep(1.5)
        return prepared(*arguments)

    monkeypatch.setattr(runner, "prepared_command", slow_start)
    monkeypatch.setattr(debt, "judge", pass_it)
    configure(tmp_path, [gate("suite", "raise SystemExit(1)")])
    assert runner.check(timeout=120) == 0
    assert gate_times.gate_limit(tmp_path, "./suite", 120) < 120


def test_a_check_in_another_process_cannot_lose_a_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    init_repository(tmp_path, monkeypatch)
    gate_times.record_gate_time(tmp_path, "./suite", 2)
    with gate_times.lock_gate_times(tmp_path):
        writer = threading.Thread(
            target=gate_times.record_gate_timeout, args=(tmp_path, "./suite")
        )
        writer.start()
        writer.join(timeout=0.5)
        assert writer.is_alive()
    writer.join(timeout=60)
    assert gate_times.gate_limit(tmp_path, "./suite", 100) == 100

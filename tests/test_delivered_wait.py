"""The delivered stage waits for a base branch check that is not done, up to `ci_seconds`."""

from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest
import shipping
from test_shipping import _PR_URL, FakeGitHub, Fixture, _check, _fixture, _pull
from test_shipping_delivered import _PUSH_SUITE, _delivered_fake, _run_of, _verify

_RUNNING = {"status": "in_progress", "conclusion": None, "completed_at": None}


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []
        self.after: Callable[[int], None] = lambda _count: None

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
        self.after(len(self.slept))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> Clock:
    fake = Clock()
    monkeypatch.setattr(shipping, "time", fake)
    return fake


def _answer(fixture: Fixture, *runs: dict[str, object]) -> None:
    fake = cast(FakeGitHub, shipping.gh)
    checks = [{**run, "head_sha": fixture.head} for run in runs]
    fake.check_payload = [{"total_count": len(checks), "check_runs": checks}]


def _running() -> dict[str, object]:
    return {**_run_of(_PUSH_SUITE, 1, "success"), **_RUNNING}


@pytest.mark.parametrize("first", [[], [{"status": "queued"}], [_RUNNING]])
def test_delivered_waits_for_a_check_that_is_not_done_and_then_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: Clock,
    first: list[dict[str, object]],
) -> None:
    fixture = _delivered_fake(tmp_path, monkeypatch, [_running()])
    _answer(fixture, *({**_running(), **change} for change in first))
    finished = _run_of(_PUSH_SUITE, 1, "success")
    clock.after = lambda count: _answer(fixture, finished) if count == 2 else None
    assert _verify(fixture).merged_sha == fixture.head
    assert len(clock.slept) == 2
    assert len(set(clock.slept)) == 1


@pytest.mark.parametrize("waited", [0, 2])
def test_delivered_fails_at_once_on_a_failed_check_and_when_a_waited_check_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock, waited: int
) -> None:
    fixture = _delivered_fake(tmp_path, monkeypatch, [_running()])
    failed = _run_of(_PUSH_SUITE, 1, "failure")
    if waited:
        clock.after = lambda count: (
            _answer(fixture, failed) if count == waited else None
        )
    else:
        _answer(fixture, failed)
    with pytest.raises(shipping.ShippingError, match="not successful: build"):
        _verify(fixture)
    assert len(clock.slept) == waited


def test_delivered_names_the_check_and_the_limit_when_time_ends(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    fixture = _delivered_fake(tmp_path, monkeypatch, [_running()])
    with pytest.raises(shipping.PendingCheck) as refused:
        _verify(fixture)
    message = str(refused.value)
    assert message.startswith("required check has not completed: build")
    assert "time limit" in message
    assert "shipping ci_seconds" in message
    assert "180" in message
    assert sum(clock.slept) == 180


def test_ready_does_not_wait_for_a_pending_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clock: Clock
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head, **_RUNNING)])
    monkeypatch.setattr(shipping, "gh", fake)
    with pytest.raises(shipping.PendingCheck, match="has not completed"):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert clock.slept == []

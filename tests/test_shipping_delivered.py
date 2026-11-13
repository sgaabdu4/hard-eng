"""The delivered stage judges the run that the push to the base branch started."""

from pathlib import Path

import pytest
import shipping
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
    _native,
    _patch_gh,
    _pull,
)

_PUSH_SUITE = 11
_OTHER_SUITE = 22


def _delivered_fake(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checks: list[dict[str, object]],
    *,
    push_suites: tuple[int, ...] = (_PUSH_SUITE,),
) -> Fixture:
    fixture = _fixture(tmp_path, target="Merge")
    pull = _pull(
        fixture,
        state="closed",
        merged=True,
        merged_at="2026-09-10T11:00:00Z",
        merge_commit_sha=fixture.head,
    )
    fake = FakeGitHub(pull, [{**check, "head_sha": fixture.head} for check in checks])
    runs = [{"id": suite, "check_suite_id": suite} for suite in push_suites]
    fake.push_runs = [{"total_count": len(runs), "workflow_runs": runs}]
    _patch_gh(monkeypatch, fake)
    real_git = shipping.git

    def controlled_git(root: Path, *args: str) -> str:
        if args[:2] == ("ls-remote", "--heads"):
            return f"{fixture.head}\trefs/heads/main\n"
        if args[:2] == ("fetch", "--no-tags"):
            return ""
        return real_git(root, *args)

    monkeypatch.setattr(shipping, "git", controlled_git)
    _native(fixture.root, "branch", "-m", "feature/unrelated")
    return fixture


def _verify(fixture: Fixture) -> shipping.Shipment:
    return shipping.verify(fixture.root, fixture.plan, _PR_URL, "delivered")


def _run_of(suite: int, run_id: int, conclusion: str) -> dict[str, object]:
    return _check("", id=run_id, conclusion=conclusion, check_suite={"id": suite})


def test_delivered_judges_the_push_run_when_a_run_of_another_pull_request_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "success"), _run_of(_OTHER_SUITE, 2, "failure")],
    )
    assert _verify(fixture).merged_sha == fixture.head


def test_delivered_refuses_when_the_push_run_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "failure"), _run_of(_OTHER_SUITE, 2, "success")],
    )
    with pytest.raises(shipping.ShippingError, match="not successful"):
        _verify(fixture)


def test_delivered_judges_a_check_with_no_push_run_as_before(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "success"), _run_of(_OTHER_SUITE, 2, "failure")],
        push_suites=(),
    )
    with pytest.raises(shipping.ShippingError, match="not successful"):
        _verify(fixture)

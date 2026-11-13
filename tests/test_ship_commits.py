"""Exercise the commit cap and the rebase step of the ship stages."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import ship_actions
import shipping
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    _check,
    _fixture,
    _patch_gh,
    _pull,
    _ready_outcome,
)


def test_ready_refuses_a_pr_over_the_commit_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-PR-COMMITS: ready passes 100 commits and refuses 101 with both ways out."""
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, commits=100), [_check(fixture.head)])
    assert _ready_outcome(fixture, fake, monkeypatch, None) is not None
    fake.pulls[0] = _pull(fixture, commits=101)
    _ready_outcome(
        fixture,
        fake,
        monkeypatch,
        "PR has 101 commits; HE-PR-COMMITS allows at most 100.*PR of their own.*join neighbour"
        ".*`git diff <old head> <new head>` must then print nothing.*`--force-with-lease`",
    )


@pytest.mark.parametrize("value", [None, "5", True, 1.5])
def test_ready_refuses_a_pr_with_no_usable_commit_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, commits=value), [_check(fixture.head)])
    _ready_outcome(fixture, fake, monkeypatch, "PR commit count is invalid")


def test_ready_refuses_a_pr_github_cannot_rebase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    checks = [_check(fixture.head)]
    over = FakeGitHub(_pull(fixture, commits=101, rebaseable=False), checks)
    _ready_outcome(fixture, over, monkeypatch, "PR has 101 commits")
    cannot = FakeGitHub(_pull(fixture, rebaseable=False), checks)
    _ready_outcome(
        fixture,
        cannot,
        monkeypatch,
        "GitHub cannot rebase this PR onto main, so nothing was merged",
    )
    unknown = FakeGitHub(_pull(fixture, rebaseable=None), checks)
    assert _ready_outcome(fixture, unknown, monkeypatch, None) is not None


def test_a_rebaseable_value_that_arrives_late_is_no_change_in_the_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=None), [_check(fixture.head)])
    fake.pulls.append(_pull(fixture, rebaseable=True))
    assert _ready_outcome(fixture, fake, monkeypatch, None) is not None


def _merge_shipment(fixture_root: Path) -> shipping.Shipment:
    return shipping.Shipment(
        root=fixture_root,
        plan=None,
        pr_url=_PR_URL,
        repository="acme/widget",
        remote="origin",
        remote_url="https://github.com/acme/widget.git",
        branch="feature/shipping",
        head_sha="a" * 40,
        base="main",
        merged_sha=None,
        delivery_target="Merge",
    )


@pytest.mark.parametrize(
    ("rebaseable", "expected"),
    [(False, "nothing was merged"), (True, "GraphQL: something else failed")],
)
def test_merge_names_a_step_when_github_cannot_rebase(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    rebaseable: bool,
    expected: str,
) -> None:
    fixture = _fixture(tmp_path)
    failure = (
        "GraphQL: This branch can't be rebased (mergePullRequest)"
        if not rebaseable
        else "GraphQL: something else failed"
    )

    def merge_fails(_root: Path, *args: str) -> str:
        raise shipping.ShippingError(failure)

    def read_pull(_root: Path, *_args: str) -> str:
        return json.dumps(_pull(fixture, rebaseable=rebaseable))

    monkeypatch.setattr(ship_actions, "gh", merge_fails)
    monkeypatch.setattr(shipping, "gh", read_pull)
    with pytest.raises(shipping.ShippingError) as refused:
        ship_actions.merge(fixture.root, None, _merge_shipment(fixture.root), "rebase")
    message = str(refused.value)
    assert expected in message
    if not rebaseable:
        assert "--force-with-lease" in message
        assert "origin/main" in message
        assert "push to main" not in message
        assert "push it to main" not in message


_SETTING_STEP = (
    "This repository does not allow rebase merges, and Hard Eng merges by rebase "
    "only, so nothing was merged. Allow rebase merges in the repository settings, "
    "then run ship again."
)


def test_a_repository_that_forbids_rebase_merges_is_named_as_the_cause(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = False
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError) as refused:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert str(refused.value).startswith(_SETTING_STEP)
    assert "Rebase the branch" not in str(refused.value)
    assert len(fake.setting_reads) == 1


def test_a_failed_merge_in_a_repository_that_forbids_rebase_merges_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = False

    def merge_fails(_root: Path, *args: str) -> str:
        raise shipping.ShippingError("GraphQL: This branch can't be rebased")

    monkeypatch.setattr(ship_actions, "gh", merge_fails)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError) as refused:
        ship_actions.merge(fixture.root, None, _merge_shipment(fixture.root), "rebase")
    assert str(refused.value) == _SETTING_STEP


@pytest.mark.parametrize("setting", [True, None, "yes"])
def test_a_pr_github_cannot_rebase_keeps_the_rebase_step_unless_the_setting_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: object
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = setting
    _ready_outcome(fixture, fake, monkeypatch, "Rebase the branch on origin/main")


def test_an_unreadable_setting_keeps_the_rebase_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])

    def unreadable(root: Path, *args: str) -> str:
        if args[:2] == ("repo", "view"):
            raise shipping.ShippingError("gh query failed")
        return fake(root, *args)

    monkeypatch.setattr(shipping, "gh", unreadable)
    with pytest.raises(
        shipping.ShippingError, match="Rebase the branch on origin/main"
    ):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_a_pr_github_can_rebase_never_reads_the_repository_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=True), [_check(fixture.head)])
    assert _ready_outcome(fixture, fake, monkeypatch, None) is not None
    assert fake.setting_reads == []

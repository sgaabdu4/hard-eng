"""Exercise the commit cap and the rebase step of the ship stages."""

from __future__ import annotations

import json
from collections.abc import Callable
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


def _failed_merge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, forbids: bool = True
) -> tuple[FakeGitHub, str]:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = not forbids
    fake.comparison = _comparison(0)

    def merge_fails(_root: Path, *args: str) -> str:
        raise shipping.ShippingError("GraphQL: This branch can't be rebased")

    monkeypatch.setattr(ship_actions, "gh", merge_fails)
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError) as refused:
        ship_actions.merge(fixture.root, None, _merge_shipment(fixture.root), "rebase")
    return fake, str(refused.value)


def test_a_failed_merge_in_a_repository_that_forbids_rebase_merges_names_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, message = _failed_merge(tmp_path, monkeypatch)
    assert message == _SETTING_STEP


@pytest.mark.parametrize("setting", [True, None, "yes"])
def test_a_pr_github_cannot_rebase_keeps_the_rebase_step_unless_the_setting_is_false(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, setting: object
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = setting
    _ready_outcome(fixture, fake, monkeypatch, "Rebase the branch on origin/main")


def _unreadable_rebase_step(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fails: Callable[[tuple[str, ...]], bool],
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])

    def unreadable(root: Path, *args: str) -> str:
        if fails(args):
            raise shipping.ShippingError("gh query failed")
        return fake(root, *args)

    monkeypatch.setattr(shipping, "gh", unreadable)
    with pytest.raises(
        shipping.ShippingError, match="Rebase the branch on origin/main"
    ):
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")


def test_an_unreadable_setting_keeps_the_rebase_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _unreadable_rebase_step(
        tmp_path, monkeypatch, lambda args: args[:2] == ("repo", "view")
    )


def test_a_pr_github_can_rebase_never_reads_the_repository_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=True), [_check(fixture.head)])
    assert _ready_outcome(fixture, fake, monkeypatch, None) is not None
    assert fake.setting_reads == []


_READ = ("repo", "view", "acme/widget", "--json", "rebaseMergeAllowed")


def test_the_ready_check_reads_the_setting_of_the_repository_of_the_pull_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.rebase_merge_allowed = False
    _ready_outcome(fixture, fake, monkeypatch, "does not allow rebase merges")
    assert fake.setting_reads == [_READ]


def test_a_failed_merge_reads_the_setting_of_the_repository_of_the_pull_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake, _ = _failed_merge(tmp_path, monkeypatch)
    assert fake.setting_reads == [_READ]


_STALE = (
    "GitHub reports that it cannot rebase this PR onto main, but the branch is "
    "current with main and has no merge commit, so that report can be stale. "
    "Close the pull request and open it again, wait for the checks, then run ship "
    "again. If GitHub still cannot rebase it, cut its commits (HE-PR-COMMITS)."
)


def _comparison(behind: int = 0, *parents: int, total: int | None = None) -> object:
    commits = [{"parents": list(range(count))} for count in parents or (1,)]
    return {
        "behind_by": behind,
        "total_commits": len(commits) if total is None else total,
        "commits": commits,
    }


def _compare_reads(fake: FakeGitHub) -> list[tuple[str, ...]]:
    return [call for call in fake.calls if "/compare/" in call[-1]]


def _cannot_rebase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comparison: object
) -> tuple[FakeGitHub, str]:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    fake.comparison = comparison
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.ShippingError) as refused:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    return fake, str(refused.value)


def test_a_stale_cannot_rebase_report_says_to_close_and_open_the_pull_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake, message = _cannot_rebase(tmp_path, monkeypatch, _comparison(0, 1, 1))
    assert message.startswith(_STALE)
    assert "Rebase the branch on" not in message
    assert len(_compare_reads(fake)) == 1


@pytest.mark.parametrize(
    "comparison",
    [
        _comparison(1),
        _comparison(0, 1, 2),
        _comparison(0, 1, total=2),
        {"behind_by": 0},
        {"behind_by": None, "commits": [], "total_commits": 0},
    ],
    ids=["behind", "merge-commit", "incomplete-list", "no-commits", "bad-behind"],
)
def test_a_cannot_rebase_report_keeps_the_rebase_step_unless_the_branch_is_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comparison: object
) -> None:
    _, message = _cannot_rebase(tmp_path, monkeypatch, comparison)
    assert message.startswith("GitHub cannot rebase this PR onto main")
    assert "Rebase the branch on origin/main" in message


def test_a_failed_comparison_keeps_the_rebase_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _unreadable_rebase_step(tmp_path, monkeypatch, lambda args: "/compare/" in args[-1])


def test_the_setting_message_and_a_rebaseable_pr_add_no_comparison_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    forbids = FakeGitHub(_pull(fixture, rebaseable=False), [_check(fixture.head)])
    forbids.rebase_merge_allowed = False
    forbids.comparison = _comparison(0)
    _ready_outcome(fixture, forbids, monkeypatch, "does not allow rebase merges")
    assert _compare_reads(forbids) == []
    clean = FakeGitHub(_pull(fixture, rebaseable=True), [_check(fixture.head)])
    assert _ready_outcome(fixture, clean, monkeypatch, None) is not None
    assert len(_compare_reads(clean)) == 1
    assert clean.setting_reads == []


def test_a_failed_merge_on_a_current_branch_gives_the_stale_report_hint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, message = _failed_merge(tmp_path, monkeypatch, forbids=False)
    assert message == _STALE

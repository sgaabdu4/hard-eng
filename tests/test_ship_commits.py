"""Exercise the commit cap and the rebase step of the ship stages."""

from __future__ import annotations

from pathlib import Path

import pytest
from test_shipping import FakeGitHub, _check, _fixture, _pull, _ready_outcome


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
        "PR has 101 commits; HE-PR-COMMITS allows at most 100.*own PR.*join neighbour",
    )


@pytest.mark.parametrize("value", [None, "5", True, 1.5])
def test_ready_refuses_a_pr_with_no_usable_commit_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, commits=value), [_check(fixture.head)])
    _ready_outcome(fixture, fake, monkeypatch, "PR commit count is invalid")

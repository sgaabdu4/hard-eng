"""The release, hotfix and join pull requests pass ship with a merge commit; every other pull request into the default branch stays refused."""

import json
from pathlib import Path

import pytest
import shipping
from conftest import git
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
    _patch_gh,
    _pull,
)


def develop_policy(tmp_path: Path, branch: str, big: bool = True) -> Fixture:
    fixture = _fixture(tmp_path)
    git(fixture.root, "branch", "-M", branch)
    gates = json.loads((fixture.root / "hard-eng.gates.json").read_text())
    gates["shipping"]["base"] = "develop"
    (fixture.root / "hard-eng.gates.json").write_text(json.dumps(gates))
    git(fixture.root, "commit", "-qam", "base is develop")
    if big:
        (fixture.root / "added.txt").write_text("a big change\n")
        git(fixture.root, "add", "added.txt")
        git(fixture.root, "commit", "-qm", "big change")
    return fixture


def _route_pull(
    fixture: Fixture, head_ref: str, base_ref: str, commits: int
) -> dict[str, object]:
    head = git(fixture.root, "rev-parse", "HEAD")
    repo = {"full_name": "acme/widget", "default_branch": "main"}
    pull = _pull(fixture, commits=commits, rebaseable=commits < 100)
    pull["head"] = {"ref": head_ref, "sha": head, "repo": repo}
    pull["base"] = {"ref": base_ref, "sha": "a" * 40, "repo": repo}
    return pull


def _ship(
    monkeypatch: pytest.MonkeyPatch,
    fixture: Fixture,
    pull: dict[str, object],
    behind: int = 0,
    plan: Path | None = None,
) -> shipping.Shipment:
    fake = FakeGitHub(pull, [_check(git(fixture.root, "rev-parse", "HEAD"))])
    fake.comparison = {"behind_by": behind}
    _patch_gh(monkeypatch, fake)
    return shipping.verify(fixture.root, plan, _PR_URL, "ready")


@pytest.mark.parametrize(
    ("branch", "head_ref", "base_ref", "behind"),
    [
        ("develop", "develop", "main", 0),
        ("hotfix/repair", "hotfix/repair", "main", 0),
        ("main", "main", "develop", 4),
    ],
    ids=["release", "hotfix", "join"],
)
def test_a_release_hotfix_or_join_passes_ship_with_a_merge_commit_beyond_the_commit_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    branch: str,
    head_ref: str,
    base_ref: str,
    behind: int,
) -> None:
    fixture = develop_policy(tmp_path, branch)
    pull = _route_pull(fixture, head_ref, base_ref, 156)
    shipment = _ship(monkeypatch, fixture, pull, behind)
    assert shipment.method == "merge"
    record = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    assert (record["head"], record["method"]) == (shipment.head_sha, "merge")


def test_a_task_pull_request_into_the_default_branch_stays_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "feature/shipping")
    pull = _route_pull(fixture, "feature/shipping", "main", 1)
    with pytest.raises(shipping.ShippingError, match="base branch does not match"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)


def test_a_rebase_pull_request_still_holds_the_commit_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "feature/shipping")
    pull = _route_pull(fixture, "feature/shipping", "develop", 156)
    with pytest.raises(shipping.ShippingError, match="HE-PR-COMMITS"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)


def test_the_base_branch_into_a_branch_that_is_not_the_default_stays_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "develop")
    pull = _route_pull(fixture, "develop", "staging", 1)
    with pytest.raises(shipping.ShippingError, match="base branch does not match"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)

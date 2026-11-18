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


def _origin_refs(fixture: Fixture, main_in_head: bool) -> None:
    """origin/develop at the first commit; origin/main inside the head or on a side commit that the head lacks."""
    first = git(fixture.root, "rev-list", "--max-parents=0", "HEAD")
    head = git(fixture.root, "rev-parse", "HEAD")
    tree = git(fixture.root, "rev-parse", "HEAD^{tree}")
    side = git(fixture.root, "commit-tree", tree, "-p", first, "-m", "main tip")
    main_tip = git(fixture.root, "rev-parse", "HEAD~1") if main_in_head else side
    git(fixture.root, "update-ref", "refs/remotes/origin/develop", first)
    git(fixture.root, "update-ref", "refs/remotes/origin/main", main_tip)
    assert head != main_tip


def _recorded_method(fixture: Fixture) -> str:
    record = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    return str(record["method"])


@pytest.mark.parametrize(
    ("head_ref", "base_ref", "behind"),
    [("develop", "main", 0), ("chore/join-main-hotfix", "develop", 4)],
    ids=["release", "join"],
)
def test_a_release_or_join_passes_ship_with_a_merge_commit_beyond_the_commit_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    head_ref: str,
    base_ref: str,
    behind: int,
) -> None:
    fixture = develop_policy(tmp_path, head_ref)
    _origin_refs(fixture, main_in_head=True)
    pull = _route_pull(fixture, head_ref, base_ref, 156)
    shipment = _ship(monkeypatch, fixture, pull, behind)
    assert shipment.method == "merge"
    assert _recorded_method(fixture) == "merge"


def test_a_task_branch_into_the_base_that_lacks_the_default_tip_is_not_a_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "chore/join-main-hotfix")
    _origin_refs(fixture, main_in_head=False)
    pull = _route_pull(fixture, "chore/join-main-hotfix", "develop", 156)
    with pytest.raises(shipping.ShippingError, match="HE-PR-COMMITS"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)
    small = _route_pull(fixture, "chore/join-main-hotfix", "develop", 1)
    assert _ship(monkeypatch, fixture, small, plan=fixture.plan).method == "rebase"


def test_a_hotfix_passes_ship_with_a_merge_commit_and_keeps_its_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "hotfix/repair")
    pull = _route_pull(fixture, "hotfix/repair", "main", 3)
    pull["rebaseable"] = False
    shipment = _ship(monkeypatch, fixture, pull, plan=fixture.plan)
    assert shipment.method == "merge"
    assert _recorded_method(fixture) == "merge"


def test_a_big_hotfix_with_no_plan_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "hotfix/repair")
    pull = _route_pull(fixture, "hotfix/repair", "main", 3)
    with pytest.raises(shipping.ShippingError, match="big change needs a plan"):
        _ship(monkeypatch, fixture, pull)


def test_a_hotfix_over_the_commit_limit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "hotfix/repair")
    pull = _route_pull(fixture, "hotfix/repair", "main", 156)
    with pytest.raises(shipping.ShippingError, match="HE-PR-COMMITS"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)


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

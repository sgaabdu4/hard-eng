"""The release, hotfix and join pull requests pass ship with a merge commit; every other pull request into the default branch stays refused."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
import shipping
from conftest import git
from gate_config import JsonValue
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


def _origin_refs(fixture: Fixture, tip: str) -> None:
    """origin/develop at the first commit; origin/main at the head, at its parent or on a side commit that the head lacks."""
    first = git(fixture.root, "rev-list", "--max-parents=0", "HEAD")
    tree = git(fixture.root, "rev-parse", "HEAD^{tree}")
    side = git(fixture.root, "commit-tree", tree, "-p", first, "-m", "main tip")
    tips = {"head": "HEAD", "parent": "HEAD~1", "side": side}
    git(fixture.root, "update-ref", "refs/remotes/origin/develop", first)
    git(
        fixture.root,
        "update-ref",
        "refs/remotes/origin/main",
        git(fixture.root, "rev-parse", tips[tip]),
    )


def _recorded_method(fixture: Fixture) -> str:
    record = json.loads((fixture.root / ".git/hard-eng/ship/1.json").read_text())
    return str(record["method"])


@pytest.mark.parametrize(
    ("head_ref", "base_ref", "behind", "method"),
    [("develop", "main", 0, "merge"), ("chore/join-main-hotfix", "develop", 4, "join")],
    ids=["release", "join"],
)
def test_a_release_or_join_passes_ship_with_a_merge_commit_beyond_the_commit_limit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    head_ref: str,
    base_ref: str,
    behind: int,
    method: str,
) -> None:
    fixture = develop_policy(tmp_path, head_ref)
    _origin_refs(fixture, "head")
    pull = _route_pull(fixture, head_ref, base_ref, 156)
    shipment = _ship(monkeypatch, fixture, pull, behind)
    assert shipment.method == method
    assert _recorded_method(fixture) == method


def test_a_task_branch_into_the_base_that_lacks_the_default_tip_is_not_a_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "chore/join-main-hotfix")
    _origin_refs(fixture, "side")
    pull = _route_pull(fixture, "chore/join-main-hotfix", "develop", 156)
    with pytest.raises(shipping.ShippingError, match="HE-PR-COMMITS"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)
    small = _route_pull(fixture, "chore/join-main-hotfix", "develop", 1)
    assert _ship(monkeypatch, fixture, small, plan=fixture.plan).method == "rebase"


def test_a_task_branch_with_its_own_commit_that_merged_the_default_branch_is_not_a_join(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = develop_policy(tmp_path, "feature/merged-main")
    _origin_refs(fixture, "parent")
    pull = _route_pull(fixture, "feature/merged-main", "develop", 156)
    with pytest.raises(shipping.ShippingError, match="HE-PR-COMMITS"):
        _ship(monkeypatch, fixture, pull, plan=fixture.plan)
    small = _route_pull(fixture, "feature/merged-main", "develop", 1)
    with pytest.raises(shipping.ShippingError, match="big change needs a plan"):
        _ship(monkeypatch, fixture, small)


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


@dataclass(frozen=True)
class JoinPull:
    head_sha: str
    head_ref: str = "chore/join-main-hotfix"
    base_ref: str = "develop"
    rebaseable: bool | None = True
    default_branch: str | None = "main"
    merge_commit_sha: str | None = None


def join_graph(tmp_path: Path) -> tuple[Path, str, str, str, str]:
    """A develop tip, the main tip that develop lacks, and a join head that holds both."""
    fixture = develop_policy(tmp_path, "chore/join-main-hotfix")
    root = fixture.root
    develop = git(root, "rev-parse", "HEAD")
    first = git(root, "rev-list", "--max-parents=0", "HEAD")
    tree = git(root, "rev-parse", "HEAD^{tree}")
    main = git(root, "commit-tree", tree, "-p", first, "-m", "main tip")
    join = git(root, "commit-tree", tree, "-p", develop, "-p", main, "-m", "join")
    return root, develop, tree, main, join


def test_a_merged_join_keeps_its_route_when_the_base_already_holds_the_default_tip(
    tmp_path: Path,
) -> None:
    from ship_record import base_before_merge, route

    root, develop, tree, main, join = join_graph(tmp_path)
    merged = git(root, "commit-tree", tree, "-p", develop, "-p", join, "-m", "merge")
    git(root, "update-ref", "refs/remotes/origin/main", main)
    git(root, "update-ref", "refs/remotes/origin/develop", merged)
    pull = JoinPull(join, merge_commit_sha=merged)
    before = base_before_merge(root, join, merged)
    assert before == develop
    assert route(root, pull, "develop") is None
    assert route(root, pull, "develop", before) == "join"

    own = git(root, "commit-tree", tree, "-p", develop, "-m", "own work")
    feature = git(root, "commit-tree", tree, "-p", own, "-p", main, "-m", "main in")
    after = git(root, "commit-tree", tree, "-p", develop, "-p", feature, "-m", "merge")
    git(root, "update-ref", "refs/remotes/origin/develop", after)
    task = JoinPull(feature, head_ref="feature/own-work", merge_commit_sha=after)
    assert route(root, task, "develop", base_before_merge(root, feature, after)) is None
    assert base_before_merge(root, join, after) is None


def test_the_delivered_stage_needs_no_plan_for_a_merged_join_but_asks_for_one_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ship_scope
    import ui_proof

    root, develop, tree, main, join = join_graph(tmp_path)
    work = git(root, "commit-tree", tree, "-p", develop, "-m", "own work")
    own = git(root, "commit-tree", tree, "-p", work, "-p", main, "-m", "main in")
    git(root, "update-ref", "refs/remotes/origin/main", main)

    def listed(*_: object) -> list[dict[str, JsonValue]]:
        return [{"filename": "features/x/PLAN.md"}]

    monkeypatch.setattr(ui_proof, "changed_files", listed)
    policy = shipping.load_policy(root)
    assert policy is not None
    policy["ui_paths"] = []
    identity = ("acme", "widget", 7)
    for head, ref, expect in (
        (join, "chore/join-main", False),
        (own, "feature/x", True),
    ):
        merged = git(root, "commit-tree", tree, "-p", develop, "-p", head, "-m", "m")
        git(root, "update-ref", "refs/remotes/origin/develop", merged)
        pull = shipping._PullRequest(
            state="closed",
            draft=False,
            head_ref=ref,
            head_sha=head,
            head_repository="acme/widget",
            base_ref="develop",
            base_repository="acme/widget",
            body="",
            mergeable=None,
            mergeable_state=None,
            merged=True,
            merged_at="2026-11-24T00:00:00Z",
            merge_commit_sha=merged,
            commits=1,
            rebaseable=False,
            default_branch="main",
        )
        args = (root, pull, identity, policy, None, "delivered")
        if expect:
            with pytest.raises(shipping.ShippingError, match="--plan is missing"):
                ship_scope.delivered_files(*args)
        else:
            assert ship_scope.delivered_files(*args) == []

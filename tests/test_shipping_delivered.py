"""The delivered stage judges the run that the push to the base branch started."""

import json
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
    elsewhere: tuple[int, ...] = (),
    release: bool = False,
    ui_paths: list[str] | None = None,
    files: list[dict[str, object]] | None = None,
) -> Fixture:
    fixture = _fixture(tmp_path, target="Merge", ui_paths=ui_paths)
    pull = _pull(
        fixture,
        state="closed",
        merged=True,
        merged_at="2026-09-10T11:00:00Z",
        merge_commit_sha=fixture.head,
    )
    if release:
        gates = json.loads((fixture.root / "hard-eng.gates.json").read_text())
        gates["shipping"]["base"] = "develop"
        (fixture.root / "hard-eng.gates.json").write_text(json.dumps(gates))
        _native(fixture.root, "commit", "-qam", "base is develop")
        fixture = Fixture(
            fixture.root, fixture.plan, _native(fixture.root, "rev-parse", "HEAD")
        )
        pull = _pull(
            fixture,
            state="closed",
            merged=True,
            merged_at="2026-09-10T11:00:00Z",
            merge_commit_sha=fixture.head,
            head={
                "ref": "develop",
                "sha": fixture.head,
                "repo": {"full_name": "acme/widget"},
            },
        )
    fake = FakeGitHub(
        pull, [{**check, "head_sha": fixture.head} for check in checks], files
    )
    runs = [
        {"id": suite, "check_suite_id": suite, "head_branch": branch}
        for branch, suites in (("main", push_suites), ("release", elsewhere))
        for suite in suites
    ]
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


def test_delivered_refuses_when_the_base_push_run_failed_and_a_push_to_another_branch_passed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "failure"), _run_of(_OTHER_SUITE, 2, "success")],
        elsewhere=(_OTHER_SUITE,),
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


def test_delivered_judges_a_release_on_the_branch_it_merged_into(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path, monkeypatch, [_run_of(_PUSH_SUITE, 1, "success")], release=True
    )
    assert _verify(fixture).merged_sha


_SCREEN: dict[str, object] = {"filename": "src/App.ts", "patch": "@@ -1 +1 @@\n-a\n+b"}
_PLAN_FILE: dict[str, object] = {
    "filename": "features/shipping/PLAN.md",
    "patch": "@@ -0,0 +1 @@\n+x",
}


def test_delivered_without_a_plan_says_the_plan_is_missing_when_the_pr_changed_a_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "success")],
        ui_paths=["src/**"],
        files=[_SCREEN, _PLAN_FILE],
    )
    with pytest.raises(shipping.ShippingError) as refused:
        shipping.verify(fixture.root, None, _PR_URL, "delivered")
    assert "--plan is missing" in str(refused.value)
    assert "features/shipping/PLAN.md" in str(refused.value)
    assert "UI appearance" not in str(refused.value)


def test_delivered_without_a_plan_still_passes_for_a_pr_that_changed_no_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _delivered_fake(
        tmp_path,
        monkeypatch,
        [_run_of(_PUSH_SUITE, 1, "success")],
        files=[{"filename": "src/util.ts", "patch": "@@ -1 +1 @@\n-a\n+b"}],
    )
    assert shipping.verify(fixture.root, None, _PR_URL, "delivered").merged_sha

"""Billed Actions minutes from GitHub's run and job records."""

import json
import sys
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import plans
import pytest
import shipping
from ci_usage import ci_usage, reused_pull_request
from test_review_bypass import required_rule, rules_answer
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    MergedPush,
    _check,
    _fixture,
    _merged_push,
    _native,
    _patch_gh,
    _pull,
)

SOURCE = Path(__file__).resolve().parents[1]


def _job(name: str, seconds: int, **changes: object) -> dict[str, object]:
    job: dict[str, object] = {
        "name": name,
        "status": "completed",
        "conclusion": "success",
        "runner_name": "GitHub Actions 1",
        "labels": ["ubuntu-latest"],
        "steps": [{"name": "Set up job"}],
        "started_at": "2026-09-10T10:00:00Z",
        "completed_at": f"2026-09-10T10:{seconds // 60:02}:{seconds % 60:02}Z",
    }
    job.update(changes)
    return job


def _usage(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    runs: list[tuple[str, list[dict[str, object]]]],
    limit: int | None = None,
) -> str:
    import shipping

    def github(_root: Path, *args: str) -> str:
        endpoint = args[-1]
        if "/actions/runs?" in endpoint:
            page = {
                "total_count": len(runs),
                "workflow_runs": [
                    {"id": index, "name": "CI", "event": event, "path": "ci.yml"}
                    for index, (event, _) in enumerate(runs)
                ],
            }
            return json.dumps([page] if "--paginate" in args else page)
        jobs = runs[int(endpoint.split("/runs/")[1].split("/")[0])][1]
        return json.dumps([{"total_count": len(jobs), "jobs": jobs}])

    monkeypatch.setattr(shipping, "gh", github)
    assert ci_usage(SOURCE, "acme/widget", 14, limit) == 0
    return capsys.readouterr().out


def test_ci_usage_bills_started_jobs_in_whole_minutes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    never_started = _job("queued", 3599, runner_name="", steps=[])
    output = _usage(
        monkeypatch,
        capsys,
        [
            (
                "pull_request",
                [
                    _job("test", 61),
                    _job("mac", 30, labels=["macos-15"]),
                    _job("lint", 5, conclusion="cancelled"),
                    _job("build", 70, conclusion="failure"),
                    never_started,
                    _job(
                        "deploy",
                        0,
                        status="in_progress",
                        conclusion=None,
                        completed_at=None,
                    ),
                ],
            )
        ],
    )
    assert "1 runs, 6 jobs. Billed 15 min (8 rounding" in output
    assert "cancelled 1, failed 2; 1 jobs never got a runner" in output
    assert "1 jobs still running are not counted" in output
    assert "    10     1        30     30  CI / pull_request / mac" in output
    assert "queued" not in output and "deploy" not in output


def test_self_hosted_jobs_are_not_billed(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _usage(
        monkeypatch,
        capsys,
        [
            (
                "push",
                [
                    _job("own", 210, labels=["Self-Hosted", "macOS", "ARM64"]),
                    _job("hosted", 61, labels=["macos-15"]),
                ],
            )
        ],
    )
    assert "Billed 20 min" in output
    assert "1 self-hosted jobs are not billed" in output
    assert "     0     1       210    210  CI / push / own" in output


def test_ci_usage_reports_jobs_repeated_on_push_and_pull_request(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = _usage(
        monkeypatch,
        capsys,
        [
            ("pull_request", [_job("test", 100), _job("preview", 20)]),
            ("push", [_job("test", 130), _job("deploy", 40)]),
        ],
    )
    assert (
        "Runs on push and pull_request: CI / test (push 3 min, pull_request 2 min)"
        in output
    )
    assert "CI / preview" not in output.split("Runs on push")[1]
    assert output.count("Runs on push and pull_request") == 1


def test_ci_usage_splits_the_slowest_jobs_into_queue_setup_and_run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def step(name: str, start: int, end: int) -> dict[str, object]:
        return {
            "name": name,
            "started_at": f"2026-09-10T10:00:{start:02}Z",
            "completed_at": f"2026-09-10T10:00:{end:02}Z",
        }

    checks = _job(
        "hard-eng",
        50,
        created_at="2026-09-10T09:59:30Z",
        steps=[
            step("Set up job", 0, 2),
            step("Run actions/checkout@v7", 2, 10),
            step("Install check tools", 10, 20),
            step("Run required checks", 20, 48),
            step("Complete job", 48, 50),
        ],
    )
    output = _usage(monkeypatch, capsys, [("pull_request", [checks])], limit=150)
    assert "acme/widget, last 150 runs: 1 runs, 1 jobs." in output
    assert "    30     22     28     80     1  CI / hard-eng" in output


def test_ci_usage_reads_only_the_newest_runs_across_pages(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import shipping

    pages: list[str] = []

    def github(_root: Path, *args: str) -> str:
        endpoint = args[-1]
        if "/actions/runs?" in endpoint:
            page = int(endpoint.rsplit("&page=", 1)[1])
            pages.append(endpoint)
            runs = [
                {"id": (page - 1) * 100 + index, "name": "CI", "event": "push"}
                for index in range(100)
            ]
            return json.dumps({"total_count": 300, "workflow_runs": runs})
        run = int(endpoint.split("/runs/")[1].split("/")[0])
        return json.dumps([{"total_count": 1, "jobs": [_job(f"job{run}", 60)]}])

    monkeypatch.setattr(shipping, "gh", github)
    assert ci_usage(SOURCE, "acme/widget", 14, 150) == 0
    output = capsys.readouterr().out
    assert len(pages) == 2
    assert "last 150 runs: 150 runs, 150 jobs." in output


def _ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def _queued(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, job: object
) -> tuple[Fixture, FakeGitHub]:
    fixture = _fixture(tmp_path)
    queued = _check(fixture.head, status="queued", conclusion=None, completed_at=None)
    fake = FakeGitHub(_pull(fixture), [queued])
    fake.job = job
    fake.rules = rules_answer(required_rule("build"))
    _patch_gh(monkeypatch, fake)
    return fixture, fake


_WAITING = {
    "status": "queued",
    "runner_name": None,
    "labels": ["self-hosted", "linux"],
}


def test_ready_names_a_required_check_that_no_runner_took(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = _queued(tmp_path, monkeypatch, _WAITING | {"created_at": _ago(120)})
    with pytest.raises(shipping.PendingCheck) as pending:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert str(pending.value) == (
        "required check has not completed: build; no runner has taken it for "
        "120 min (labels: self-hosted, linux). Start a runner with those labels, "
        "or ask its owner whether it serves this PR's author. GitHub fails a job "
        "queued over 24 hours."
    )
    assert [call[-1] for call in fake.calls if "/actions/jobs/" in call[-1]] == [
        "repos/acme/widget/actions/jobs/1"
    ]


@pytest.mark.parametrize(
    "job",
    [
        _WAITING | {"created_at": _ago(1)},
        _WAITING | {"created_at": _ago(120), "runner_name": "runner-1"},
        _WAITING | {"created_at": _ago(120), "labels": []},
        _WAITING | {"created_at": _ago(120), "status": "waiting"},
        _WAITING | {"created_at": _ago(120), "labels": ["ubuntu-latest"]},
        _WAITING | {"created_at": "yesterday"},
        _WAITING,
        ["not", "a", "job"],
        None,
    ],
)
def test_a_fresh_or_unreadable_queued_job_keeps_the_plain_pending_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, job: object
) -> None:
    fixture, _ = _queued(tmp_path, monkeypatch, job)
    with pytest.raises(shipping.PendingCheck) as pending:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert str(pending.value) == "required check has not completed: build"


def test_a_running_check_makes_no_job_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    running = _check(fixture.head, status="in_progress", conclusion=None)
    fake = FakeGitHub(_pull(fixture), [running])
    fake.rules = rules_answer(required_rule("build"))
    fake.job = _WAITING | {"created_at": _ago(120)}
    _patch_gh(monkeypatch, fake)
    with pytest.raises(shipping.PendingCheck) as pending:
        shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert str(pending.value) == "required check has not completed: build"
    assert not [call for call in fake.calls if "/actions/jobs/" in call[-1]]


def test_completed_checks_make_no_job_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert not [call for call in fake.calls if "/actions/jobs/" in call[-1]]


def test_branch_point_never_looks_up_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture, fake = _queued(tmp_path, monkeypatch, _WAITING | {"created_at": _ago(120)})
    monkeypatch.setattr(plans, "default_branch_point", Mock(return_value=fixture.head))
    monkeypatch.delitem(sys.modules, "ci_usage")
    assert shipping.passed_branch_point(fixture.root) is None
    assert [call for call in fake.calls if "check-runs" in call[-1]]
    assert not [call for call in fake.calls if "/actions/jobs/" in call[-1]]
    imported = "ci_usage" in sys.modules
    assert not imported


def test_push_reuse_never_looks_up_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push = _merged_push(tmp_path, monkeypatch)
    check = _check(push.head, status="queued", conclusion=None)
    push.responses[f"commits/{push.head}/check-runs?per_page=100&filter=all"] = [
        {"total_count": 1, "check_runs": [check]}
    ]
    push.responses["actions/jobs/1"] = _WAITING | {"created_at": _ago(120)}
    spy = Mock(side_effect=shipping.gh)
    monkeypatch.setattr(shipping, "gh", spy)
    monkeypatch.delitem(sys.modules, "ci_usage")
    assert reused_pull_request(push.root, push.base) is None
    assert [call for call in spy.call_args_list if "check-runs" in call.args[-1]]
    assert not [
        call for call in spy.call_args_list if "/actions/jobs/" in call.args[-1]
    ]
    imported = "ci_usage" in sys.modules
    assert not imported


@pytest.mark.parametrize("method", ["squash", "merge", "rebase"])
def test_push_reuses_passed_pull_request_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    push = _merged_push(tmp_path, monkeypatch, method=method)
    assert reused_pull_request(push.root, push.base) == push.head


def _different_tree(push: MergedPush) -> None:
    push.responses[f"git/commits/{push.head}"] = {"tree": {"sha": "f" * 40}}


def _base_not_contained(push: MergedPush) -> None:
    push.responses[f"compare/{push.base}...{push.head}"] = {"status": "diverged"}


def _check_failed(push: MergedPush) -> None:
    push.responses[f"commits/{push.head}/check-runs?per_page=100&filter=all"] = [
        {"total_count": 1, "check_runs": [_check(push.head, conclusion="failure")]}
    ]


def _check_missing(push: MergedPush) -> None:
    push.responses[f"commits/{push.head}/check-runs?per_page=100&filter=all"] = [
        {"total_count": 0, "check_runs": []}
    ]


def _check_pending(push: MergedPush) -> None:
    push.responses[f"commits/{push.head}/check-runs?per_page=100&filter=all"] = [
        {
            "total_count": 1,
            "check_runs": [_check(push.head, status="in_progress", conclusion=None)],
        }
    ]


def _query_failure(push: MergedPush) -> None:
    del push.responses[f"commits/{_native(push.root, 'rev-parse', 'HEAD')}/pulls"]


def _no_merged_pull_request(push: MergedPush) -> None:
    push.pulls[0]["merged_at"] = None


def _pull_request_into_another_base(push: MergedPush) -> None:
    push.pulls[0]["base"] = {"ref": "release"}


def _two_merged_pull_requests(push: MergedPush) -> None:
    push.pulls.append({**push.pulls[0], "number": 8, "head": {"sha": "e" * 40}})


def _uncommitted_change(push: MergedPush) -> None:
    (push.root / "source.txt").write_text("uncommitted\n")


@pytest.mark.parametrize(
    "break_proof",
    [
        _different_tree,
        _base_not_contained,
        _check_failed,
        _check_missing,
        _check_pending,
        _query_failure,
        _no_merged_pull_request,
        _pull_request_into_another_base,
        _two_merged_pull_requests,
        _uncommitted_change,
    ],
)
def test_push_runs_checks_when_pull_request_proof_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    break_proof: Callable[[MergedPush], None],
) -> None:
    push = _merged_push(tmp_path, monkeypatch)
    break_proof(push)
    assert reused_pull_request(push.root, push.base) is None
    reason = capsys.readouterr().out
    assert reason.startswith(
        "Running the checks again; the merged PR's checks do not cover this push: "
    )
    assert (
        reason.strip()
        .removeprefix(
            "Running the checks again; the merged PR's checks do not cover this push:"
        )
        .strip()
    )


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("GITHUB_ACTIONS", None),
        ("GITHUB_EVENT_NAME", "pull_request"),
        ("GITHUB_REF", "refs/heads/feature/shipping"),
    ],
)
def test_only_ci_pushes_to_the_base_branch_reuse_pull_request_checks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    name: str,
    value: str | None,
) -> None:
    push = _merged_push(tmp_path, monkeypatch)
    if value is None:
        monkeypatch.delenv(name)
    else:
        monkeypatch.setenv(name, value)
    assert reused_pull_request(push.root, push.base) is None
    assert capsys.readouterr().out == ""


def test_reused_pull_request_result_skips_gates(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing = {
        "name": "fails",
        "command": [sys.executable, "-c", "raise SystemExit(2)"],
    }
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [failing]})
    )

    def reused(_root: Path, base: str) -> str:
        return base

    monkeypatch.setattr("ci_usage.reused_pull_request", reused)
    assert runner.check(base="a" * 40) == 0
    output = capsys.readouterr().out
    assert f"PR head {'a' * 40} passed the required checks" in output
    assert "fails" not in output

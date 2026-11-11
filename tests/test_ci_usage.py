"""Billed Actions minutes from GitHub's run and job records."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import plans
import pytest
import shipping
from ci_usage import ci_usage
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
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
    _patch_gh(monkeypatch, fake)
    return fixture, fake


_WAITING = {"runner_name": None, "labels": ["self-hosted", "linux"]}


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


def test_completed_checks_make_no_job_lookup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture), [_check(fixture.head)])
    _patch_gh(monkeypatch, fake)
    shipping.verify(fixture.root, fixture.plan, _PR_URL, "ready")
    assert not [call for call in fake.calls if "/actions/jobs/" in call[-1]]


@pytest.mark.parametrize("path", ["checks", "branch_point"])
def test_branch_point_and_push_reuse_never_look_up_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    fixture, fake = _queued(tmp_path, monkeypatch, _WAITING | {"created_at": _ago(120)})
    monkeypatch.setattr(plans, "default_branch_point", Mock(return_value=fixture.head))
    policy = shipping.load_policy(fixture.root)
    assert policy is not None
    if path == "branch_point":
        assert shipping.passed_branch_point(fixture.root) is None
    else:
        with pytest.raises(shipping.PendingCheck) as pending:
            shipping._checks(fixture.root, "acme/widget", fixture.head, policy, False)
        assert str(pending.value) == "required check has not completed: build"
    assert [call for call in fake.calls if "check-runs" in call[-1]]
    assert not [call for call in fake.calls if "/actions/jobs/" in call[-1]]

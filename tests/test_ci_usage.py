"""Billed Actions minutes from GitHub's run and job records."""

import json
from pathlib import Path

import pytest
from ci_setup import ci_usage

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
) -> str:
    import shipping

    def github(_root: Path, *args: str) -> str:
        endpoint = args[-1]
        if "/actions/runs?" in endpoint:
            return json.dumps(
                [
                    {
                        "total_count": len(runs),
                        "workflow_runs": [
                            {
                                "id": index,
                                "name": "CI",
                                "event": event,
                                "path": "ci.yml",
                            }
                            for index, (event, _) in enumerate(runs)
                        ],
                    }
                ]
            )
        jobs = runs[int(endpoint.split("/runs/")[1].split("/")[0])][1]
        return json.dumps([{"total_count": len(jobs), "jobs": jobs}])

    monkeypatch.setattr(shipping, "gh", github)
    assert ci_usage(SOURCE, "acme/widget", 14) == 0
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

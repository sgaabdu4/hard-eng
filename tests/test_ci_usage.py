"""Billed Actions minutes from GitHub's run and job records."""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
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
        ("GITHUB_EVENT_NAME", "schedule"),
        ("GITHUB_REF", "refs/tags/v1"),
    ],
)
def test_only_ci_branch_pushes_reuse_pull_request_checks(
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


def reuse_every_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stand in for a CI run whose base commit already passed on this exact tree."""

    def reused(_root: Path, base: str) -> str:
        return base

    monkeypatch.setattr("ci_usage.reused_pull_request", reused)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")


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

    reuse_every_commit(monkeypatch)
    assert runner.check(base="a" * 40) == 0
    output = capsys.readouterr().out
    assert f"Commit {'a' * 40} passed the required checks" in output
    assert "fails" not in output


def sharded_project(root: Path) -> None:
    tests = {
        "name": "tests",
        "role": "tests",
        "shards": 2,
        "command": ["pytest", "--junitxml=j.xml"],
        "report": {"type": "python-tests", "tests": "j.xml", "coverage": "c.json"},
    }
    package = {"path": ".", "language": "python", "sources": ["."], "checks": [tests]}
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [package], "shared": []})
    )


@pytest.mark.parametrize(("shard", "marked"), [("rest", False), ("2", True)])
def test_a_shard_job_that_reuses_a_passed_commit_marks_its_shard(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    shard: str,
    marked: bool,
) -> None:
    sharded_project(tmp_path)
    reuse_every_commit(monkeypatch)
    assert runner.check(base="a" * 40, shard=shard) == 0
    assert f"Commit {'a' * 40} passed the required checks" in capsys.readouterr().out
    assert (tmp_path / "coverage/shards/2/proven.txt").is_file() is marked
    assert not (tmp_path / "coverage/shards/rest").exists()


def test_the_gate_job_takes_a_shard_proof_and_runs_none_itself(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    sharded_project(tmp_path)

    def proof_without_uv(_base: str | None) -> bool:
        raise FileNotFoundError("uv")

    monkeypatch.setattr(runner, "proven_elsewhere", proof_without_uv)
    (tmp_path / "coverage/shards/2").mkdir(parents=True)
    (tmp_path / "coverage/shards/2/proven.txt").write_text("ok\n")
    assert runner.check(base="a" * 40, shard="merge") == 0
    assert "Shard 2 proved this tree in its own job" in capsys.readouterr().out


def _diverged(push: MergedPush, base_tree: str, merge_base_tree: str) -> None:
    push.responses[f"compare/{push.base}...{push.head}"] = {
        "status": "diverged",
        "base_commit": {"commit": {"tree": {"sha": base_tree}}},
        "merge_base_commit": {"commit": {"tree": {"sha": merge_base_tree}}},
    }


def test_a_push_reuses_a_pr_head_that_starts_from_the_files_of_a_merged_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A release merge commit on the branch is not in the next PR head, but its files are."""
    push = _merged_push(tmp_path, monkeypatch, method="merge")
    _diverged(push, "b" * 40, "b" * 40)
    assert reused_pull_request(push.root, push.base) == push.head
    _diverged(push, "b" * 40, "c" * 40)
    assert reused_pull_request(push.root, push.base) is None
    assert "PR head does not contain the previous base" in capsys.readouterr().out


def test_a_push_to_another_branch_reuses_the_merged_pr_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    push = _merged_push(tmp_path, monkeypatch)
    push.pulls[0]["base"] = {"ref": "release/1"}
    monkeypatch.setenv("GITHUB_REF", "refs/heads/release/1")
    assert reused_pull_request(push.root, push.base) == push.head


@dataclass
class ReleasePR:
    root: Path
    head: str
    pull: dict[str, dict[str, object]]
    runs: list[dict[str, object]]
    event_path: Path

    def reused(self) -> str | None:
        self.event_path.write_text(json.dumps({"pull_request": self.pull}))
        return reused_pull_request(self.root, self.head)


def _release_pr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ReleasePR:
    root = _fixture(tmp_path).root
    head = _native(root, "rev-parse", "HEAD")
    _native(
        root, "commit", "-q", "--allow-empty", "-m", "Merge the PR into the release"
    )
    runs = [_check(head)]
    pull: dict[str, dict[str, object]] = {
        "head": {"ref": "main", "sha": head, "repo": {"full_name": "acme/widget"}},
        "base": {"ref": "release", "repo": {"full_name": "acme/widget"}},
    }

    def github(_root: Path, *args: str) -> str:
        endpoint = args[-1]
        assert endpoint == (
            f"repos/acme/widget/commits/{head}/check-runs?per_page=100&filter=all"
        )
        return json.dumps([{"total_count": len(runs), "check_runs": runs}])

    monkeypatch.setattr(shipping, "gh", github)
    event_path = tmp_path / "event.json"
    for name, value in {
        "GITHUB_ACTIONS": "true",
        "GITHUB_EVENT_NAME": "pull_request",
        "GITHUB_EVENT_PATH": str(event_path),
        "GITHUB_REPOSITORY": "acme/widget",
    }.items():
        monkeypatch.setenv(name, value)
    return ReleasePR(root, head, pull, runs, event_path)


def test_a_release_pr_reuses_the_passed_checks_of_the_base_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    pr = _release_pr(tmp_path, monkeypatch)
    pr.runs[:] = [
        _check(pr.head, id=1),
        _check(pr.head, id=2, conclusion="cancelled"),
        _check(pr.head, id=3, status="in_progress", conclusion=None),
    ]
    assert pr.reused() == pr.head
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("errors", "tries", "reused"),
    [
        (["gh: Server Error (HTTP 502)"] * 2, 3, True),
        (["gh: Server Error (HTTP 502)"] * 3, 3, False),
        (["gh: Not Found (HTTP 404)"], 1, False),
    ],
    ids=["two-server-errors", "three-server-errors", "not-a-server-error"],
)
def test_a_release_pr_lookup_tries_again_only_after_a_github_server_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    errors: list[str],
    tries: int,
    reused: bool,
) -> None:
    pr = _release_pr(tmp_path, monkeypatch)
    answer = shipping.gh
    asked: list[str] = []
    waits: list[float] = []

    def github(root: Path, *args: str) -> str:
        asked.append(args[-1])
        if len(asked) <= len(errors):
            raise shipping.ShippingError(f"gh query failed: {errors[len(asked) - 1]}")
        return answer(root, *args)

    monkeypatch.setattr(shipping, "gh", github)
    monkeypatch.setattr("ci_usage.sleep", waits.append)
    assert (pr.reused() == pr.head) is reused
    assert (len(asked), waits) == (tries, [2.0, 6.0][: tries - 1])
    assert (
        capsys.readouterr().out.startswith("Running the checks again; ") is not reused
    )


def _no_completed_run(pr: ReleasePR) -> None:
    pr.runs[:] = [_check(pr.head, status="in_progress", conclusion=None)]


def _newest_completed_run_failed(pr: ReleasePR) -> None:
    pr.runs[:] = [_check(pr.head, id=1), _check(pr.head, id=2, conclusion="failure")]


def _merge_tree_differs(pr: ReleasePR) -> None:
    (pr.root / "source.txt").write_text("changed by the merge\n")
    _native(pr.root, "commit", "-qam", "Change the tree")


def _head_from_a_fork(pr: ReleasePR) -> None:
    pr.pull["head"]["repo"] = {"full_name": "someone/widget"}


def _head_is_not_the_base(pr: ReleasePR) -> None:
    pr.pull["head"]["ref"] = "feature/shipping"


def _base_is_the_base(pr: ReleasePR) -> None:
    pr.pull["base"]["ref"] = "main"


@pytest.mark.parametrize(
    "break_proof",
    [_no_completed_run, _newest_completed_run_failed, _merge_tree_differs],
)
def test_a_release_pr_runs_the_checks_when_no_pass_covers_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    break_proof: Callable[[ReleasePR], None],
) -> None:
    pr = _release_pr(tmp_path, monkeypatch)
    break_proof(pr)
    assert pr.reused() is None
    reason = capsys.readouterr().out
    assert reason.startswith("Running the checks again; ")
    assert reason.strip().removeprefix("Running the checks again;").strip()


@pytest.mark.parametrize(
    "change", [_head_from_a_fork, _head_is_not_the_base, _base_is_the_base]
)
def test_an_ordinary_pr_prints_nothing_and_asks_nothing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    change: Callable[[ReleasePR], None],
) -> None:
    pr = _release_pr(tmp_path, monkeypatch)
    change(pr)
    spy = Mock(side_effect=AssertionError("no query expected"))
    monkeypatch.setattr(shipping, "gh", spy)
    monkeypatch.setattr(shipping, "git", spy)
    assert pr.reused() is None
    assert capsys.readouterr().out == ""
    assert not spy.called

"""`release_canary.py`: a push or a release PR follows the passed new-project jobs of a merged PR."""

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

import release_canary

PUSHED = "a" * 40
MERGED_HEAD = "c" * 40


def all_passed() -> list[str]:
    return [
        f"new project ({release_canary.folder(' '.join(target))}, {os_name})\tsuccess"
        for target in release_canary.CI_TARGETS
        for os_name in ("ubuntu-latest", "macos-latest")
    ]


def merged_pr_world(
    monkeypatch: pytest.MonkeyPatch,
    head_rows: list[str],
    pulls: list[str] | None = None,
    head_tree: str = "t1",
    breaks: tuple[str, Exception] | None = None,
) -> None:
    def output(command: list[str]) -> str:
        text = " ".join(command)
        if breaks and breaks[0] in text:
            raise breaks[1]
        if command[0] == "git" and command[1] == "diff":
            return "setup.py"
        if command[0] == "git":
            return "t1"
        if "check-runs" in text:
            return "\n".join(head_rows) if MERGED_HEAD in text else ""
        if text.endswith("/pulls") or "/pulls " in text:
            return "\n".join([MERGED_HEAD] if pulls is None else pulls)
        assert f"git/commits/{MERGED_HEAD}" in text
        return head_tree

    monkeypatch.setattr(release_canary, "output", output)


def test_a_develop_push_reuses_the_new_project_jobs_of_the_merged_pr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    merged_pr_world(monkeypatch, all_passed())
    assert release_canary.ci_failures(PUSHED) == []
    assert release_canary.push_outputs(["setup.py"], PUSHED) == (
        f"targets=[]\ncovered={MERGED_HEAD}"
    )
    assert release_canary.push_outputs(["README.md"], PUSHED) == "targets=[]"
    workflow = yaml.safe_load(
        (release_canary.SOURCE / ".github/workflows/canary.yml").read_text()
    )
    job = workflow["jobs"]["targets"]
    assert job["permissions"] == {
        "contents": "read",
        "checks": "read",
        "pull-requests": "read",
    }
    assert "covered" in job["outputs"]
    assert release_canary.PUSH_LOOKUP_SECONDS * 2 <= job["timeout-minutes"] * 60
    matrix = workflow["jobs"]["new-project"]["strategy"]["matrix"]
    assert tuple(matrix["os"]) == release_canary.CI_SYSTEMS
    assert matrix["exclude"] == [{"os": "macos-latest", "target": "update-python"}]
    summary = workflow["jobs"]["canary"]["steps"][0]["run"]
    assert (
        "passed every new project on these exact files; not repeating them." in summary
    )


@pytest.mark.parametrize(
    "case",
    [
        "no runs at the head",
        "a failed job",
        "other files",
        "no merged pull request",
        "no macOS runs at the head",
        "a failed run beside a passed run of one job",
        "a failed lookup",
        "a failed check-runs lookup",
        "a lookup that timed out",
    ],
)
def test_a_push_runs_the_new_projects_when_the_pr_did_not_prove_them(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    failed = [*all_passed()[1:], all_passed()[0][:-7] + "failure"]
    linux = [row for row in all_passed() if "ubuntu" in row]
    rows = {
        "no runs at the head": [],
        "a failed job": failed,
        "no macOS runs at the head": linux,
        "a failed run beside a passed run of one job": [*all_passed(), failed[-1]],
    }.get(case, all_passed())
    fault = subprocess.CalledProcessError(1, "gh")
    breaks = {
        "a failed lookup": ("/pulls", fault),
        "a failed check-runs lookup": (f"{MERGED_HEAD}/check-runs", fault),
        "a lookup that timed out": (
            f"{PUSHED}/check-runs",
            subprocess.TimeoutExpired("gh", 60),
        ),
    }
    merged_pr_world(
        monkeypatch,
        rows,
        pulls=[] if case == "no merged pull request" else None,
        head_tree="t2" if case == "other files" else "t1",
        breaks=breaks.get(case),
    )
    listed = [release_canary.folder(" ".join(t)) for t in release_canary.CI_TARGETS]
    got = release_canary.push_outputs(["setup.py"], PUSHED)
    seen = capsys.readouterr()
    assert got == "targets=" + json.dumps(listed)
    assert (seen.out, "merged PR failed" in seen.err) == ("", case in breaks)
    if case not in breaks or case == "a failed lookup":
        assert release_canary.ci_failures(PUSHED)


def test_a_push_runs_the_new_projects_when_a_lookup_stalls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (tmp_path / "gh").write_text("#!/bin/sh\nexec sleep 2\n")
    (tmp_path / "gh").chmod(0o755)
    monkeypatch.setenv("PATH", f"{tmp_path}:{os.environ['PATH']}")
    run = release_canary.output

    def output(command: list[str]) -> str:
        return "t1" if command[0] == "git" else run(command)

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary, "PUSH_LOOKUP_SECONDS", 0.2)
    listed = [release_canary.folder(" ".join(t)) for t in release_canary.CI_TARGETS]
    got = release_canary.push_outputs(["setup.py"], PUSHED)
    assert got == "targets=" + json.dumps(listed)
    assert "merged PR failed" in capsys.readouterr().err


def test_the_release_gate_follows_a_reused_push_to_the_pr_head(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    merged_pr_world(monkeypatch, all_passed())
    assert release_canary.release_pr_gate("b" * 40, PUSHED) == 0
    assert f"PR head {MERGED_HEAD}" in capsys.readouterr().out
    merged_pr_world(monkeypatch, all_passed()[2:])
    assert release_canary.release_pr_gate("b" * 40, PUSHED) == 1
    assert "Rerun this job" in capsys.readouterr().out


def release_gate(monkeypatch: pytest.MonkeyPatch, changed: str, rows: list[str]) -> int:
    def output(command: list[str]) -> str:
        return changed if command[0] == "git" else "\n".join(rows)

    monkeypatch.setattr(release_canary, "output", output)
    return release_canary.release_pr_gate("b" * 40, "a" * 40)


def test_a_release_pr_waits_for_develops_push_run_to_pass(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    passed = all_passed()
    assert release_gate(monkeypatch, "setup.py", passed) == 0
    assert release_gate(monkeypatch, "setup.py", passed[1:] + [passed[0][:-7]]) == 1
    assert "Rerun this job" in capsys.readouterr().out
    assert release_gate(monkeypatch, "setup.py", []) == 1
    assert release_gate(monkeypatch, "README.md", []) == 0


def test_a_release_pr_waits_while_develops_push_run_is_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passed = all_passed()
    replies = [passed[1:] + [passed[0][:-7] + "null"], passed, passed, passed]
    waits: list[float] = []

    def output(command: list[str]) -> str:
        return "setup.py" if command[0] == "git" else "\n".join(replies.pop(0))

    monkeypatch.setattr(release_canary, "output", output)
    monkeypatch.setattr(release_canary.time, "sleep", waits.append)
    assert release_canary.release_pr_gate("b" * 40, "a" * 40) == 0
    assert waits == [30]

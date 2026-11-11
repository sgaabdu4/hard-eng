"""The PR text rules have one owner that `ship` and CI both call."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from conftest import SOURCE
from pr_text import body_problem, event_problem
from test_shipping import (
    _DIAGRAM,
    FakeGitHub,
    _check,
    _fixture,
    _pull,
    _ready_outcome,
)

_GOOD = "Undo: revert the commits.\n" + _DIAGRAM * 2
_VALID = _GOOD + "Not checked: the Mac canary\n"


@pytest.mark.parametrize(
    ("line", "passes"),
    [
        (None, False),
        ("Not checked:", False),
        ("Not checked: None", False),
        ("Not checked: nothing.", False),
        ("**Not checked:** the Mac canary", False),
        ("Not checked: the Mac canary", True),
        ("  Not checked: the Mac canary", True),
        ("Not checked: None — docs only, CI ran every check", True),
    ],
)
def test_not_checked_needs_what_was_not_checked_or_a_reason_for_none(
    line: str | None, passes: bool
) -> None:
    body = _GOOD if line is None else f"{_GOOD}{line}\n"
    assert (body_problem(body) is None) is passes
    assert (body_problem(body.replace("\n", "\r\n")) is None) is passes


def test_ready_refuses_a_pr_body_without_a_not_checked_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, body=_GOOD), [_check(fixture.head)])
    _ready_outcome(fixture, fake, monkeypatch, "Not checked")


def _event(
    tmp_path: Path, body: str | None, *, head: str = "task", base: str = "main"
) -> str:
    event = {
        "pull_request": {
            "body": body,
            "head": {"ref": head, "repo": {"full_name": "acme/widget"}},
            "base": {"ref": base},
        }
    }
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event))
    return str(path)


def _project(tmp_path: Path, *, shipping: bool = True) -> Path:
    root = _fixture(tmp_path).root
    if not shipping:
        gates = root / "hard-eng.gates.json"
        payload = json.loads(gates.read_text())
        del payload["shipping"]
        gates.write_text(json.dumps(payload))
    return root


@pytest.mark.parametrize(
    ("body", "head", "base", "shipping", "refused"),
    [
        (None, "task", "main", True, True),
        ("", "task", "main", True, True),
        (_GOOD, "task", "main", True, True),
        (_GOOD, "task", "main", False, True),
        (_VALID, "task", "main", True, False),
        (_VALID, "task", "main", False, False),
        ("", "hard-eng/update", "main", True, False),
        ("", "task", "develop", True, False),
    ],
)
def test_event_problem_exempts_only_the_update_pr_and_other_bases(
    tmp_path: Path,
    body: str | None,
    head: str,
    base: str,
    shipping: bool,
    refused: bool,
) -> None:
    root = _project(tmp_path, shipping=shipping)
    problem = event_problem(_event(tmp_path, body, head=head, base=base), root)
    assert (problem is not None) is refused
    if problem:
        assert "Edit the PR text" in problem


def _workflow_text() -> str:
    return (SOURCE / ".github/workflows/pr-text.yml").read_text()


def _run_step(tmp_path: Path, body: str) -> subprocess.CompletedProcess[str]:
    steps = yaml.safe_load(_workflow_text())["jobs"]["pr-text"]["steps"]
    run = next(step["run"] for step in steps if "run" in step)
    work = tmp_path / "work"
    work.mkdir(parents=True)
    (work / ".hooks").symlink_to(SOURCE / ".hooks")
    shutil.copy(_project(tmp_path) / "hard-eng.gates.json", work)
    environment = {**os.environ, "GITHUB_EVENT_PATH": _event(tmp_path, body)}
    return subprocess.run(
        ["bash", "-c", run],
        check=False,
        cwd=work,
        env=environment,
        capture_output=True,
        text=True,
    )


def test_pr_text_workflow_step_fails_a_pr_whose_text_breaks_the_rules(
    tmp_path: Path,
) -> None:
    refused = _run_step(tmp_path / "bad", _GOOD)
    assert refused.returncode == 1
    assert "Not checked" in refused.stderr
    hostile = "$(touch pwned) `touch pwned` \"'\n" + _GOOD
    attack = _run_step(tmp_path / "attack", hostile)
    assert attack.returncode == 1
    assert not (tmp_path / "attack" / "work" / "pwned").exists()
    assert _run_step(tmp_path / "good", _VALID).returncode == 0


def test_pr_text_check_runs_on_each_push_and_edit_and_the_footer_job_skips_pushes() -> (
    None
):
    workflow = yaml.safe_load(_workflow_text())
    types = workflow[True]["pull_request"]["types"]
    assert {"synchronize", "edited"} <= set(types)
    footer = workflow["jobs"]["remove-claude-footer"]["if"]
    assert "github.event.action != 'synchronize'" in footer

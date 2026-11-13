"""The PR text rules have one owner that `ship` and CI both call."""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import shipping
import yaml
from conftest import SOURCE
from pr_text import body_problem, event_problem
from test_shipping import (
    _DIAGRAM,
    _UI_BODY,
    FakeGitHub,
    _check,
    _fixture,
    _patch_gh,
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
        ("Not checked: N/A", False),
        ("Not checked: n/a", False),
        ("Not checked: -", False),
        ("Not checked: None —", False),
        ("Not checked: None -", False),
        ("**Not checked:** the Mac canary", False),
        ("Not checked: the Mac canary", True),
        ("  Not checked: the Mac canary", True),
        ("- Not checked: the Mac canary", True),
        ("* Not checked: the Mac canary", True),
        ("- Not checked: N/A", False),
        ("Not checked:\n- the Mac canary", False),
        ("Not checked: None — docs only, CI ran every check", True),
    ],
)
def test_not_checked_needs_what_was_not_checked_or_a_reason_for_none(
    line: str | None, passes: bool
) -> None:
    body = _GOOD if line is None else f"{_GOOD}{line}\n"
    assert (body_problem(body) is None) is passes
    assert (body_problem(body.replace("\n", "\r\n")) is None) is passes


def test_mermaid_blocks_in_tilde_fences_count_like_backtick_fences() -> None:
    tilde = _DIAGRAM.replace("```", "~~~")
    assert body_problem("Undo: revert.\n" + tilde * 2 + "Not checked: x\n") is None
    assert body_problem("Undo: revert.\n" + tilde + "Not checked: x\n") is not None


def _lines(count: int, width: int = 49) -> str:
    return ("a" * width + "\n") * count


def _fold(text: str) -> str:
    return f"<details>\n{text}</details>\n"


def test_a_wall_of_visible_text_is_refused_but_folded_text_does_not_count() -> None:
    wall = _VALID + _lines(133)
    problem = body_problem(wall)
    assert problem is not None
    assert "limit is 6,000" in problem
    assert "<details>" in problem
    assert body_problem(_VALID + _lines(72) + _fold(_lines(61))) is None


def test_a_line_over_the_limit_is_refused_with_its_number_and_start() -> None:
    long = "start of a long line " + "b" * 700
    body = _VALID + "short\n" + long + "\n"
    problem = body_problem(body)
    lines = body.split("\n")
    assert problem is not None
    assert f"line {lines.index(long) + 1} " in problem
    assert '(it starts "start of a long line bbbbbbbbbbbbbbbbbbb")' in problem
    assert "the limit is 600" in problem


@pytest.mark.parametrize(
    "hidden",
    [
        "```\n{}\n```\n",
        "~~~\n{}\n~~~\n",
        "<details>\n{}\n</details>\n",
        "<details>\n<details>\n{}\n</details>\n</details>\n",
        "<details>\n{}\n",
        "<!-- {} -->\n",
        "[x](https://example.com/{})\n",
    ],
)
def test_long_text_in_a_code_block_fold_comment_or_link_target_is_not_visible(
    hidden: str,
) -> None:
    assert body_problem(_VALID + hidden.format("c" * 700)) is None


def test_text_after_an_unclosed_details_block_does_not_count() -> None:
    assert body_problem(_VALID + "<details>\n" + _lines(200)) is None


def test_a_big_mermaid_block_does_not_count() -> None:
    big = "```mermaid\nflowchart TD\n" + "    A --> B\n" * 900 + "```\n"
    assert body_problem(_VALID + big) is None


def test_a_long_undo_line_is_refused_as_a_long_line() -> None:
    body = "Undo: " + "revert the commits, " * 100 + "\n" + _DIAGRAM * 2
    problem = body_problem(body + "Not checked: the Mac canary\n")
    assert problem is not None
    assert "line 1 " in problem


def test_crlf_line_ends_give_the_same_line_number() -> None:
    body = _VALID + "d" * 700 + "\n"
    assert body_problem(body.replace("\n", "\r\n")) == body_problem(body)


def test_a_missing_undo_line_is_named_before_a_wall() -> None:
    problem = body_problem(_lines(200))
    assert problem is not None
    assert "Undo:" in problem


def test_event_problem_ends_a_wall_refusal_with_the_edit_hint(tmp_path: Path) -> None:
    root = _project(tmp_path)
    problem = event_problem(_event(tmp_path, _VALID + "e" * 700), root)
    assert problem is not None
    assert "the limit is 600" in problem
    assert "Edit the PR text" in problem


def test_not_checked_refusal_says_the_answer_goes_on_the_line_that_starts_it() -> None:
    problem = body_problem(f"{_GOOD}Not checked:\n- the Mac canary\n")
    assert problem is not None
    assert "a line that starts `Not checked:`, with the answer on that line" in problem


def test_ready_refuses_a_pr_body_without_a_not_checked_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = _fixture(tmp_path)
    fake = FakeGitHub(_pull(fixture, body=_GOOD), [_check(fixture.head)])
    _ready_outcome(fixture, fake, monkeypatch, "Not checked")


def _event(
    tmp_path: Path,
    body: str | None,
    *,
    head: str = "task",
    base: str = "main",
    repo: str = "acme/widget",
    author: str = "pat",
) -> str:
    event = {
        "pull_request": {
            "number": 1,
            "body": body,
            "user": {"login": author},
            "head": {"ref": head, "repo": {"full_name": repo}},
            "base": {"ref": base, "repo": {"full_name": "acme/widget"}},
        }
    }
    path = tmp_path / "event.json"
    path.write_text(json.dumps(event))
    return str(path)


def _project(
    tmp_path: Path,
    *,
    shipping: bool = True,
    bad_shipping: bool = False,
    ui_paths: list[str] | None = None,
) -> Path:
    root = _fixture(tmp_path, ui_paths=ui_paths).root
    if not shipping or bad_shipping:
        gates = root / "hard-eng.gates.json"
        payload = json.loads(gates.read_text())
        del payload["shipping"]
        if bad_shipping:
            payload["shipping"] = "develop"
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


@pytest.mark.parametrize(
    ("author", "refused"),
    [
        ("dependabot[bot]", False),
        ("renovate[bot]", False),
        ("pat", True),
        ("helper[bot]", True),
    ],
)
def test_event_problem_skips_a_dependency_bot_pr_and_checks_each_other_author(
    tmp_path: Path, author: str, refused: bool
) -> None:
    root = _project(tmp_path)
    problem = event_problem(_event(tmp_path, "", author=author), root)
    assert (problem is not None) is refused


def test_event_problem_checks_a_fork_pr_even_on_the_update_branch_name(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path)
    (tmp_path / "fork").mkdir()
    (tmp_path / "own").mkdir()
    fork = _event(tmp_path / "fork", "", head="hard-eng/update", repo="outsider/widget")
    problem = event_problem(fork, root)
    assert problem is not None
    assert "Edit the PR text" in problem
    own = _event(tmp_path / "own", "", head="hard-eng/update")
    assert event_problem(own, root) is None


def test_event_problem_treats_a_gates_file_with_a_bad_shipping_value_as_no_shipping(
    tmp_path: Path,
) -> None:
    root = _project(tmp_path, bad_shipping=True)
    refused = event_problem(_event(tmp_path, _GOOD, base="develop"), root)
    assert refused is not None
    assert event_problem(_event(tmp_path, _VALID, base="develop"), root) is None


_UNCHANGED = "UI appearance: unchanged \u2014 same screen before and after.\n"
_EDIT_HINT = "Edit the PR text; this check runs again on each edit."


def _ui_problem(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    body: str,
    files: list[dict[str, object]],
    ui_paths: list[str] | None = None,
) -> tuple[str | None, list[tuple[str, ...]]]:
    root = _project(tmp_path, ui_paths=["src/**"] if ui_paths is None else ui_paths)
    (tmp_path / "pull").mkdir()
    fake = FakeGitHub(_pull(_fixture(tmp_path / "pull")), [], files)
    _patch_gh(monkeypatch, fake)
    return event_problem(_event(tmp_path, body), root), fake.calls


def test_remote_check_refuses_a_ui_change_without_pictures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem, calls = _ui_problem(
        tmp_path, monkeypatch, _VALID, [{"filename": "src/App.tsx"}]
    )
    assert problem is not None
    assert problem.startswith("UI changes require distinct Before and After")
    assert problem.endswith(f". {_EDIT_HINT}")
    assert [call[-1] for call in calls] == [
        "repos/acme/widget/pulls/1/files?per_page=100"
    ]


@pytest.mark.parametrize("evidence", [_UI_BODY + "\n", _UNCHANGED])
def test_remote_check_accepts_a_ui_change_with_pictures_or_an_unchanged_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, evidence: str
) -> None:
    problem, _ = _ui_problem(
        tmp_path, monkeypatch, evidence + _VALID, [{"filename": "src/App.tsx"}]
    )
    assert problem is None


@pytest.mark.parametrize(
    ("changed", "refused"),
    [
        ({"filename": "README.md"}, False),
        ({"filename": "lib/new.ts", "previous_filename": "src/old.ts"}, True),
    ],
)
def test_remote_check_matches_ui_paths_on_new_and_old_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: dict[str, object],
    refused: bool,
) -> None:
    problem, _ = _ui_problem(tmp_path, monkeypatch, _VALID, [changed])
    assert (problem is not None) is refused


def test_remote_check_runs_no_files_query_without_ui_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem, calls = _ui_problem(
        tmp_path, monkeypatch, _VALID, [{"filename": "src/App.tsx"}], ui_paths=[]
    )
    assert problem is None
    assert calls == []


def test_remote_check_fails_with_one_line_when_the_files_query_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_root: Path, *_args: str) -> str:
        raise shipping.ShippingError("gh query failed")

    monkeypatch.setattr(shipping, "gh", broken)
    root = _project(tmp_path, ui_paths=["src/**"])
    problem = event_problem(_event(tmp_path, _VALID), root)
    assert problem is not None
    assert "\n" not in problem
    assert problem.startswith("The list of files that the PR changes is unavailable")
    assert "gh query failed" in problem
    assert problem.endswith(f". {_EDIT_HINT}")


def test_remote_check_reports_the_text_fault_before_missing_pictures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    problem, calls = _ui_problem(
        tmp_path, monkeypatch, _GOOD, [{"filename": "src/App.tsx"}]
    )
    assert problem is not None
    assert "Not checked" in problem
    assert calls == []


def _workflow_text() -> str:
    return (SOURCE / ".github/workflows/pr-text.yml").read_text()


def _run_step(
    tmp_path: Path, body: str, current: str | None = None
) -> subprocess.CompletedProcess[str]:
    steps = yaml.safe_load(_workflow_text())["jobs"]["pr-text"]["steps"]
    run = next(step["run"] for step in steps if "run" in step)
    work, tools, now, temp = (
        tmp_path / name for name in ("work", "tools", "now", "temp")
    )
    for folder in (work, tools, now, temp):
        folder.mkdir(parents=True)
    (work / ".hooks").symlink_to(SOURCE / ".hooks")
    shutil.copy(_project(tmp_path) / "hard-eng.gates.json", work)
    stand_in = tools / "gh"
    stand_in.write_text('#!/bin/sh\necho "$*" > "$GH_ASKED"\ncat "$GH_ANSWER"\n')
    stand_in.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_EVENT_PATH": _event(tmp_path, body),
        "GH_ANSWER": str(now / "none") if current is None else _event(now, current),
        "GH_ASKED": str(tmp_path / "asked"),
        "RUNNER_TEMP": str(temp),
        "PR": "1",
        "REPO": "acme/widget",
    }
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


def test_the_step_judges_the_text_that_the_pr_has_now_not_the_text_of_the_event(
    tmp_path: Path,
) -> None:
    mended = _run_step(tmp_path / "mended", _GOOD, current=_VALID)
    assert mended.returncode == 0
    asked = (tmp_path / "mended" / "asked").read_text()
    assert asked == "api repos/acme/widget/pulls/1 --jq {pull_request: .}\n"
    broken = _run_step(tmp_path / "broken", _VALID, current=_GOOD)
    assert broken.returncode == 1
    assert "Not checked" in broken.stderr


def test_a_new_event_waits_for_the_running_pr_text_job_and_never_cancels_it() -> None:
    job = yaml.safe_load(_workflow_text())["jobs"]["pr-text"]
    assert job["concurrency"] == {
        "group": "pr-text-check-${{ github.event.pull_request.number }}",
        "cancel-in-progress": False,
    }


def test_pr_text_check_runs_on_each_push_and_edit_and_the_footer_job_skips_pushes() -> (
    None
):
    workflow = yaml.safe_load(_workflow_text())
    types = workflow[True]["pull_request"]["types"]
    assert {"opened", "edited", "synchronize", "reopened"} <= set(types)
    assert "if" not in workflow["jobs"]["pr-text"]
    footer = workflow["jobs"]["remove-claude-footer"]["if"]
    assert "github.event.action != 'synchronize'" in footer


def test_each_job_holds_its_own_concurrency_group_so_a_push_cannot_cancel_the_footer() -> (
    None
):
    workflow = yaml.safe_load(_workflow_text())
    assert "concurrency" not in workflow
    assert workflow["jobs"]["remove-claude-footer"]["concurrency"] == {
        "group": (
            "pr-text-${{ github.event.pull_request.number }}-"
            "${{ github.event.action == 'synchronize' && github.run_id || 'footer' }}"
        ),
        "cancel-in-progress": False,
    }


def test_pr_text_job_reads_the_pr_files_with_the_workflow_token_and_nothing_more() -> (
    None
):
    job = yaml.safe_load(_workflow_text())["jobs"]["pr-text"]
    assert job["permissions"] == {"contents": "read", "pull-requests": "read"}
    check = next(step for step in job["steps"] if "run" in step)
    assert check["env"] == {
        "GH_TOKEN": "${{ github.token }}",
        "PR": "${{ github.event.pull_request.number }}",
        "REPO": "${{ github.repository }}",
    }

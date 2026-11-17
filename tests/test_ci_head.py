"""In CI, a check refuses a tree that is not the commit GitHub started the run for."""

import json
from pathlib import Path

import pytest
from ci_setup import require_ci_base
from conftest import commit, git, init

EVENTS = ["pull_request", "push", "workflow_dispatch", "schedule"]


def merge_commit(tmp_path: Path) -> tuple[Path, str, str, str]:
    """A pull request run starts on the merge commit of the base and the head."""
    root = tmp_path / "repo"
    init(root)
    (root / "a.txt").write_text("base\n")
    base = commit(root, "base")
    git(root, "checkout", "-qb", "topic")
    (root / "b.txt").write_text("head\n")
    head = commit(root, "head")
    git(root, "checkout", "-q", "--detach", base)
    git(root, "merge", "--no-ff", "-qm", "merge", head)
    return root, base, head, git(root, "rev-parse", "HEAD")


def in_ci(
    monkeypatch: pytest.MonkeyPatch, event: str, sha: str, payload: Path | None = None
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_SHA", sha)
    if payload:
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(payload))


def test_the_merge_commit_of_a_pull_request_run_passes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """GITHUB_SHA is the merge commit, not `pull_request.head.sha` of the event file, and the default checkout uses it."""
    root, base, head, merge = merge_commit(tmp_path)
    event = tmp_path / "event.json"
    event.write_text(
        json.dumps({"pull_request": {"head": {"sha": head}, "base": {"sha": base}}})
    )
    in_ci(monkeypatch, "pull_request", merge, event)
    require_ci_base(base, root)


@pytest.mark.parametrize("moved", ["HEAD~1", "HEAD^2"])
def test_a_checkout_of_another_commit_before_the_check_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, moved: str
) -> None:
    """A `ref:` on the checkout step or an early `git checkout` leaves HEAD on another commit, and the check would judge that one."""
    root, base, _, merge = merge_commit(tmp_path)
    in_ci(monkeypatch, "pull_request", merge)
    git(root, "checkout", "-q", "--detach", moved)
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, root)


@pytest.mark.parametrize("event", EVENTS)
def test_the_run_commit_passes_for_every_event_that_checks_out_its_own_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    root, base, _, merge = merge_commit(tmp_path)
    in_ci(monkeypatch, event, merge)
    require_ci_base(base, root)


def test_a_local_run_has_no_run_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, _, _ = merge_commit(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    require_ci_base(base, root)

"""In CI, a check refuses a tree that is not the commit GitHub started the run for."""

import json
from pathlib import Path

import pytest
from ci_setup import require_ci_base
from conftest import commit, git, init

EVENTS = ["pull_request", "push", "workflow_dispatch", "schedule"]


def merge_commit(tmp_path: Path, name: str = "repo") -> tuple[Path, str, str, str]:
    """A pull request run starts on the merge commit of the base and the head."""
    root = tmp_path / name
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
    monkeypatch: pytest.MonkeyPatch,
    event: str,
    sha: str,
    workspace: Path,
    payload: Path | None = None,
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", event)
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("GITHUB_WORKSPACE", str(workspace))
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
    in_ci(monkeypatch, "pull_request", merge, root, event)
    require_ci_base(base, root)


@pytest.mark.parametrize("moved", ["HEAD~1", "HEAD^2"])
def test_a_checkout_of_another_commit_before_the_check_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, moved: str
) -> None:
    """A `ref:` on the checkout step or an early `git checkout` leaves HEAD on another commit, and the check would judge that one."""
    root, base, _, merge = merge_commit(tmp_path)
    in_ci(monkeypatch, "pull_request", merge, root)
    git(root, "checkout", "-q", "--detach", moved)
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, root)


@pytest.mark.parametrize("event", EVENTS)
def test_the_run_commit_passes_for_every_event_that_checks_out_its_own_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    root, base, _, merge = merge_commit(tmp_path)
    in_ci(monkeypatch, event, merge, root)
    require_ci_base(base, root)


def test_a_local_run_has_no_run_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, base, _, _ = merge_commit(tmp_path)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    require_ci_base(base, root)


def test_a_repository_other_than_the_workspace_is_judged_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tests and the canary run `check` in other repositories while GITHUB_SHA names the commit of the workspace checkout."""
    workspace, base, _, merge = merge_commit(tmp_path)
    other = tmp_path / "other"
    init(other)
    (other / "x.txt").write_text("x\n")
    commit(other, "x")
    in_ci(monkeypatch, "push", merge, workspace)
    require_ci_base(base, other)
    nested = workspace / "nested"
    init(nested)
    (nested / "y.txt").write_text("y\n")
    commit(nested, "y")
    require_ci_base(base, nested)


def test_the_workspace_repository_at_another_commit_is_still_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, base, _, merge = merge_commit(tmp_path)
    in_ci(monkeypatch, "push", merge, workspace)
    git(workspace, "checkout", "-q", "--detach", "HEAD~1")
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, workspace)
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, workspace / ".")


OWN = "https://github.com/owner/hard-eng.git"


def in_job_repository(
    monkeypatch: pytest.MonkeyPatch, workspace: Path, sha: str
) -> None:
    in_ci(monkeypatch, "push", sha, workspace)
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/hard-eng")


def test_a_checkout_with_a_path_below_the_workspace_is_still_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`actions/checkout` with `path:` puts the job's repository in a subfolder of the workspace."""
    workspace = tmp_path / "work"
    (workspace / "src").mkdir(parents=True)
    root, base, _, merge = merge_commit(workspace / "src", "hard-eng")
    git(root, "remote", "add", "origin", OWN)
    in_job_repository(monkeypatch, workspace, merge)
    require_ci_base(base, root)
    git(root, "checkout", "-q", "--detach", "HEAD~1")
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, root)


def test_a_package_below_the_workspace_repository_is_still_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, base, _, merge = merge_commit(tmp_path)
    package = workspace / "packages" / "app"
    package.mkdir(parents=True)
    in_job_repository(monkeypatch, workspace, merge)
    git(workspace, "checkout", "-q", "--detach", "HEAD~1")
    with pytest.raises(ValueError, match="GITHUB_SHA"):
        require_ci_base(base, package)


def test_another_repository_inside_the_workspace_is_judged_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, base, _, merge = merge_commit(tmp_path)
    second = workspace / "vendor" / "tool"
    second.parent.mkdir()
    init(second)
    (second / "a.txt").write_text("a\n")
    commit(second, "a")
    git(second, "remote", "add", "origin", "https://github.com/owner/tool.git")
    in_job_repository(monkeypatch, workspace, merge)
    require_ci_base(base, second)


def test_a_clone_of_the_job_repository_outside_the_workspace_is_judged_normally(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, base, _, merge = merge_commit(tmp_path)
    git(workspace, "remote", "add", "origin", OWN)
    clone = tmp_path / "elsewhere" / "clone"
    clone.parent.mkdir()
    git(tmp_path, "clone", "-q", str(workspace), str(clone))
    git(clone, "remote", "set-url", "origin", OWN)
    git(clone, "checkout", "-q", "--detach", "HEAD~1")
    in_job_repository(monkeypatch, workspace, merge)
    require_ci_base(base, clone)

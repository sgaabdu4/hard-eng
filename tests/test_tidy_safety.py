"""Safety rules of the tidy: what it keeps, and what it never writes."""

import fcntl
import os
import shutil
from pathlib import Path

import pytest
import stale_updates
from conftest import commit, git
from test_tidy import (
    age,
    age_branch,
    branches,
    build_primary,
    fake_gh,
    git_path,
    linked,
    tidy,
    unmerged,
)


@pytest.fixture
def primary(repository: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return build_primary(repository, tmp_path, monkeypatch)


def test_tidy_keeps_a_branch_whose_only_difference_is_whitespace(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (primary / "ind.py").write_text("if x:\n    y = 1\n")
    commit(primary, "base file")
    git(primary, "switch", "-qc", "reindent")
    (primary / "ind.py").write_text("if x:\n  y = 1\n")
    commit(primary, "two spaces")
    git(primary, "switch", "-q", "main")
    (primary / "ind.py").write_text("if x:\n        y = 1\n")
    commit(primary, "eight spaces")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-qc", "parking")
    for name in ("reindent", "parking"):
        age_branch(primary, name)
    age(primary)
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    session = linked(primary, "session")
    tidy(session)
    assert "reindent" in branches(primary)


@pytest.mark.parametrize("kept_by", ["worktree-reset", "detached", "branch-only"])
def test_tidy_keeps_work_that_only_a_reflog_holds(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kept_by: str
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    holder = linked(primary, "holder")
    if kept_by == "detached":
        git(holder, "switch", "-q", "--detach")
    unmerged(holder)
    if kept_by == "branch-only":
        git(primary, "worktree", "remove", "--force", str(holder))
        git(primary, "branch", "-f", "holder", "main")
        age_branch(primary, "holder")
    elif kept_by == "detached":
        git(holder, "checkout", "-q", "--detach", "main")
        age(holder)
    else:
        git(holder, "reset", "-q", "--hard", "main")
        age(holder)
    session = linked(primary, "session")
    tidy(session)
    assert holder.is_dir() == (kept_by != "branch-only")
    assert ("holder" in branches(primary)) == (kept_by != "detached")


@pytest.mark.parametrize("flag", ["--assume-unchanged", "--skip-worktree"])
def test_tidy_keeps_a_worktree_with_hidden_edits(primary: Path, flag: str) -> None:
    hidden = linked(primary, "hidden")
    git(hidden, "update-index", flag, "tracked.txt")
    (hidden / "tracked.txt").write_text("edited and hidden\n")
    age(hidden)
    gone = linked(primary, "gone")
    tidy(primary)
    assert hidden.is_dir() and not gone.exists()


@pytest.mark.parametrize(
    "marker",
    [
        "rebase-merge",
        "rebase-apply",
        "BISECT_LOG",
        "MERGE_HEAD",
        "CHERRY_PICK_HEAD",
        "REVERT_HEAD",
    ],
)
def test_tidy_keeps_a_worktree_in_the_middle_of_a_git_operation(
    primary: Path, marker: str
) -> None:
    busy = linked(primary, "midway")
    folder = git_path(busy, marker)
    if marker.startswith("rebase"):
        folder.mkdir()
    else:
        folder.write_text("x\n")
    gone = linked(primary, "gone")
    tidy(primary)
    assert busy.is_dir() and not gone.exists()


def test_tidy_goes_on_after_a_worktree_with_no_commits(
    primary: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "wt-aaa-empty"
    git(primary, "worktree", "add", "-q", "--orphan", "-b", "empty", str(empty))
    gone = linked(primary, "zzz-gone")
    tidy(primary)
    assert empty.is_dir() and not gone.exists()
    assert "stopped" not in capsys.readouterr().err


def test_tidy_removes_a_merged_worktree_whose_log_is_long(primary: Path) -> None:
    long = linked(primary, "long")
    for number in range(120):
        git(long, "commit", "--allow-empty", "-qm", f"step {number}")
    git(primary, "merge", "-q", "--ff-only", "long")
    git(primary, "push", "-q", "origin", "main")
    age(long)
    age(primary)
    session = linked(primary, "session")
    tidy(session)
    assert not long.exists()


def test_tidy_removes_a_squash_merged_worktree_with_a_long_log(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    long = linked(primary, "long")
    for number in range(120):
        (long / f"f{number}.txt").write_text("x\n")
        commit(long, f"step {number}")
    git(primary, "merge", "-q", "--squash", "long")
    git(primary, "commit", "-qm", "squash of long")
    git(primary, "push", "-q", "origin", "main")
    git(long, "reset", "-q", "--hard", "main")
    age(long)
    age(primary)
    session = linked(primary, "session")
    tidy(session)
    assert not long.exists()
    assert "long" not in branches(primary)


def test_tidy_keeps_a_file_that_only_an_earlier_logged_commit_holds(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    holder = linked(primary, "holder")
    (holder / "draft.txt").write_text("only here\n")
    commit(holder, "add a draft")
    git(holder, "rm", "-q", "draft.txt")
    git(holder, "commit", "-qm", "remove the draft")
    git(holder, "reset", "-q", "--hard", "main")
    age(holder)
    session = linked(primary, "session")
    tidy(session)
    assert holder.is_dir()


def test_tidy_removes_an_amended_branch_after_it_was_merged(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    amended = linked(primary, "amended")
    (amended / "a.txt").write_text("a\n")
    commit(amended, "first version")
    (amended / "b.txt").write_text("b\n")
    git(amended, "add", "b.txt")
    git(amended, "commit", "-q", "--amend", "--no-edit")
    git(primary, "merge", "-q", "--ff-only", "amended")
    git(primary, "push", "-q", "origin", "main")
    age(amended)
    age(primary)
    session = linked(primary, "session")
    tidy(session)
    assert not amended.exists()
    assert "amended" not in branches(primary)


def test_tidy_keeps_a_branch_with_unrelated_history_and_goes_on(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    git(primary, "switch", "-q", "--orphan", "separate")
    (primary / "other.txt").write_text("other\n")
    commit(primary, "separate history")
    git(primary, "switch", "-qc", "parking", "main")
    age_branch(primary, "separate")
    age_branch(primary, "parking")
    age(primary)
    gone = linked(primary, "gone")
    tidy(primary)
    assert "separate" in branches(primary)
    assert not gone.exists()
    assert "stopped" not in capsys.readouterr().err


def loose_objects(root: Path) -> int:
    counts = git(root, "count-objects", "-v").splitlines()
    return int(next(line for line in counts if line.startswith("count:")).split()[1])


def test_tidy_writes_no_objects_into_the_repository_and_leaves_no_scratch_folder(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    git(primary, "switch", "-qc", "diverged")
    (primary / "tracked.txt").write_text("changed on the branch\n")
    commit(primary, "branch edit")
    git(primary, "switch", "-q", "main")
    (primary / "tracked.txt").write_text("changed on the base\n")
    commit(primary, "base edit")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-qc", "parking")
    for name in ("diverged", "parking"):
        age_branch(primary, name)
    age(primary)
    session = linked(primary, "session")
    before = loose_objects(primary)
    tidy(session)
    assert "diverged" in branches(primary)
    assert loose_objects(primary) == before
    assert not list((tmp_path / "tmp").glob("hard-eng-tidy-*"))


def gh_calls(calls: Path) -> list[str]:
    return calls.read_text().splitlines() if calls.exists() else []


def test_tidy_asks_gh_only_after_every_local_check_passed(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_gh(tmp_path, monkeypatch, {"open": {}})
    dirty = linked(primary, "dirty")
    unmerged(dirty)
    (dirty / "tracked.txt").write_text("changed\n")
    stashed = linked(primary, "stashed")
    unmerged(stashed)
    (stashed / "tracked.txt").write_text("changed\n")
    git(stashed, "stash")
    age(stashed)
    recent = linked(primary, "recent")
    unmerged(recent)
    os.utime(recent / "tracked.txt", None)
    control = linked(primary, "control")
    unmerged(control)
    git(primary, "worktree", "remove", "--force", str(control))
    tidy(primary)
    assert gh_calls(calls) == [
        "pr list --repo fixture/project --state merged --head control --base main --json headRefOid"
    ]


def test_a_kept_branch_costs_no_gh_call_on_the_next_pass(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = fake_gh(tmp_path, monkeypatch, {"open": {"with-pr": [{"number": 7}]}})
    lasting = linked(primary, "lasting")
    unmerged(lasting)
    git(primary, "worktree", "remove", "--force", str(lasting))
    git(primary, "branch", "with-pr", "main")
    age_branch(primary, "with-pr")
    git(primary, "push", "-q", "origin", "with-pr")
    session = linked(primary, "session")
    tidy(session)
    first = gh_calls(calls)
    assert len(first) == 2
    tidy(session)
    assert gh_calls(calls) == first
    assert {"lasting", "with-pr"} <= branches(primary)
    assert (primary / ".git/hard-eng-tidy-gh.json").is_file()


def test_the_tidy_lock_lives_in_the_common_git_folder_for_every_worktree(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:

    first, second = linked(primary, "first"), linked(primary, "second")
    gone = linked(primary, "gone")
    assert (
        stale_updates.common_dir(first)
        == stale_updates.common_dir(second)
        == (primary / ".git").resolve()
    )
    with (primary / ".git/hard-eng-tidy.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        tidy(first)
        tidy(second)
    assert gone.is_dir()
    assert capsys.readouterr().err.count("another tidy is running") == 2


def test_status_fetch_and_a_full_tidy_pass_leave_an_idle_worktree_idle(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    resting = linked(primary, "resting")
    unmerged(resting)
    session = linked(primary, "session")

    def is_idle() -> bool:
        opened = stale_updates.Tidy.open(session, stale_updates.Counter())
        try:
            return opened.idle_worktree(resting)
        finally:
            shutil.rmtree(opened.scratch, ignore_errors=True)

    touched = resting.stat().st_mtime_ns
    assert is_idle()
    git(resting, "status")
    assert is_idle()
    git(resting, "fetch", "-q", "origin")
    assert is_idle()
    tidy(session)
    assert resting.is_dir()
    assert is_idle()
    assert resting.stat().st_mtime_ns == touched

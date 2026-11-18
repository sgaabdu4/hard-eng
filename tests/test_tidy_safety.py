"""Safety rules of the tidy: what it keeps, and what it never writes."""

import fcntl
import os
from pathlib import Path

import pytest
import stale_updates
import tidy_guards
from conftest import OLD, age_branch, commit, git
from test_tidy import (
    add_vendor,
    age,
    branches,
    fake_gh,
    linked,
    retire_after_merge,
    sparse_worktree,
    squash_merged_steps,
    tidy,
    unmerged,
)


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


def test_tidy_keeps_a_branch_that_only_a_reflog_holds(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    holder = linked(primary, "holder")
    unmerged(holder)
    git(primary, "worktree", "remove", "--force", str(holder))
    git(primary, "branch", "-f", "holder", "main")
    age_branch(primary, "holder")
    tidy(linked(primary, "session"))
    assert "holder" in branches(primary)


def test_tidy_removes_a_merged_branch_whose_log_is_long(primary: Path) -> None:
    long = linked(primary, "long")
    for number in range(120):
        git(long, "commit", "--allow-empty", "-qm", f"step {number}")
    git(primary, "merge", "-q", "--ff-only", "long")
    retire_after_merge(primary, long, "long")
    assert "long" not in branches(primary)


def test_tidy_removes_a_squash_merged_branch_with_a_long_log(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    squash_merged_steps(primary, "long", 120)
    assert "long" not in branches(primary)


def test_tidy_keeps_a_branch_that_only_an_earlier_logged_commit_holds(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    holder = linked(primary, "holder")
    (holder / "draft.txt").write_text("only here\n")
    commit(holder, "add a draft")
    git(holder, "rm", "-q", "draft.txt")
    git(holder, "commit", "-qm", "remove the draft")
    git(holder, "reset", "-q", "--hard", "main")
    git(primary, "worktree", "remove", "--force", str(holder))
    age_branch(primary, "holder")
    tidy(linked(primary, "session"))
    assert "holder" in branches(primary)


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
    git(primary, "worktree", "remove", "--force", str(amended))
    age_branch(primary, "amended")
    age(primary)
    tidy(linked(primary, "session"))
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
    git(primary, "branch", "gone", "main")
    age_branch(primary, "gone")
    age(primary)
    tidy(primary)
    assert "separate" in branches(primary)
    assert "gone" not in branches(primary)
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
    stashed = linked(primary, "stashed")
    unmerged(stashed)
    (stashed / "tracked.txt").write_text("changed\n")
    git(stashed, "stash")
    git(primary, "worktree", "remove", "--force", str(stashed))
    git(primary, "branch", "recent", "main")
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
    git(primary, "branch", "gone", "main")
    age_branch(primary, "gone")
    assert (
        stale_updates.common_dir(first)
        == stale_updates.common_dir(second)
        == (primary / ".git").resolve()
    )
    with (primary / ".git/hard-eng-tidy.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        tidy(first)
        tidy(second)
    assert "gone" in branches(primary)
    assert capsys.readouterr().err.count("another tidy is running") == 2


def test_status_fetch_and_a_full_tidy_pass_leave_an_idle_worktree_idle(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    resting = linked(primary, "resting")
    unmerged(resting)
    session = linked(primary, "session")

    def is_idle() -> bool:
        return tidy_guards.idle_worktree(resting)

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


def test_a_worktree_whose_nested_tracked_file_was_touched_lately_counts_as_used(
    primary: Path,
) -> None:
    (primary / "src/app").mkdir(parents=True)
    (primary / "src/app/file.py").write_text("value = 1\n")
    commit(primary, "nested file")
    git(primary, "push", "-q", "origin", "main")
    used = linked(primary, "used")
    (used / "src/app/file.py").write_text("value = 2\n")
    (used / "src/app/file.py").write_text("value = 1\n")
    for folder in (used / "src/app", used / "src", used):
        os.utime(folder, (OLD, OLD))
    assert not tidy_guards.idle_worktree(used)


def test_a_worktree_whose_submodule_file_was_touched_lately_counts_as_used(
    primary: Path, tmp_path: Path
) -> None:
    allow = add_vendor(primary, tmp_path)
    used = linked(primary, "used")
    git(used, *allow, "submodule", "update", "--init", "-q")
    age(used)
    os.utime(used / "vendor/lib.txt", None)
    assert not tidy_guards.idle_worktree(used)


def test_a_tracked_path_that_a_sparse_checkout_left_out_does_not_make_a_worktree_busy(
    primary: Path,
) -> None:
    sparse = sparse_worktree(primary)
    assert tidy_guards.idle_worktree(sparse)


def test_a_deleted_tracked_file_makes_a_worktree_count_as_used(primary: Path) -> None:
    (primary / "lib").mkdir()
    (primary / "lib/b.txt").write_text("b\n")
    commit(primary, "a folder")
    git(primary, "push", "-q", "origin", "main")
    edited = linked(primary, "edited")
    (edited / "lib/b.txt").unlink()
    age(edited)
    assert not tidy_guards.idle_worktree(edited)

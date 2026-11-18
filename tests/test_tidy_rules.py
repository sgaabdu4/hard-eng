"""The tidy keeps work that a repository setting, a paused operation or a path spelling could hide."""

import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import stale_updates
import tidy_guards
from conftest import OLD, age_branch, commit, git, git_path
from test_tidy import add_vendor, age, branches, linked, sparse_worktree, tidy


def diverge(primary: Path, how: str) -> None:
    """A branch that holds a change the base never took, while a setting makes a merge look empty."""
    if how == "info":
        git_path(primary, "info/attributes").write_text("tracked.txt merge=ours\n")
    else:
        driver = "union" if how == "union" else "ours"
        (primary / ".gitattributes").write_text(f"tracked.txt merge={driver}\n")
        commit(primary, "attributes")
    if how != "union":
        git(primary, "config", "merge.ours.driver", "true")
    git(primary, "switch", "-qc", "edge")
    (primary / "tracked.txt").write_text("feature\n")
    commit(primary, "feature")
    git(primary, "switch", "-q", "main")
    (primary / "tracked.txt").write_text("other\n")
    commit(primary, "other")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-qc", "parking")
    age_branch(primary, "edge")


@pytest.mark.parametrize("how", ["tree", "info", "union"])
def test_tidy_keeps_a_branch_when_a_merge_setting_would_hide_its_change(
    primary: Path, how: str
) -> None:
    diverge(primary, how)
    tidy(linked(primary, "session"))
    assert "edge" in branches(primary)


def pause_rebase(primary: Path) -> None:
    git(primary, "switch", "-qc", "feat")
    (primary / "f.txt").write_text("f\n")
    commit(primary, "f")
    git(primary, "switch", "-q", "main")
    git(primary, "cherry-pick", "feat")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-q", "feat")
    editor = primary.parent / "break-editor"
    editor.write_text('#!/bin/sh\nprintf "break\\n" > "$1"\n')
    editor.chmod(0o755)
    git(primary, "-c", f"sequence.editor={editor}", "rebase", "-i", "main")
    (primary / "new.txt").write_text("written while paused\n")
    commit(primary, "written while paused")


def pause_bisect(primary: Path) -> None:
    git(primary, "switch", "-qc", "feat")
    for name in ("a", "b", "c"):
        (primary / f"{name}.txt").write_text(f"{name}\n")
        commit(primary, name)
    git(primary, "switch", "-q", "main")
    git(primary, "merge", "-q", "--ff-only", "feat")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-q", "feat")
    git(primary, "bisect", "start", "feat", "feat~2")


@pytest.mark.parametrize("pause", [pause_rebase, pause_bisect])
def test_tidy_keeps_a_branch_that_a_paused_operation_will_return_to(
    primary: Path, pause: Callable[[Path], None]
) -> None:
    pause(primary)
    age_branch(primary, "feat")
    tidy(linked(primary, "session"))
    assert "feat" in branches(primary)


def test_tidy_keeps_a_worktree_when_a_process_path_differs_only_in_letter_case(
    primary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy = linked(primary, "busy")
    session = linked(primary, "session")
    monkeypatch.setattr(
        stale_updates, "open_paths", lambda: {str(busy.resolve()).swapcase() + "/x"}
    )
    tidy(session)
    assert busy.is_dir()


@pytest.mark.parametrize(
    ("name", "inside"),
    [
        ("/Work/CAFÉ/file", True),
        ("/work/café", True),
        ("/work/cafés/file", False),
        ("/other/café", False),
    ],
)
def test_a_path_matches_after_letter_case_and_unicode_form_are_folded(
    name: str, inside: bool
) -> None:
    assert tidy_guards.inside(Path("/work/café"), {name}) is inside
    assert tidy_guards.under(name, "/work/café") is inside


def test_the_codex_folder_and_session_match_in_any_letter_case() -> None:
    assert tidy_guards.under("/HOME/me/.codex/worktrees/a", "/home/me/.codex/worktrees")
    assert tidy_guards.same_place(Path("/Work/Tree"), Path("/work/tree"))


WHO = ["-c", "user.name=T", "-c", "user.email=t@example.invalid"]


def leave_submodule_commit_in_log(primary: Path, path: Path, allow: list[str]) -> None:
    git(path, *allow, "submodule", "update", "--init", "-q")
    git(path / "vendor", *WHO, "commit", "--allow-empty", "-qm", "left behind")
    git(path, *allow, "submodule", "update", "-q", "--force")


def keep_stash_commit_in_a_worktree_ref(
    primary: Path, path: Path, allow: list[str]
) -> None:
    (path / "tracked.txt").write_text("edited\n")
    saved = git(path, "stash", "create")
    git(path, "update-ref", "refs/worktree/keep", saved)
    git(path, "checkout", "--", "tracked.txt")


def leave_a_note_in_the_git_folder(primary: Path, path: Path, allow: list[str]) -> None:
    (Path(git(path, "rev-parse", "--absolute-git-dir")) / "NOTES.md").write_text("n\n")


@pytest.mark.parametrize(
    "setup",
    [
        leave_submodule_commit_in_log,
        keep_stash_commit_in_a_worktree_ref,
        leave_a_note_in_the_git_folder,
    ],
)
def test_tidy_keeps_a_worktree_whose_private_git_folder_holds_work(
    primary: Path, tmp_path: Path, setup: Callable[[Path, Path, list[str]], None]
) -> None:
    allow = add_vendor(primary, tmp_path)
    path = linked(primary, "private")
    setup(primary, path, allow)
    age(path)
    tidy(primary)
    assert path.is_dir()


def test_tidy_removes_a_sparse_worktree_whose_skipped_files_are_absent(
    primary: Path,
) -> None:
    sparse = sparse_worktree(primary)
    tidy(primary)
    assert not sparse.exists()


def test_tidy_keeps_a_worktree_with_a_present_skip_worktree_file(primary: Path) -> None:
    present = linked(primary, "present")
    git(present, "update-index", "--skip-worktree", "tracked.txt")
    age(present)
    tidy(primary)
    assert present.is_dir()


def test_tidy_says_why_it_keeps_a_locked_or_gone_worktree(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    locked = linked(primary, "locked")
    git(primary, "worktree", "lock", str(locked))
    gone = linked(primary, "gone")
    shutil.rmtree(gone)
    tidy(linked(primary, "session"))
    said = capsys.readouterr().err
    assert f"kept worktree {locked}: locked" in said
    assert f"kept worktree {gone}: its folder is gone" in said


def test_tidy_writes_what_it_removes_to_a_file_in_the_common_git_folder(
    primary: Path,
) -> None:
    done = linked(primary, "done")
    head = git(done, "rev-parse", "HEAD")
    log = (
        Path(git(primary, "rev-parse", "--absolute-git-dir"))
        / "hard-eng-tidy-removed.log"
    )
    log.write_text(f"{int(time.time()) - 40 * 86400} branch old {head}\n")
    tidy(linked(primary, "session"))
    rows = [row.partition(" ")[2] for row in log.read_text().splitlines()]
    assert rows == [f"worktree {done} {head}", f"branch done {head}"]
    git(primary, "branch", "done", head)


def test_tidy_keeps_a_worktree_whose_orig_head_is_the_last_reference_to_a_commit(
    primary: Path,
) -> None:
    path = linked(primary, "reset")
    git(path, "switch", "-q", "--detach")
    (path / "own.txt").write_text("own\n")
    commit(path, "own work")
    git(path, "reset", "-q", "--hard", "main")
    main = git(path, "rev-parse", "HEAD")
    git_path(path, "logs/HEAD").write_text(
        f"{main} {main} T <t@example.invalid> {OLD} +0000\treset: moving to main\n"
    )
    age(path)
    tidy(primary)
    assert path.is_dir()


def gc_now(primary: Path) -> None:
    git(primary, "reflog", "expire", "--expire=now", "--all")
    git(primary, "gc", "-q", "--prune=now")


def resolves(primary: Path, commit: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=primary,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_a_removed_branch_with_a_net_change_of_zero_survives_a_garbage_collection(
    primary: Path,
) -> None:
    git(primary, "switch", "-qc", "zero")
    (primary / "z.txt").write_text("z\n")
    first = commit(primary, "add")
    git(primary, "rm", "-q", "z.txt")
    tip = commit(primary, "revert")
    git(primary, "switch", "-qc", "parking", "main")
    age_branch(primary, "zero")
    tidy(linked(primary, "session"))
    assert "zero" not in branches(primary)
    gc_now(primary)
    assert resolves(primary, tip) and resolves(primary, first)


def test_rescue_refs_expire_after_thirty_days_and_no_other_reader_lists_them(
    primary: Path,
) -> None:
    head = git(primary, "rev-parse", "HEAD")
    old = "refs/hard-eng/tidy/20200101T000000Z/0"
    new = f"refs/hard-eng/tidy/{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}/0"
    git(primary, "update-ref", old, head)
    git(primary, "update-ref", new, head)
    tidy(linked(primary, "session"))
    names = git(primary, "for-each-ref", "--format=%(refname)", "refs/hard-eng").split()
    assert names == [new]
    assert branches(primary) == {"main", "session"}


def nested_repository(path: Path) -> None:
    inner = path / ".venv/src/pkg"
    inner.mkdir(parents=True)
    git(inner, "init", "-q")
    (inner / "m.txt").write_text("m\n")
    git(inner, "add", ".")
    git(inner, *WHO, "commit", "-qm", "unpushed")


def fresh_file(path: Path) -> None:
    (path / "node_modules/pkg").mkdir(parents=True)
    (path / "node_modules/pkg/index.js").write_text("x\n")
    age(path)
    (path / "node_modules/pkg/edited.js").write_text("edited a moment ago\n")


def dropped_in_submodule_folder(path: Path) -> None:
    (path / "vendor").mkdir(exist_ok=True)
    (path / "vendor/dropped.txt").write_text("dropped\n")


def old_install(path: Path) -> None:
    (path / "node_modules/pkg").mkdir(parents=True)
    (path / "node_modules/pkg/index.js").write_text("x\n")
    (path / "src/__pycache__").mkdir(parents=True)
    (path / "src/__pycache__/m.pyc").write_text("c\n")
    (path / ".venv/bin").mkdir(parents=True)
    (path / ".venv/bin/python").symlink_to("/usr/bin/true")


def ordinary_git_files(path: Path) -> None:
    git_path(path, "COMMIT_EDITMSG").write_text("msg\n")
    git_path(path, "FETCH_HEAD").write_text("")


@pytest.mark.parametrize(
    ("setup", "kept"),
    [
        (nested_repository, True),
        (fresh_file, True),
        (dropped_in_submodule_folder, True),
        (old_install, False),
        (ordinary_git_files, False),
    ],
)
def test_tidy_tests_what_the_removal_deletes_in_every_untracked_or_ignored_path(
    primary: Path, tmp_path: Path, setup: Callable[[Path], None], kept: bool
) -> None:
    add_vendor(primary, tmp_path)
    path = linked(primary, "walk")
    setup(path)
    age(path)
    if setup is fresh_file:
        (path / "node_modules/pkg/edited.js").write_text("edited a moment ago\n")
    tidy(primary)
    assert path.is_dir() == kept

"""The tidy keeps work that a repository setting, a paused operation or a path spelling could hide."""

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import stale_updates
import tidy_guards
from conftest import age_branch, commit, git, git_path
from test_tidy import (
    age,
    age_folders,
    branches,
    fake_gh,
    linked,
    make_target,
    merged_branch,
    quick_git_limits,
    squash_merged_steps,
    stand_in_git,
    tidy,
    unmerged,
)


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
    conflicting_branch(primary)


def conflicting_branch(primary: Path) -> None:
    """An aged branch `edge` whose line the base changed another way."""
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


def test_tidy_keeps_a_build_folder_when_a_process_path_differs_only_in_letter_case(
    primary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy = linked(primary, "busy")
    unmerged(busy)
    target = make_target(busy)
    monkeypatch.setattr(
        stale_updates, "open_paths", lambda: {str(busy.resolve()).swapcase() + "/x"}
    )
    tidy(linked(primary, "session"))
    assert target.is_dir()


def test_tidy_writes_what_it_removes_to_a_file_in_the_common_git_folder(
    primary: Path,
) -> None:
    head = merged_branch(primary, "done")
    log = (
        Path(git(primary, "rev-parse", "--absolute-git-dir"))
        / "hard-eng-tidy-removed.log"
    )
    log.write_text(f"{int(time.time()) - 40 * 86400} branch old {head}\n")
    tidy(linked(primary, "session"))
    rows = [row.partition(" ")[2] for row in log.read_text().splitlines()]
    assert rows == [f"branch done {head}"]


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


@pytest.mark.parametrize("through", ["global-config", "environment"])
def test_the_scratch_repository_takes_no_template_from_the_users_settings(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, through: str
) -> None:
    template = tmp_path / "template"
    (template / "info").mkdir(parents=True)
    (template / "info/attributes").write_text("tracked.txt merge=ours\n")
    (template / "config").write_text('[merge "ours"]\n\tdriver = true\n')
    if through == "global-config":
        settings = tmp_path / "settings"
        settings.write_text(f"[init]\n\ttemplateDir = {template}\n")
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(settings))
    else:
        monkeypatch.setenv("GIT_TEMPLATE_DIR", str(template))
    conflicting_branch(primary)
    tidy(linked(primary, "session"))
    assert "edge" in branches(primary)


def test_a_commit_that_an_expiring_rescue_ref_holds_gets_a_fresh_ref_on_a_new_removal(
    primary: Path,
) -> None:
    git(primary, "switch", "-qc", "zero")
    (primary / "z.txt").write_text("z\n")
    commit(primary, "add")
    git(primary, "rm", "-q", "z.txt")
    tip = commit(primary, "revert")
    git(primary, "update-ref", "refs/hard-eng/tidy/20200101T000000Z/old", tip)
    git(primary, "switch", "-qc", "parking", "main")
    age_branch(primary, "zero")
    tidy(linked(primary, "session"))
    assert "zero" not in branches(primary)
    gc_now(primary)
    assert resolves(primary, tip)


def test_tidy_leaves_a_symbolic_branch_and_its_target_alone(primary: Path) -> None:
    (primary / "log-only.txt").write_text("x\n")
    only_logged = commit(primary, "held by the log of main only")
    git(primary, "reset", "-q", "--hard", "HEAD~1")
    git(primary, "symbolic-ref", "refs/heads/trunk", "refs/heads/main")
    merged_branch(primary, "feat")
    git(primary, "symbolic-ref", "refs/heads/alias", "refs/heads/feat")
    for name in ("trunk", "main"):
        age_branch(primary, name)
    tidy(linked(primary, "session"))
    assert {"main", "trunk", "feat", "alias"} <= branches(primary)
    assert resolves(primary, only_logged)
    assert git(primary, "symbolic-ref", "refs/heads/trunk") == "refs/heads/main"


@pytest.mark.parametrize("bare", [False, True], ids=["with-git-folder", "bare"])
@pytest.mark.parametrize("place", ["main-checkout", "linked-worktree"])
def test_tidy_keeps_a_build_folder_that_holds_a_nested_repository(
    primary: Path, place: str, bare: bool
) -> None:
    path = primary if place == "main-checkout" else linked(primary, "work")
    target = make_target(path)
    inner = target / "vendor/pkg"
    inner.mkdir(parents=True)
    git(inner, "init", "-q", *(["--bare"] if bare else []))
    age(path)
    age_folders(target)
    tidy(linked(primary, "session"))
    assert (inner / ("HEAD" if bare else ".git")).exists()


def test_a_squash_merged_branch_of_forty_commits_leaves_one_rescue_ref(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    tip = squash_merged_steps(primary, "long", 40)
    assert "long" not in branches(primary)
    refs = git(primary, "for-each-ref", "--format=%(objectname)", "refs/hard-eng")
    assert refs.split() == [tip]


def test_the_tidy_fetch_prunes_no_remote_tracking_branch_even_with_fetch_prune_set(
    primary: Path, tmp_path: Path
) -> None:
    git(primary, "branch", "gone-upstream", "main")
    git(primary, "push", "-q", "origin", "gone-upstream")
    git(primary, "fetch", "-q", "origin")
    git(tmp_path / "origin.git", "branch", "-D", "gone-upstream")
    git(primary, "config", "fetch.prune", "true")
    git(primary, "config", "remote.origin.prune", "true")
    tidy(linked(primary, "session"))
    git(primary, "rev-parse", "--verify", "refs/remotes/origin/gone-upstream")


def test_tidy_keeps_every_branch_and_says_why_when_info_grafts_exists(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    merged_branch(primary, "done")
    grafts = primary / ".git/info/grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text("")
    tidy(linked(primary, "session"))
    assert "done" in branches(primary)
    assert "info/grafts" in capsys.readouterr().err


def test_tidy_keeps_every_branch_when_the_reflogs_are_not_plain_files(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    merged_branch(primary, "done")
    stand_in_git(
        tmp_path,
        monkeypatch,
        '[ "$1 $2 $3" = "config --get extensions.refstorage" ]',
        "echo reftable; exit 0",
    )
    tidy(linked(primary, "session"))
    assert "done" in branches(primary)
    assert "reftable" in capsys.readouterr().err


def test_tidy_removes_a_merged_branch_whose_log_message_holds_a_form_feed(
    primary: Path,
) -> None:
    git(primary, "switch", "-qc", "odd")
    (primary / "o.txt").write_text("o\n")
    commit(primary, "first\x0csecond word")
    git(primary, "switch", "-q", "main")
    git(primary, "merge", "-q", "--ff-only", "odd")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-qc", "parking")
    age_branch(primary, "odd")
    tidy(linked(primary, "session"))
    assert "odd" not in branches(primary)


def test_tidy_keeps_a_branch_that_a_rebase_with_update_refs_will_move(
    primary: Path,
) -> None:
    git(primary, "branch", "side", "main")
    git(primary, "switch", "-qc", "stack-base")
    (primary / "b.txt").write_text("b\n")
    commit(primary, "b")
    git(primary, "switch", "-qc", "stack-top")
    (primary / "t.txt").write_text("t\n")
    commit(primary, "t")
    git(primary, "switch", "-q", "main")
    git(primary, "cherry-pick", "stack-base")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-q", "stack-top")
    editor = primary.parent / "break-editor"
    editor.write_text(
        '#!/bin/sh\n{ echo break; cat "$1"; } > "$1.new"; mv "$1.new" "$1"\n'
    )
    editor.chmod(0o755)
    git(
        primary,
        "-c",
        f"sequence.editor={editor}",
        "rebase",
        "-i",
        "--update-refs",
        "side",
    )
    assert "stack-base" in git_path(primary, "rebase-merge/update-refs").read_text()
    age_branch(primary, "stack-base")
    tidy(linked(primary, "session"))
    assert "stack-base" in branches(primary)


def test_a_removed_branch_takes_its_config_section_with_it(primary: Path) -> None:
    merged_branch(primary, "done")
    git(primary, "config", "branch.done.description", "old notes")
    git(primary, "config", "branch.done.remote", "origin")
    tidy(linked(primary, "session"))
    assert "done" not in branches(primary)
    git(primary, "branch", "done", "main")
    shown = subprocess.run(
        ["git", "config", "--get-regexp", r"^branch\.done\."],
        cwd=primary,
        capture_output=True,
        text=True,
        check=False,
    )
    assert shown.stdout == ""


@pytest.mark.parametrize("hangs", [False, True], ids=["fails", "hangs"])
def test_a_failed_config_cleanup_is_reported_with_a_quoted_command_to_retry(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    hangs: bool,
) -> None:
    merged_branch(primary, "feat/$USER")
    if hangs:
        quick_git_limits(monkeypatch)
    stand_in_git(
        tmp_path,
        monkeypatch,
        '[ "$1 $2" = "config --remove-section" ]',
        "sleep 30" if hangs else "exit 1",
    )
    tidy(linked(primary, "session"))
    said = capsys.readouterr().err
    assert "feat/$USER" not in branches(primary)
    assert "git config --remove-section 'branch.feat/$USER'" in said
    assert "removed branch feat/$USER" in said
    assert "kept branch" not in said


def test_a_branch_whose_name_ends_the_section_name_of_a_kept_branch_keeps_that_section(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    merged_branch(primary, "a")
    git(primary, "branch", "a]b", "main")
    git(primary, "switch", "-q", "a]b")
    (primary / "k.txt").write_text("k\n")
    commit(primary, "own work")
    git(primary, "switch", "-qc", "parking", "main")
    git(primary, "config", "branch.a]b.description", "notes that exist nowhere else")
    tidy(linked(primary, "session"))
    said = capsys.readouterr().err
    assert "a" not in branches(primary)
    assert "a]b" in branches(primary)
    assert git(primary, "config", "branch.a]b.description").startswith("notes")
    assert "git config --remove-section branch.a" in said


def test_a_section_that_the_cleanup_could_not_remove_is_reported(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    merged_branch(primary, "a]b")
    git(primary, "config", "branch.a]b.description", "old notes")
    tidy(linked(primary, "session"))
    assert "a]b" not in branches(primary)
    shown = subprocess.run(
        ["git", "config", "--get", "branch.a]b.description"],
        cwd=primary,
        capture_output=True,
        text=True,
        check=False,
    )
    assert shown.stdout == "" or "settings stay" in capsys.readouterr().err


@pytest.mark.parametrize("how", ["symlink", "mount-point"])
def test_tidy_keeps_a_build_folder_that_is_a_link_or_a_mount_point(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    how: str,
) -> None:
    path = linked(primary, "work")
    unmerged(path)
    if how == "symlink":
        real = make_target(tmp_path)
        (path / "target").symlink_to(real, target_is_directory=True)
    else:
        real = make_target(path)
        monkeypatch.setattr(
            os.path, "ismount", lambda place: Path(place).name == "target"
        )
    tidy(linked(primary, "session"))
    assert real.is_dir() and (path / "target").exists()
    assert "link or a mount point" in capsys.readouterr().err

"""The tidy keeps work that a repository setting, a paused operation or a path spelling could hide."""

import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import stale_updates
import tidy_guards
from conftest import age_branch, commit, git, git_path
from test_tidy import (
    branches,
    linked,
    make_target,
    merged_branch,
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

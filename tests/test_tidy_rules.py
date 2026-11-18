"""The tidy keeps work that a repository setting, a paused operation or a path spelling could hide."""

from collections.abc import Callable
from pathlib import Path

import pytest
import stale_updates
import tidy_guards
from conftest import age_branch, commit, git, git_path
from test_tidy import add_vendor, age, branches, linked, tidy


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

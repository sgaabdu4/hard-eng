"""The tidy keeps work that a repository setting, a paused operation or a path spelling could hide."""

from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import age_branch, commit, git, git_path
from test_tidy import branches, linked, tidy


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

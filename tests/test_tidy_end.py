"""After a tidy and a garbage collection, nothing is lost that a person could want back; the test knows no guard."""

import os
import re
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
import stale_updates
from conftest import age_branch, commit, git
from test_tidy import add_vendor, age, age_folders, fake_gh, linked, tidy, unmerged
from test_tidy_rules import (
    diverge,
    dropped_in_submodule_folder,
    fresh_file,
    keep_stash_commit_in_a_worktree_ref,
    leave_submodule_commit_in_log,
    nested_repository,
    old_install,
    pause_bisect,
    pause_rebase,
)

COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
INSTALL = {
    ".venv",
    "node_modules",
    ".dart_tool",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".hard-eng",
}
CARGO = "Signature: 8a477f597d28d172789f06886806bc55"
Fixture = Callable[[Path, Path, pytest.MonkeyPatch], Callable[[], None] | None]


def git_folders(primary: Path) -> list[Path]:
    common = primary / ".git"
    found = [common, *sorted((common / "worktrees").glob("*"))]
    for folder in list(found):
        for here, names, files in os.walk(folder / "modules"):
            if "HEAD" in files:
                found.append(Path(here))
                names[:] = [name for name in names if name == "modules"]
    return found


def named_commits(primary: Path) -> dict[str, Path]:
    """Every commit that any ref or log of any Git folder names, read as plain files."""
    found: dict[str, Path] = {}
    for folder in git_folders(primary):
        for here, _, files in os.walk(folder):
            for name in files:
                place = Path(here) / name
                relative = place.relative_to(folder).parts
                if relative[0] in {"modules", "worktrees", "objects", "hooks"}:
                    continue
                if relative[:3] == ("refs", "hard-eng", "tidy"):
                    continue
                if relative[0] in {"refs", "logs", "packed-refs", "HEAD", "ORIG_HEAD"}:
                    for sha in COMMIT.findall(place.read_text(errors="ignore")):
                        if sha != "0" * 40:
                            found.setdefault(sha, folder)
    return found


def lost_candidates(primary: Path) -> list[tuple[Path, float, Path, bool]]:
    """Every file of a linked worktree that Git does not track, with its change time and its worktree."""
    listing = git(primary, "worktree", "list", "--porcelain")
    folders = [
        Path(line.removeprefix("worktree "))
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ][1:]
    found: list[tuple[Path, float, Path, bool]] = []
    for folder in folders:
        tracked = set(
            subprocess.check_output(
                ["git", "ls-files", "-z", "--recurse-submodules"], cwd=folder, text=True
            ).split("\0")
        )
        tag = folder / "target/CACHEDIR.TAG"
        cargo = tag.is_file() and tag.read_text().startswith(CARGO)
        for here, names, files in os.walk(folder):
            for name in files:
                place = Path(here) / name
                if str(place.relative_to(folder)) not in tracked:
                    found.append((place, os.lstat(place).st_mtime, folder, cargo))
    return found


def may_vanish(place: Path, mtime: float, folder: Path, cargo: bool) -> bool:
    parts = place.relative_to(folder).parts
    if parts == (".git",):
        return True
    if parts[0] == "target":
        return cargo
    return (
        bool(INSTALL & set(parts))
        and ".git" not in parts
        and time.time() - mtime > 24 * 3600
    )


def merged_commit_in_a_removed_item(
    primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch
) -> None:
    linked(primary, "done")


def with_vendor(
    primary: Path, setup: Callable[[Path, Path, list[str]], None], tmp_path: Path
) -> None:
    allow = add_vendor(primary, tmp_path)
    setup(primary, linked(primary, "work"), allow)


def installs(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    old_install(linked(primary, "work"))


def nested(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    nested_repository(linked(primary, "work"))


def fresh(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> Callable[[], None]:
    path = linked(primary, "work")
    return lambda: fresh_file(path)


def dropped(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    add_vendor(primary, tmp_path)
    dropped_in_submodule_folder(linked(primary, "work"))


def submodule_log(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    with_vendor(primary, leave_submodule_commit_in_log, tmp_path)


def stash_ref(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    with_vendor(primary, keep_stash_commit_in_a_worktree_ref, tmp_path)


def net_zero(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    git(primary, "switch", "-qc", "zero")
    (primary / "z.txt").write_text("z\n")
    commit(primary, "add")
    git(primary, "rm", "-q", "z.txt")
    commit(primary, "revert")
    git(primary, "switch", "-qc", "parking", "main")


def reset_away(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    path = linked(primary, "work")
    unmerged(path)
    git(path, "reset", "-q", "--hard", "main")


def own_work(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    unmerged(linked(primary, "work"))


def untracked_note(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    (linked(primary, "work") / "notes.txt").write_text("notes\n")


def paused_rebase(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    pause_rebase(primary)


def paused_bisect(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    pause_bisect(primary)


def merge_attributes(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    diverge(primary, "info")


def gap_while_waiting(
    primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch
) -> Callable[[], None]:
    waiting = linked(primary, "waiting")
    git(waiting, "push", "-q", "origin", "waiting")
    real = stale_updates.tidy_gh

    def slow(cwd: Path, *arguments: str) -> list[object] | None:
        (waiting / "late.txt").write_text("late\n")
        return real(cwd, *arguments)

    fake_gh(tmp_path, mp, {"open": {}})
    return lambda: mp.setattr(stale_updates, "tidy_gh", slow)


def target_output(primary: Path, tmp_path: Path, mp: pytest.MonkeyPatch) -> None:
    path = linked(primary, "work")
    (path / "target/debug").mkdir(parents=True)
    (path / "target/CACHEDIR.TAG").write_text(f"{CARGO}\n")
    (path / "target/debug/app").write_text("bin\n")
    age_folders(path / "target")


FIXTURES: dict[str, Fixture] = {
    "merged": merged_commit_in_a_removed_item,
    "installs": installs,
    "nested-repository": nested,
    "fresh-install-file": fresh,
    "dropped-in-submodule-folder": dropped,
    "submodule-commit-in-log": submodule_log,
    "stash-in-worktree-ref": stash_ref,
    "net-zero-branch": net_zero,
    "reset-away": reset_away,
    "own-work": own_work,
    "untracked-note": untracked_note,
    "paused-rebase": paused_rebase,
    "paused-bisect": paused_bisect,
    "merge-attributes": merge_attributes,
    "gap-while-waiting": gap_while_waiting,
    "cargo-target": target_output,
}


def age_everything(primary: Path) -> None:
    listing = git(primary, "worktree", "list", "--porcelain")
    for line in listing.splitlines():
        if line.startswith("worktree "):
            age(Path(line.removeprefix("worktree ")))
    for name in git(
        primary, "for-each-ref", "--format=%(refname:short)", "refs/heads"
    ).split():
        age_branch(primary, name)


@pytest.mark.parametrize("name", FIXTURES)
def test_a_tidy_and_a_garbage_collection_lose_no_commit_and_only_regenerable_files(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    session = linked(primary, "session")
    later = FIXTURES[name](primary, tmp_path, monkeypatch)
    age_everything(primary)
    if later is not None:
        later()
    git(primary, "reflog", "expire", "--expire=now", "HEAD")
    commits = named_commits(primary)
    files = lost_candidates(primary)
    tidy(session)
    still = named_commits(primary)
    git(primary, "gc", "-q", "--prune=now")
    library = tmp_path / "library"
    for sha, folder in commits.items():
        if sha in still:
            continue
        homes = [primary]
        if folder.name != ".git" and "modules" in folder.parts:
            homes = [folder, library] if folder.is_dir() else [library]
        assert any(
            subprocess.run(
                ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
                cwd=home,
                capture_output=True,
                check=False,
            ).returncode
            == 0
            for home in homes
            if home.is_dir()
        ), f"commit {sha} named in {folder} is gone"
    for place, mtime, folder, cargo in files:
        if not os.path.lexists(place):
            assert may_vanish(place, mtime, folder, cargo), f"{place} was lost"

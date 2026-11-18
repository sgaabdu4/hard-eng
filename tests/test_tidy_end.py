"""After a tidy and a garbage collection, nothing is lost that a person could want back; the test knows no guard."""

import os
import re
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from conftest import age_branch, commit, git
from test_tidy import age, age_folders, linked, merged_branch, tidy, unmerged
from test_tidy_rules import (
    diverge,
    pause_bisect,
    pause_rebase,
)

COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
REMOVED = "hard-eng-tidy-removed.log"
CARGO = "Signature: 8a477f597d28d172789f06886806bc55"
Finish = Callable[[Path], None]
Fixture = Callable[[Path], Finish | None]


def git_folders(primary: Path) -> list[Path]:
    common = primary / ".git"
    return [common, *sorted((common / "worktrees").glob("*"))]


def named_commits(primary: Path) -> set[str]:
    """Every commit that any ref or log of any Git folder names, read as plain files."""
    found: set[str] = set()
    for folder in git_folders(primary):
        for here, _, files in os.walk(folder):
            for name in files:
                place = Path(here) / name
                relative = place.relative_to(folder).parts
                if relative[0] in {"worktrees", "objects", "hooks"}:
                    continue
                if relative[:3] == ("refs", "hard-eng", "tidy"):
                    continue
                if relative[0] in {"refs", "logs", "packed-refs", "HEAD", "ORIG_HEAD"}:
                    found |= set(COMMIT.findall(place.read_text(errors="ignore")))
    return found - {"0" * 40}


def checkouts(primary: Path) -> list[Path]:
    listing = git(primary, "worktree", "list", "--porcelain")
    return [
        Path(line.removeprefix("worktree "))
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]


def untracked_files(primary: Path) -> list[tuple[Path, Path, bool]]:
    """Every file that Git does not track in the main checkout and each linked one, with its checkout and whether a cargo marker was there."""
    found: list[tuple[Path, Path, bool]] = []
    for folder in checkouts(primary):
        tracked = set(
            subprocess.check_output(
                ["git", "ls-files", "-z"], cwd=folder, text=True
            ).split("\0")
        )
        tag = folder / "target/CACHEDIR.TAG"
        cargo = tag.is_file() and tag.read_text().startswith(CARGO)
        for here, names, files in os.walk(folder):
            if Path(here) == folder:
                names[:] = [name for name in names if name != ".git"]
            for name in files:
                place = Path(here) / name
                if str(place.relative_to(folder)) not in tracked:
                    found.append((place, folder, cargo))
    return found


def may_vanish(place: Path, folder: Path, cargo: bool) -> bool:
    parts = place.relative_to(folder).parts
    return parts[0] == "target" and cargo and ".git" not in parts


def resolves(home: Path, sha: str) -> bool:
    return (
        subprocess.run(
            ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
            cwd=home,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def ref_names(primary: Path) -> set[str]:
    return set(git(primary, "for-each-ref", "--format=%(refname)").split())


def merged_commit_in_a_removed_item(primary: Path) -> None:
    merged_branch(primary, "done")


def net_zero(primary: Path) -> None:
    git(primary, "switch", "-qc", "zero")
    (primary / "z.txt").write_text("z\n")
    commit(primary, "add")
    git(primary, "rm", "-q", "z.txt")
    commit(primary, "revert")
    git(primary, "switch", "-qc", "parking", "main")


def reset_away(primary: Path) -> None:
    path = linked(primary, "work")
    unmerged(path)
    git(path, "reset", "-q", "--hard", "main")
    git(primary, "worktree", "remove", "--force", str(path))


def paused_rebase(primary: Path) -> None:
    pause_rebase(primary)


def paused_bisect(primary: Path) -> None:
    pause_bisect(primary)


def merge_attributes(primary: Path) -> None:
    diverge(primary, "info")


def symbolic_branch(primary: Path) -> None:
    (primary / "log-only.txt").write_text("x\n")
    commit(primary, "held by the log of main only")
    git(primary, "reset", "-q", "--hard", "HEAD~1")
    git(primary, "symbolic-ref", "refs/heads/trunk", "refs/heads/main")


def nested_in_target(path: Path) -> None:
    (path / "target/vendor/pkg").mkdir(parents=True)
    (path / "target/CACHEDIR.TAG").write_text(f"{CARGO}\n")
    git(path / "target/vendor/pkg", "init", "-q")
    age_folders(path / "target")


def nested_in_main_target(primary: Path) -> None:
    nested_in_target(primary)


def nested_in_linked_target(primary: Path) -> None:
    nested_in_target(linked(primary, "work"))


def dated(root: Path, days: int, *arguments: str) -> None:
    stamp = f"{int(time.time()) - days * 86400} +0000"
    env = {**os.environ, "GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp}
    subprocess.run(
        ["git", *arguments], cwd=root, env=env, check=True, capture_output=True
    )


def reset_then_real_gc(primary: Path) -> None:
    path = linked(primary, "work")
    (path / "w.txt").write_text("work kept nowhere else\n")
    dated(path, 40, "add", "w.txt")
    dated(path, 40, "commit", "-qm", "work W")
    dated(path, 20, "reset", "-q", "--hard", "main")
    git(primary, "worktree", "remove", "--force", str(path))
    git(primary, "gc", "-q")


def rewound(primary: Path) -> None:
    git(primary, "switch", "-qc", "rewound")
    (primary / "w.txt").write_text("work kept nowhere else\n")
    commit(primary, "work W")
    git(primary, "switch", "-qc", "parking", "main")
    git(primary, "reflog", "expire", "--expire=now", "refs/heads/rewound")
    git(primary, "branch", "-f", "rewound", "main")


def log_message_option(separator: str, option: str) -> Fixture:
    def build(primary: Path) -> None:
        git(primary, "switch", "-qc", "rewound")
        (primary / "w.txt").write_text("work kept nowhere else\n")
        commit(primary, f"ship it{separator}{option}")
        git(primary, "switch", "-qc", "parking", "main")
        git(primary, "branch", "-f", "rewound", "main")

    return build


def base_outside_refspec(primary: Path) -> None:
    git(
        primary,
        "config",
        "remote.origin.fetch",
        "+refs/heads/session:refs/remotes/origin/session",
    )
    git(primary, "update-ref", "-d", "refs/remotes/origin/main")
    git(primary, "switch", "-qc", "shipped")
    (primary / "s.txt").write_text("shipped work\n")
    commit(primary, "shipped work")
    git(primary, "push", "-q", "origin", "shipped:main")
    git(primary, "switch", "-q", "main")


def orphan_legacy(primary: Path) -> str:
    git(primary, "switch", "-q", "--orphan", "legacy")
    (primary / "old.txt").write_text("legacy\n")
    legacy = commit(primary, "legacy history")
    git(primary, "switch", "-qc", "parking", "main")
    return legacy


def main_root(primary: Path) -> str:
    return git(primary, "rev-list", "--max-parents=0", "main")


def graft_by_replace(primary: Path) -> Finish:
    legacy = orphan_legacy(primary)
    root = main_root(primary)
    git(primary, "replace", "--graft", root, legacy)

    def drop(repo: Path) -> None:
        git(repo, "replace", "-d", root)

    return drop


def graft_by_file(primary: Path) -> Finish:
    legacy = orphan_legacy(primary)
    grafts = primary / ".git/info/grafts"
    grafts.parent.mkdir(exist_ok=True)
    grafts.write_text(f"{main_root(primary)} {legacy}\n")
    return lambda repo: (repo / ".git/info/grafts").unlink()


def target_output(primary: Path) -> None:
    path = linked(primary, "work")
    (path / "target/debug").mkdir(parents=True)
    (path / "target/CACHEDIR.TAG").write_text(f"{CARGO}\n")
    (path / "target/debug/app").write_text("bin\n")
    age_folders(path / "target")


FIXTURES: dict[str, Fixture] = {
    "merged": merged_commit_in_a_removed_item,
    "net-zero-branch": net_zero,
    "reset-away": reset_away,
    "paused-rebase": paused_rebase,
    "paused-bisect": paused_bisect,
    "merge-attributes": merge_attributes,
    "symbolic-branch": symbolic_branch,
    "reset-then-real-gc": reset_then_real_gc,
    "rewound": rewound,
    "base-outside-refspec": base_outside_refspec,
    "log-form-feed-quiet": log_message_option("\x0c", "--quiet"),
    "log-line-separator-count": log_message_option("\u2028", "--count"),
    "graft-by-replace": graft_by_replace,
    "graft-by-file": graft_by_file,
    "cargo-target": target_output,
    "nested-repository-in-main-target": nested_in_main_target,
    "nested-repository-in-linked-target": nested_in_linked_target,
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
def test_a_tidy_loses_nothing_that_a_plain_garbage_collection_keeps(
    primary: Path, tmp_path: Path, name: str
) -> None:
    session = linked(primary, "session")
    finish = FIXTURES[name](primary)
    age_everything(primary)
    git(primary, "reflog", "expire", "--expire=now", "HEAD")
    control = tmp_path / "control"
    shutil.copytree(primary, control, symlinks=True)
    if finish is not None:
        finish(control)
    git(control, "gc", "-q", "--prune=now")
    commits = named_commits(primary)
    files = untracked_files(primary)
    refs = ref_names(primary)
    tidy(session)
    kept_refs = ref_names(primary)
    if finish is not None:
        finish(primary)
    git(primary, "gc", "-q", "--prune=now")
    for sha in commits:
        assert resolves(primary, sha) or not resolves(control, sha), f"{sha} is lost"
    for place, folder, cargo in files:
        if not os.path.lexists(place):
            assert may_vanish(place, folder, cargo), f"{place} was lost"
    record = Path(git(primary, "rev-parse", "--absolute-git-dir")) / REMOVED
    removed = {
        f"refs/heads/{row.split(' ')[2]}"
        for row in (record.read_text().splitlines() if record.exists() else [])
    }
    assert refs - kept_refs <= removed
    for checkout in checkouts(primary):
        assert resolves(checkout, "HEAD"), f"HEAD of {checkout} does not resolve"

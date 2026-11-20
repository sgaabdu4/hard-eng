"""`release_canary.py`: the update target starts from the release that users have."""

from pathlib import Path

import pytest
from conftest import commit, git, init

import release_canary


def released_history(tmp_path: Path) -> dict[str, str]:
    """develop `base` → `released`; main is `base` plus a merge of develop, and the candidate follows on develop."""
    checkout = tmp_path / "checkout"
    init(checkout)
    git(checkout, "checkout", "-qb", "develop")
    (checkout / "a.txt").write_text("base\n")
    shas = {"base": commit(checkout, "base")}
    (checkout / "a.txt").write_text("released\n")
    shas["released"] = commit(checkout, "released")
    git(checkout, "checkout", "-qb", "main", shas["base"])
    git(checkout, "merge", "-q", "--no-ff", "-m", "release", "develop")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    shas["merged"] = git(checkout, "rev-parse", "HEAD")
    git(checkout, "checkout", "-q", "develop")
    (checkout / "a.txt").write_text("candidate\n")
    shas["candidate"] = commit(checkout, "candidate")
    git(tmp_path, "clone", "-q", str(checkout), str(tmp_path / "source"))
    return shas


def installed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, candidate: str) -> str:
    installed_from: list[Path] = []

    def install_new(kind: str, value: str, old: Path, work: Path, log: object) -> None:
        installed_from.append(old)

    monkeypatch.setattr(release_canary, "install_new", install_new)
    with (tmp_path / "log").open("w") as log:
        release_canary.install_last_release(
            "python",
            candidate,
            tmp_path / "source",
            tmp_path / "work",
            log,
            tmp_path / "checkout",
        )
    return git(installed_from[0], "rev-parse", "HEAD")


def test_the_last_release_is_the_candidates_merge_base_with_main_not_mains_merge_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Users go from main's merge commit to the next one, so the old install is its ancestor."""
    shas = released_history(tmp_path)
    assert installed(tmp_path, monkeypatch, shas["candidate"]) == shas["released"]


def test_a_main_commit_installs_the_main_tip_that_it_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push, manual run or rerun on main checks a main commit; its first parent is the release users had."""
    shas = released_history(tmp_path)
    assert installed(tmp_path, monkeypatch, shas["merged"]) == shas["base"]


def test_a_develop_commit_already_released_fails_with_the_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A develop job rerun after its release has no older release to update from, so it stops instead of guessing one."""
    shas = released_history(tmp_path)
    with pytest.raises(release_canary.Failed, match="reached main inside a release"):
        installed(tmp_path, monkeypatch, shas["released"])

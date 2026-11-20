"""`release_canary.py`: the update target starts from the release that users have."""

from pathlib import Path

import pytest
from conftest import commit, git, init

import release_canary


def test_the_last_release_is_the_candidates_merge_base_with_main_not_mains_merge_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Users go from main's merge commit to the next one, so the old install is its ancestor."""
    checkout = tmp_path / "checkout"
    init(checkout)
    git(checkout, "checkout", "-qb", "develop")
    (checkout / "a.txt").write_text("base\n")
    base = commit(checkout, "base")
    (checkout / "a.txt").write_text("released\n")
    released = commit(checkout, "released")
    git(checkout, "checkout", "-qb", "main", base)
    git(checkout, "merge", "-q", "--no-ff", "-m", "release", "develop")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(checkout, "checkout", "-q", "develop")
    (checkout / "a.txt").write_text("candidate\n")
    candidate = commit(checkout, "candidate")
    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(checkout), str(source))
    git(source, "checkout", "-q", "--detach", candidate)
    installed_from: list[Path] = []

    def install_new(kind: str, value: str, old: Path, work: Path, log: object) -> None:
        installed_from.append(old)

    monkeypatch.setattr(release_canary, "install_new", install_new)
    with (tmp_path / "log").open("w") as log:
        release_canary.install_last_release(
            "python", candidate, source, tmp_path / "work", log, checkout
        )
    assert git(installed_from[0], "rev-parse", "HEAD") == released


def test_a_candidate_on_main_installs_the_main_tip_it_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A push to main checks main's new merge commit, so the release users had is its first parent."""
    checkout = tmp_path / "checkout"
    init(checkout)
    git(checkout, "checkout", "-qb", "develop")
    (checkout / "a.txt").write_text("base\n")
    base = commit(checkout, "base")
    (checkout / "a.txt").write_text("next\n")
    commit(checkout, "next")
    git(checkout, "checkout", "-qb", "main", base)
    git(checkout, "merge", "-q", "--no-ff", "-m", "release", "develop")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    merged = git(checkout, "rev-parse", "HEAD")
    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(checkout), str(source))
    installed_from: list[Path] = []

    def install_new(kind: str, value: str, old: Path, work: Path, log: object) -> None:
        installed_from.append(old)

    monkeypatch.setattr(release_canary, "install_new", install_new)
    with (tmp_path / "log").open("w") as log:
        release_canary.install_last_release(
            "python", merged, source, tmp_path / "work", log, checkout
        )
    assert git(installed_from[0], "rev-parse", "HEAD") == base


def test_a_released_develop_commit_installs_the_main_tip_before_its_release(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rerun of a develop job after the release starts from the main tip that the release replaced."""
    checkout = tmp_path / "checkout"
    init(checkout)
    git(checkout, "checkout", "-qb", "develop")
    (checkout / "a.txt").write_text("base\n")
    base = commit(checkout, "base")
    (checkout / "a.txt").write_text("one\n")
    commit(checkout, "one")
    (checkout / "a.txt").write_text("candidate\n")
    candidate = commit(checkout, "candidate")
    git(checkout, "checkout", "-qb", "main", base)
    git(checkout, "merge", "-q", "--no-ff", "-m", "release", "develop")
    (checkout / "b.txt").write_text("later\n")
    commit(checkout, "later on main")
    git(checkout, "update-ref", "refs/remotes/origin/main", "HEAD")
    source = tmp_path / "source"
    git(tmp_path, "clone", "-q", str(checkout), str(source))
    installed_from: list[Path] = []

    def install_new(kind: str, value: str, old: Path, work: Path, log: object) -> None:
        installed_from.append(old)

    monkeypatch.setattr(release_canary, "install_new", install_new)
    with (tmp_path / "log").open("w") as log:
        release_canary.install_last_release(
            "python", candidate, source, tmp_path / "work", log, checkout
        )
    assert git(installed_from[0], "rev-parse", "HEAD") == base

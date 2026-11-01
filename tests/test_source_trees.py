"""Prove one run fetches the Hard Eng source trees once, however many checks need them."""

from pathlib import Path
from unittest.mock import Mock

import change_size
import pytest
import update
from conftest import git
from test_updates import select_release


@pytest.fixture
def update_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, Mock]:
    source, target, _ = release
    base = git(target, "rev-parse", "HEAD")
    guide = source / "AGENTS.md"
    guide.write_text(guide.read_text() + "\nUpdated managed fixture guidance.\n")
    select_release(source, monkeypatch)
    assert "Updated Hard Eng" in update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    fetch = Mock(side_effect=update.fetch_sources)
    monkeypatch.setattr(update, "fetch_sources", fetch)
    return target, base, fetch


def revisions(target: Path, base: str) -> tuple[str, str]:
    found = update.update_in_diff(target, base)
    assert found is not None
    return found[0], found[1]


def test_every_round_of_one_run_takes_the_trees_from_the_first_fetch(
    update_branch: tuple[Path, str, Mock],
) -> None:
    target, base, fetch = update_branch
    assert update.check_scaffold_update(target, base)
    installed = update.installed_update_paths(target, base)
    assert installed
    assert change_size.update_written(target, base) >= installed
    assert update.installed_update_paths(target, base) == installed
    assert fetch.call_count == 1
    revision, previous = revisions(target, base)
    source, old = update.shared_sources(revision, previous)
    assert git(source, "rev-parse", "HEAD") == revision
    assert git(old, "rev-parse", "HEAD") == previous
    assert git(source, "status", "--porcelain") == ""
    assert git(old, "status", "--porcelain") == ""


def test_a_tree_a_round_changed_is_fetched_again(
    update_branch: tuple[Path, str, Mock],
) -> None:
    target, base, fetch = update_branch
    assert update.check_scaffold_update(target, base)
    revision, previous = revisions(target, base)
    source, _ = update.shared_sources(revision, previous)
    (source / "left-behind.txt").write_text("stray\n")
    assert update.check_scaffold_update(target, base)
    assert fetch.call_count == 2
    renewed, _ = update.shared_sources(revision, previous)
    assert not (renewed / "left-behind.txt").exists()


def test_different_revisions_are_not_merged(
    update_branch: tuple[Path, str, Mock],
) -> None:
    target, base, fetch = update_branch
    revision, previous = revisions(target, base)
    first = update.shared_sources(revision, previous)
    second = update.shared_sources(previous, previous)
    assert fetch.call_count == 2
    assert first[0] != second[0]
    assert git(second[0], "rev-parse", "HEAD") == previous

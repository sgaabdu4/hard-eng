"""Prove one run fetches the Hard Eng source trees once, however many checks need them."""

from pathlib import Path
from unittest.mock import Mock

import change_size
import pytest
import source_trees
import update
from conftest import commit, git
from project_files import keeping
from test_updates import select_release

NOTED = (
    "on: push\njobs:\n  check:\n    runs-on: ubuntu-latest\n    steps:\n      - run: |\n"
    "          MISE_DATA_DIR: ${{ runner.temp }}/hard-eng-tools/mise/data\n"
)


def updated(
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


@pytest.fixture
def update_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str, Mock]:
    return updated(release, monkeypatch)


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
    found = update.update_in_diff(target, base)
    assert found is not None
    assert change_size.update_written(target, base, found[2]) >= installed
    assert update.installed_update_paths(target, base) == installed
    assert fetch.call_count == 1
    revision, previous = revisions(target, base)
    source, old = update.shared_sources(revision, previous)
    assert git(source, "rev-parse", "HEAD") == revision
    assert git(old, "rev-parse", "HEAD") == previous
    assert git(source, "status", "--porcelain") == ""
    assert git(old, "status", "--porcelain") == ""


def test_one_check_plans_each_tree_and_tells_each_note_one_time(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """While a check keeps its listings, each proof reuses the setup plan of the checkout and of the base tree."""
    workflow = release[1] / ".github/workflows/deploy.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(NOTED)
    commit(release[1], "add a workflow")
    target, base, _ = updated(release, monkeypatch)
    plans = Mock(side_effect=update.update_plan)
    monkeypatch.setattr(update, "update_plan", plans)
    found = update.update_in_diff(target, base)
    assert found is not None
    capfd.readouterr()
    with keeping("references", "listings"):
        assert update.check_scaffold_update(target, base)
        installed = update.installed_update_paths(target, base)
        assert change_size.update_written(target, base, found[2]) >= installed
    replaced = [call.kwargs.get("replace", False) for call in plans.call_args_list]
    assert replaced == [False, True]
    assert capfd.readouterr().err.count("CI tool directories") == 1
    assert update.check_scaffold_update(target, base)
    assert len(plans.call_args_list) == 3


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


def test_a_failed_fetch_is_tried_once_per_run() -> None:
    source_trees.forget_all()
    fetch = Mock(side_effect=ValueError("clone refused"))
    for _ in range(3):
        with pytest.raises(ValueError, match="clone refused"):
            source_trees.shared("repository", "a" * 40, "b" * 40, fetch)
    assert fetch.call_count == 1
    source_trees.forget_all()
    with pytest.raises(ValueError, match="clone refused"):
        source_trees.shared("repository", "a" * 40, "b" * 40, fetch)
    assert fetch.call_count == 2

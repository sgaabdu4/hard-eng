"""A project still updates after upstream rewrote the history of its recorded release."""

import json
import subprocess
from pathlib import Path

import pytest
import update
from conftest import commit, git
from release_history import StaleRelease


def _rewrite(source: Path, monkeypatch: pytest.MonkeyPatch, served: bool) -> str:
    """Replace the installed release with a same-tree commit; GitHub keeps serving the old one by ID."""
    git(source, "commit", "--amend", "--quiet", "-m", "rewritten baseline")
    if not served:
        git(source, "reflog", "expire", "--expire=now", "--all")
        git(source, "gc", "--quiet", "--prune=now")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2030-01-01T00:00:00+00:00")
    revision = commit(source, "verified update")

    def latest(_previous: str) -> str:
        return revision

    monkeypatch.setattr(update, "latest_verified", latest)
    return revision


def test_update_fetches_a_release_that_left_upstream_history(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    source, target, old = release
    revision = _rewrite(source, monkeypatch, served=True)
    ancestry = ["git", "merge-base", "--is-ancestor", old, revision]
    assert subprocess.run(ancestry, cwd=source, check=False).returncode == 1
    assert revision in update.update(target)
    marker = json.loads((target / update.SOURCE_FILE).read_text())
    assert marker["revision"] == revision
    assert f"recorded release {old} left upstream history" in capfd.readouterr().err


def test_an_unfetchable_recorded_release_names_the_stale_record(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, old = release
    _rewrite(source, monkeypatch, served=False)
    with pytest.raises(StaleRelease, match=f"{old} in .hooks/hard-eng-source.json"):
        update.update(target)

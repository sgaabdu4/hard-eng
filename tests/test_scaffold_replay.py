"""A verified update is proven from its tree, even when the base held edited scaffold files."""

from pathlib import Path
from unittest.mock import Mock

import pytest
import update
from conftest import commit, git
from test_updates import fixed_revision

SKILL_LOCK = ".agents/skills/marketing-video/bun.lock"
WORKFLOW = ".github/workflows/hard-eng.yml"
GENERATED_RUNNER = (
    "${{ vars.CI_RUNS_ON && fromJSON(vars.CI_RUNS_ON) || 'ubuntu-latest' }}"
)


def edited_base(target: Path) -> tuple[str, str]:
    """A base that carries a project's own copy of a shipped file and an older workflow."""
    workflow = target / WORKFLOW
    original = workflow.read_text()
    assert GENERATED_RUNNER in original
    workflow.write_text(original.replace(GENERATED_RUNNER, "ubuntu-latest"))
    lock = target / SKILL_LOCK
    shipped = lock.read_text()
    lock.write_text(shipped.replace("1.", "2.", 1))
    assert lock.read_text() != shipped
    return commit(target, "project copy of a skill file"), shipped


def test_update_that_restores_edited_skill_files_is_proven(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    base, shipped = edited_base(target)
    (target / SKILL_LOCK).write_text(shipped)
    commit(target, "restore the shipped skill file")
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert git(target, "diff", "--name-only", base, "--", SKILL_LOCK) == SKILL_LOCK
    assert update.check_scaffold_update(target, base)
    assert GENERATED_RUNNER in (target / WORKFLOW).read_text()


def test_update_still_refuses_an_edited_skill_file(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    edited_base(target)
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    with pytest.raises(ValueError, match="already differs"):
        update.update(target)

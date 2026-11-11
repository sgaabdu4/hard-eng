"""A verified update is proven from its tree, even when the base held edited scaffold files."""

import subprocess
from pathlib import Path
from unittest.mock import Mock

import change_size
import pytest
import update
from conftest import commit, git
from coverage_sources import require_listed_sources
from gate_config import parse_config, repository_files
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


COORDINATOR = ".agents/skills/trello-coordinator/"
RUN = COORDINATOR + "references/run.md"
SCRIPT = COORDINATOR + "scripts/trello_board/commands.py"
LOCAL_RULE = "- Project rule: reply in the card's language.\n"
LOCAL_CODE = "\n\ndef project_command() -> str:\n    return 'project'\n"


def release_now(source: Path, monkeypatch: pytest.MonkeyPatch, message: str) -> str:
    git(source, "add", ".")
    git(source, "commit", "-q", "--allow-empty", "-m", message)
    revision = git(source, "rev-parse", "HEAD")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))
    return revision


def edited_coordinator(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path]:
    """A project with the coordinator installed and its own committed lines in it."""
    source, target, _ = release
    (target / "trello.json").write_text('{"board": "https://trello.com/b/abc"}')
    commit(target, "connect the board")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    with (target / RUN).open("a") as rules:
        rules.write(LOCAL_RULE)
    with (target / SCRIPT).open("a") as script:
        script.write(LOCAL_CODE)
    commit(target, "project coordinator edits")
    return source, target


def change_first_line(path: Path, line: str) -> None:
    lines = path.read_text().splitlines(keepends=True)
    path.write_text(line + "".join(lines[1:]))


def test_update_merges_local_coordinator_edits(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    base = git(target, "rev-parse", "HEAD")
    change_first_line(source / RUN, "# One coordinator run, release two\n")
    change_first_line(source / SCRIPT, 'import argparse\nRELEASE = "release two"\n')
    release_now(source, monkeypatch, "release two")
    update.update(target)
    for name, local, new in (
        (RUN, LOCAL_RULE, "release two"),
        (SCRIPT, LOCAL_CODE, "release two"),
    ):
        text = (target / name).read_text()
        assert local in text and new in text
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert update.check_scaffold_update(target, base)


def test_local_coordinator_edits_survive_two_releases(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    for number in ("two", "three"):
        change_first_line(source / RUN, f"# One coordinator run, release {number}\n")
        release_now(source, monkeypatch, f"release {number}")
        update.update(target)
        text = (target / RUN).read_text()
        assert text.startswith(f"# One coordinator run, release {number}\n")
        assert text.endswith(LOCAL_RULE)


def test_untouched_coordinator_file_keeps_local_edits(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    before = git(target, "rev-parse", "HEAD")
    release_now(source, monkeypatch, "release without coordinator changes")
    update.update(target)
    assert (target / RUN).read_text().endswith(LOCAL_RULE)
    assert RUN not in git(target, "diff", "--name-only", before, "HEAD").splitlines()


def test_overlapping_coordinator_edit_is_refused(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    change_first_line(target / RUN, "# Our coordinator run\n")
    commit(target, "project heading")
    head = git(target, "rev-parse", "HEAD")
    change_first_line(source / RUN, "# One coordinator run, release two\n")
    release_now(source, monkeypatch, "release two")
    with pytest.raises(ValueError, match=f"{RUN} has local edits on the same lines"):
        update.update(target)
    assert git(target, "rev-parse", "HEAD") == head
    assert git(target, "status", "--porcelain") == ""


def test_merged_coordinator_script_must_compile(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target = edited_coordinator(release, monkeypatch)
    head = git(target, "rev-parse", "HEAD")
    change_first_line(source / SCRIPT, "def broken(:\n")
    release_now(source, monkeypatch, "release two")
    with pytest.raises(ValueError, match=f"{SCRIPT} does not compile"):
        update.update(target)
    assert git(target, "rev-parse", "HEAD") == head


def update_beside_code_outside_the_sources(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, str]:
    source, target, _ = release
    for name in ("src/index.ts", "scripts/build.mjs"):
        (target / name).parent.mkdir(exist_ok=True)
        (target / name).write_text("export const a = 1;\n")
    commit(target, "code outside the listed sources")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    assert '"sources": ["src"]' in (target / "hard-eng.gates.json").read_text()
    base = git(target, "rev-parse", "HEAD")
    release_now(source, monkeypatch, "release two")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    return target, base


def after_the_gate_check(spy: Mock) -> list[str]:
    """The Git commands started after the last start that is not Git."""
    words = [call.args[0] for call in spy.call_args_list]
    last = max(
        (n for n, command in enumerate(words) if command[0] != "git"), default=-1
    )
    return [command[1] for command in words[last + 1 :]]


def test_scaffold_update_check_refuses_code_outside_the_sources(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, base = update_beside_code_outside_the_sources(release, monkeypatch)
    spy = Mock(side_effect=subprocess.Popen)
    monkeypatch.setattr(subprocess, "Popen", spy)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    assert update.check_scaffold_update(target, base)
    assert after_the_gate_check(spy) == []
    spy.reset_mock()
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    with pytest.raises(ValueError, match="outside its sources: scripts"):
        update.check_scaffold_update(target, base)
    assert after_the_gate_check(spy) == ["ls-files"]


def test_the_step_of_the_update_refusal_works_on_the_update_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target, base = update_beside_code_outside_the_sources(release, monkeypatch)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    gates = target / "hard-eng.gates.json"
    gates.write_text(
        gates.read_text().replace('"sources": ["src"]', '"sources": ["scripts", "src"]')
    )
    commit(target, "list the scripts folder")
    assert not update.check_scaffold_update(target, base)
    packages = parse_config(gates.read_text())["packages"]
    require_listed_sources(
        target, packages, repository_files(target), python_only=False
    )


def test_an_update_adds_the_biome_entry_and_stays_an_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    (target / "biome.json").write_text(
        '{\n  "files": {\n    "includes": ["**"]\n  }\n}\n'
    )
    base = commit(target, "project Biome settings")
    release_now(source, monkeypatch, "release one")
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert '"!.hooks"' in (target / "biome.json").read_text()
    changed = set(git(target, "diff", "--name-only", base).splitlines())
    assert "biome.json" in changed
    assert change_size.update_only(target, base, changed)

"""A Hard Eng update travels on its own branch and PR, never on the checkout's branch."""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest
import update
import update_pr
import update_runner
from conftest import add_origin, commit, git
from test_updates import select_release

PULL = "https://github.com/fixture/project/pull/9"
BRANCH = update_runner.UPDATE_BRANCH


class FakeGh:
    def __init__(self) -> None:
        self.pulls: list[dict[str, object]] = []
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, _root: Path, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("pr", "list"):
            return json.dumps(self.pulls)
        if args[:2] == ("pr", "create"):
            title = args[args.index("--title") + 1]
            self.pulls = [{"url": PULL, "title": title, "statusCheckRollup": []}]
            return f"Creating pull request\n{PULL}\n"
        if args[:2] == ("pr", "edit"):
            self.pulls[0]["title"] = args[args.index("--title") + 1]
        return ""

    def verbs(self) -> list[str]:
        return [" ".join(call[:2]) for call in self.calls]


@pytest.fixture
def gh(monkeypatch: pytest.MonkeyPatch) -> FakeGh:
    fake = FakeGh()
    monkeypatch.setattr(update_pr, "gh", fake)
    return fake


@pytest.fixture
def feature(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    source, target, _ = release
    remote = add_origin(target)
    git(target, "switch", "-qc", "feature/work")
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    return source, target, remote


def publish(target: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    with monkeypatch.context() as scope:
        scope.setenv("GIT_CONFIG_COUNT", "2")
        scope.setenv("GIT_CONFIG_KEY_1", "core.hooksPath")
        scope.setenv("GIT_CONFIG_VALUE_1", "/dev/null")
        return update_pr.publish(target)


def newer_release(source: Path, monkeypatch: pytest.MonkeyPatch, note: str) -> str:
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + f"\n{note}\n")
    select_release(source, monkeypatch)
    return git(source, "rev-parse", "HEAD")


def test_background_update_leaves_the_checkout_and_moves_one_branch(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    (target / "staged.txt").write_text("staged work\n")
    git(target, "add", "staged.txt")
    (target / "project.txt").write_text("working edit\n")
    head, marker = git(target, "rev-parse", "HEAD"), (target / update.SOURCE_FILE)
    first = newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "rev-parse", "HEAD") == head
    assert git(target, "branch", "--show-current") == "feature/work"
    assert git(target, "diff", "--cached", "--name-only") == "staged.txt"
    assert (target / "project.txt").read_text() == "working edit\n"
    assert first not in marker.read_text()
    assert git(target, "worktree", "list", "--porcelain").count("worktree ") == 1
    assert git(target, "rev-list", "--count", f"origin/main..{BRANCH}") == "1"
    assert first in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")
    result = (target / update_runner.RESULT_FILE).read_text()
    assert f"ready on branch {BRANCH}" in result
    assert "python3 .hooks/hard-eng.py update-pr" in result
    assert "ready on branch" in update_runner.freshness_note(target)
    second = newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "branch", "--list", "hard-eng/*").split() == [BRANCH]
    assert git(target, "rev-list", "--count", f"origin/main..{BRANCH}") == "1"
    assert second in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")


def test_background_update_keeps_an_update_branch_being_fixed(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    fixing = target.parent / "fixing"
    git(target, "worktree", "add", "-q", str(fixing), BRANCH)
    (fixing / "fix.txt").write_text("fix\n")
    fixed = commit(fixing, "fix the update")
    newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "rev-parse", BRANCH) == fixed
    assert "unfinished work" in (target / update_runner.RESULT_FILE).read_text()


def test_update_pr_pushes_opens_one_pr_and_turns_on_auto_merge(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, remote = feature
    first = newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)
    create = next(call for call in gh.calls if call[:2] == ("pr", "create"))
    assert create[create.index("--title") + 1] == f"Update Hard Eng to {first[:12]}"
    assert create[create.index("--base") + 1] == "main"
    assert ("pr", "merge", PULL, "--auto", "--rebase") in gh.calls
    assert f"{PULL}: checks pending" in capsys.readouterr().out
    second = newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)
    assert gh.verbs().count("pr create") == 1
    assert gh.pulls[0]["title"] == f"Update Hard Eng to {second[:12]}"


def test_update_pr_reports_a_failing_pr_with_its_fix_steps(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    capsys.readouterr()
    failure = {"status": "COMPLETED", "conclusion": "FAILURE"}
    gh.pulls[0]["statusCheckRollup"] = [failure]
    assert publish(target, monkeypatch) == 1
    shown = capsys.readouterr().out
    assert "checks failing" in shown
    assert (
        f"git worktree add {target.parent / (target.name + '-hard-eng-update')} {BRANCH}"
        in shown
    )
    assert gh.verbs().count("pr create") == 1


def test_update_pr_says_when_hard_eng_is_already_on_the_base(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    git(target, "push", "-q", "--no-verify", "origin", f"{BRANCH}:main")
    assert publish(target, monkeypatch) == 0
    assert "Nothing to publish" in capsys.readouterr().out
    assert gh.calls == []
    assert (
        subprocess.run(["git", "diff", "--quiet"], cwd=target, check=False).returncode
        == 0
    )


def test_manual_setup_rerun_prepares_the_branch_instead_of_committing(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    head = git(target, "rev-parse", "HEAD")
    (target / "project.txt").write_text("working edit\n")
    revision = newer_release(source, monkeypatch, "manual update")
    message = update_runner.locked_update(target, repair=True)
    assert "python3 .hooks/hard-eng.py update-pr" in message
    assert git(target, "rev-parse", "HEAD") == head
    assert (target / "project.txt").read_text() == "working edit\n"
    assert revision in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")
    assert git(target, "rev-list", "--count", f"origin/main..{BRANCH}") == "1"


def test_update_waits_quietly_until_origin_has_the_base_branch(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    newer_release(source, monkeypatch, "early update")
    for remote in (None, "empty"):
        if remote:
            empty = target.parent / "empty.git"
            git(target.parent, "init", "-q", "--bare", str(empty))
            git(target, "remote", "add", "origin", str(empty))
        assert update_runner.apply_update(target) == 0
        result = (target / update_runner.RESULT_FILE).read_text()
        assert update_runner.NOT_PUBLISHED in result
        assert "failed" not in result
        assert update_runner.freshness_note(target) == update_runner.NOT_PUBLISHED
    git(target, "remote", "set-url", "origin", str(target.parent / "missing.git"))
    assert update_runner.apply_update(target) == 0
    assert "Hard Eng update failed" in (target / update_runner.RESULT_FILE).read_text()

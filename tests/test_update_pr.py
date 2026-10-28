"""A Hard Eng update travels on its own branch and PR, never on the checkout's branch."""

import json
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path
from unittest.mock import Mock

import change_size
import pytest
import update
import update_pr
import update_runner
from conftest import add_origin, commit, default_policy, git
from test_husky_setup import husky_project
from test_updates import select_release

PULL = "https://github.com/fixture/project/pull/9"
BRANCH = update_runner.UPDATE_BRANCH


class FakeGh:
    def __init__(self) -> None:
        self.pulls: list[dict[str, object]] = []
        self.calls: list[tuple[str, ...]] = []
        self.merging = {
            "rebaseMergeAllowed": True,
            "squashMergeAllowed": True,
            "mergeCommitAllowed": True,
        }

    def __call__(self, root: Path, *args: str) -> str:
        self.calls.append(args)
        if args[:2] == ("pr", "list"):
            for pull in self.pulls:
                pull["headRefOid"] = git(root, "rev-parse", f"refs/heads/{BRANCH}")
            return json.dumps(self.pulls)
        if args[:2] == ("repo", "view"):
            return json.dumps(self.merging)
        if args[:2] == ("pr", "create"):
            title = args[args.index("--title") + 1]
            self.pulls = [
                *(pull for pull in self.pulls if pull.get("isCrossRepository")),
                {
                    "url": PULL,
                    "title": title,
                    "statusCheckRollup": [],
                    "isCrossRepository": False,
                },
            ]
            return f"Creating pull request\n{PULL}\n"
        if args[:2] == ("pr", "edit"):
            pull = next(pull for pull in self.pulls if pull["url"] == args[2])
            pull["title"] = args[args.index("--title") + 1]
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


def publish(target: Path, monkeypatch: pytest.MonkeyPatch, merge: bool = True) -> int:
    with monkeypatch.context() as scope:
        scope.setenv("GIT_CONFIG_COUNT", "2")
        scope.setenv("GIT_CONFIG_KEY_1", "core.hooksPath")
        scope.setenv("GIT_CONFIG_VALUE_1", "/dev/null")
        return update_pr.publish(target, merge)


def newer_release(source: Path, monkeypatch: pytest.MonkeyPatch, note: str) -> str:
    reference = source / ".agents/skills/he/references/workflow.md"
    reference.write_text(reference.read_text() + f"\n{note}\n")
    select_release(source, monkeypatch)
    return git(source, "rev-parse", "HEAD")


def apply_first_update(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> Path:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    return target


@pytest.fixture
def opened(
    feature: tuple[Path, Path, Path], gh: FakeGh, monkeypatch: pytest.MonkeyPatch
) -> Path:
    target = apply_first_update(feature, monkeypatch)
    assert publish(target, monkeypatch) == 0
    return target


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
    assert f"ready on {BRANCH}" in result
    assert "python3 .hooks/hard-eng.py update-pr" in result
    assert f"ready on {BRANCH}" in update_runner.freshness_note(target)
    second = newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "branch", "--list", "hard-eng/*").split() == [BRANCH]
    assert git(target, "rev-list", "--count", f"origin/main..{BRANCH}") == "1"
    assert second in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")


def test_update_from_a_linked_worktree_ignores_its_inherited_hooks_path(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    stale = target / ".stale-hooks"
    stale.mkdir()
    with (target / ".git/info/exclude").open("a") as exclude:
        exclude.write(".stale-hooks/\n")
    (stale / "pre-commit").write_text("#!/bin/sh\nexit 1\n")
    (stale / "pre-commit").chmod(0o755)
    git(target, "config", "extensions.worktreeConfig", "true")
    linked = target.parent / "linked"
    git(target, "worktree", "add", "-q", "--detach", str(linked), "HEAD")
    git(linked, "config", "--worktree", "core.hooksPath", str(stale))
    first = newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(linked) == 0
    assert first in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")
    assert git(linked, "config", "core.hooksPath") == str(stale)


def test_husky_update_succeeds_when_the_temporary_directory_is_a_symlink(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _, target, _ = release
    husky_project(target)
    add_origin(target)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    symlinked = tmp_path / "symlinked-tmp"
    symlinked.symlink_to(tmp_path / "tmp")
    monkeypatch.setenv("TMPDIR", str(symlinked))
    monkeypatch.setattr(tempfile, "tempdir", None)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "failed" not in result, result


def fix_update_branch(target: Path) -> str:
    fixing = target.parent / "fixing"
    git(target, "worktree", "add", "-q", str(fixing), BRANCH)
    (fixing / "fix.txt").write_text("fix\n")
    return commit(fixing, "fix the update")


def test_background_update_keeps_an_update_branch_being_fixed(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    fixed = fix_update_branch(target)
    newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "rev-parse", BRANCH) == fixed
    assert "unfinished work" in (target / update_runner.RESULT_FILE).read_text()


def second_update_after(
    feature: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    during: Callable[[Path], None],
) -> Path:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    original = update.update

    def update_with(
        root: Path, repair: bool = False, *, remember: Path | None = None
    ) -> str:
        during(target)
        return original(root, repair, remember=remember)

    monkeypatch.setattr(update, "update", update_with)
    newer_release(source, monkeypatch, "second update")
    update_runner.apply_update(target)
    return target


def test_background_update_keeps_a_fix_committed_while_it_ran(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed: list[str] = []
    target = second_update_after(
        feature, monkeypatch, lambda target: fixed.append(fix_update_branch(target))
    )
    assert git(target, "rev-parse", BRANCH) == fixed[0]
    assert git(target.parent / "fixing", "status", "--porcelain") == ""


def test_background_update_keeps_a_fix_committed_and_left_while_it_ran(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixed: list[str] = []

    def fix_and_leave(target: Path) -> None:
        fixed.append(fix_update_branch(target))
        git(target.parent / "fixing", "switch", "-q", "--detach")

    target = second_update_after(feature, monkeypatch, fix_and_leave)
    assert git(target, "rev-parse", BRANCH) == fixed[0]


def test_background_update_reports_a_branch_it_could_not_write(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    def lock(target: Path) -> None:
        (target / ".git/refs/heads" / f"{BRANCH}.lock").write_text("")

    target = second_update_after(feature, monkeypatch, lock)
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "Hard Eng update failed" in result
    assert f"{BRANCH}.lock" in result


def test_background_update_names_a_clean_checked_out_update_branch(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    parked = target.parent / "parked"
    git(target, "worktree", "add", "-q", "-b", BRANCH, str(parked), "main")
    first = newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    result = (target / update_runner.RESULT_FILE).read_text()
    assert "holds unfinished work" not in result
    assert f"checked out in {parked}" in result
    assert f"git -C {parked} switch --detach" in result
    git(parked, "switch", "-q", "--detach")
    assert update_runner.apply_update(target) == 0
    assert first in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")


def test_background_update_records_why_setup_refused_it(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    edited = ".agents/skills/he/references/workflow.md"
    (target / edited).write_text("local edit\n")
    commit(target, "edit a scaffold file")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    refusal = f"{edited} already differs"
    assert refusal in (target / update_runner.RESULT_FILE).read_text()
    assert update_runner.apply_update(target) == 0
    replayed = (target / update_runner.RESULT_FILE).read_text()
    assert refusal in replayed
    assert "not retried" in replayed


def rebase_merge(landing: Path) -> None:
    (landing / "moved.txt").write_text("base moved\n")
    commit(landing, "base moved")
    git(landing, "cherry-pick", f"{BRANCH}~1", BRANCH)


def squash_merge(landing: Path) -> None:
    git(landing, "merge", "-q", "--squash", BRANCH)
    commit(landing, "Update Hard Eng (#1)")


def land(target: Path, merge: Callable[[Path], None]) -> None:
    landing = target.parent / "landing"
    git(target, "worktree", "add", "-q", "--detach", str(landing), "origin/main")
    merge(landing)
    git(landing, "-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "HEAD:main")
    git(target, "worktree", "remove", "--force", str(landing))


def retire_fix(target: Path) -> None:
    git(target, "fetch", "-q", "origin", "main")
    git(target, "switch", "-q", "--detach", "origin/main")
    git(target, "rm", "-q", "fix.txt")
    commit(target, "retire the fix file")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")


@pytest.mark.parametrize("merge", [rebase_merge, squash_merge])
def test_update_after_a_merged_fix_prepares_and_publishes_the_next_release(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    merge: Callable[[Path], None],
) -> None:
    source, target, remote = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    fix_update_branch(target)
    git(target, "worktree", "remove", "--force", str(target.parent / "fixing"))
    git(target, "-c", "core.hooksPath=/dev/null", "push", "-q", "origin", BRANCH)
    land(target, merge)
    second = newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert "unfinished work" not in (target / update_runner.RESULT_FILE).read_text()
    assert second in git(target, "show", f"{BRANCH}:{update.SOURCE_FILE}")
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)


@pytest.mark.parametrize("merge", [rebase_merge, squash_merge])
def test_update_pr_publishes_nothing_after_a_merged_fix_without_a_newer_release(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    merge: Callable[[Path], None],
) -> None:
    source, target, _ = feature
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    fix_update_branch(target)
    git(target, "worktree", "remove", "--force", str(target.parent / "fixing"))
    land(target, merge)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    assert publish(target, monkeypatch) == 0
    retire_fix(target)
    assert publish(target, monkeypatch) == 0
    assert gh.calls == []


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
    assert "pr merge" not in gh.verbs()
    assert f"{PULL}: checks pending" in capsys.readouterr().out
    second = newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)
    assert gh.verbs().count("pr create") == 1
    assert gh.pulls[0]["title"] == f"Update Hard Eng to {second[:12]}"


def test_update_pr_ignores_a_fork_pr_from_a_branch_with_the_same_name(
    feature: tuple[Path, Path, Path], gh: FakeGh, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    fork: dict[str, object] = {
        "url": f"{PULL}0",
        "title": "Fork",
        "statusCheckRollup": [],
        "isCrossRepository": True,
    }
    gh.pulls = [fork]
    newer_release(source, monkeypatch, "first update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    assert gh.verbs().count("pr create") == 1
    assert fork["title"] == "Fork"
    assert not any(fork["url"] in call for call in gh.calls)


def test_update_pr_merges_only_after_every_check_on_the_pushed_head_passed(
    opened: Path,
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = opened
    gh.pulls[0]["statusCheckRollup"] = [
        {"name": "a", "status": "COMPLETED", "conclusion": "SKIPPED"}
    ]
    assert publish(target, monkeypatch) == 0
    assert "pr merge" not in gh.verbs()
    gh.pulls[0]["statusCheckRollup"] = [
        {"name": "a", "status": "COMPLETED", "conclusion": "SUCCESS"},
        {"name": "b", "status": "IN_PROGRESS", "conclusion": ""},
    ]
    assert publish(target, monkeypatch) == 0
    capsys.readouterr()
    assert publish(target, monkeypatch, merge=False) == 0
    assert "pr merge" not in gh.verbs()
    assert "--no-merge` again once the checks pass" in capsys.readouterr().out
    gh.pulls[0]["statusCheckRollup"][1] = {
        "name": "b",
        "status": "COMPLETED",
        "conclusion": "SUCCESS",
    }
    head = git(target, "rev-parse", BRANCH)
    capsys.readouterr()
    assert publish(target, monkeypatch, merge=False) == 0
    assert "pr merge" not in gh.verbs()
    command = f"gh pr merge {PULL} --auto --rebase --match-head-commit {head}"
    assert command in capsys.readouterr().out
    assert publish(target, monkeypatch) == 0
    assert (
        "pr",
        "merge",
        PULL,
        "--auto",
        "--rebase",
        "--match-head-commit",
        head,
    ) in gh.calls


@pytest.mark.parametrize(
    ("allowed", "flag"),
    [
        ({"squashMergeAllowed": True, "mergeCommitAllowed": True}, "--squash"),
        ({"mergeCommitAllowed": True}, "--merge"),
    ],
)
def test_update_pr_uses_a_merge_method_the_repository_allows(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    allowed: dict[str, bool],
    flag: str,
) -> None:
    target = apply_first_update(feature, monkeypatch)
    gh.merging = {
        "rebaseMergeAllowed": False,
        "squashMergeAllowed": False,
        "mergeCommitAllowed": False,
        **allowed,
    }
    assert publish(target, monkeypatch) == 0
    gh.pulls[0]["statusCheckRollup"] = [
        {"name": "a", "status": "COMPLETED", "conclusion": "SUCCESS"}
    ]
    assert publish(target, monkeypatch) == 0
    head = git(target, "rev-parse", BRANCH)
    assert (
        "pr",
        "merge",
        PULL,
        "--auto",
        flag,
        "--match-head-commit",
        head,
    ) in gh.calls


def test_update_pr_waits_for_the_configured_shipping_checks(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = apply_first_update(feature, monkeypatch)
    monkeypatch.setattr(
        update_pr,
        "load_policy",
        Mock(return_value={"base": "main", "checks": ["gate"]}),
    )
    assert publish(target, monkeypatch) == 0
    gh.pulls[0]["statusCheckRollup"] = [
        {"name": "other", "status": "COMPLETED", "conclusion": "SUCCESS"}
    ]
    assert publish(target, monkeypatch) == 0
    assert "pr merge" not in gh.verbs()
    gh.pulls[0]["statusCheckRollup"].append(
        {"name": "gate", "status": "COMPLETED", "conclusion": "SKIPPED"}
    )
    assert publish(target, monkeypatch) == 1
    assert "pr merge" not in gh.verbs()
    gh.pulls[0]["statusCheckRollup"][-1]["conclusion"] = "SUCCESS"
    gh.pulls[0]["statusCheckRollup"][0]["conclusion"] = "FAILURE"
    assert publish(target, monkeypatch) == 1
    assert "pr merge" not in gh.verbs()
    gh.pulls[0]["statusCheckRollup"][0].update(status="IN_PROGRESS", conclusion="")
    assert publish(target, monkeypatch) == 0
    assert "pr merge" not in gh.verbs()
    gh.pulls[0]["statusCheckRollup"][0].update(status="COMPLETED", conclusion="SUCCESS")
    assert publish(target, monkeypatch) == 0
    assert "pr merge" in gh.verbs()


def test_update_pr_does_not_overwrite_a_fix_pushed_to_the_remote_branch(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, remote = feature
    apply_first_update(feature, monkeypatch)
    assert publish(target, monkeypatch) == 0
    other = other_checkout(target, remote)
    git(other, "switch", "-q", BRANCH)
    (other / "fix.txt").write_text("fix\n")
    fix = commit(other, "fix the update")
    git(other, "push", "-q", "--no-verify", "origin", BRANCH)
    newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()
    assert publish(target, monkeypatch) == 1
    assert git(remote, "rev-parse", BRANCH) == fix
    assert "not replaced" in capsys.readouterr().out


def test_update_pr_recreates_the_update_branch_after_the_remote_deleted_it(
    feature: tuple[Path, Path, Path], gh: FakeGh, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, remote = feature
    apply_first_update(feature, monkeypatch)
    assert publish(target, monkeypatch) == 0
    git(remote, "branch", "-qD", BRANCH)
    gh.pulls = []
    newer_release(source, monkeypatch, "second update")
    assert update_runner.apply_update(target) == 0
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)


def other_checkout(target: Path, remote: Path) -> Path:
    other = target.parent / "other"
    git(target.parent, "clone", "-q", str(remote), str(other))
    git(other, "config", "user.name", "Fixture")
    git(other, "config", "user.email", "fixture@example.invalid")
    return other


def test_update_pr_refreshes_a_branch_another_checkout_already_superseded(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, target, remote = feature
    apply_first_update(feature, monkeypatch)
    second = newer_release(source, monkeypatch, "second update")
    other = other_checkout(target, remote)
    assert update_runner.apply_update(other) == 0
    git(other, "push", "-q", "--no-verify", "origin", f"{BRANCH}:main")

    def newest(previous: str) -> str | None:
        return None if previous == second else second

    monkeypatch.setattr(update, "latest_verified", newest)
    assert update_pr.publish(target) == 0
    assert "Nothing to publish" in capsys.readouterr().out
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", BRANCH], cwd=remote, check=False
    ).returncode
    assert gh.calls == []


def test_update_pr_does_not_replace_a_newer_update_with_an_older_branch(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, _, remote = feature
    target = apply_first_update(feature, monkeypatch)
    first = update_runner.revision_at(target, f"refs/heads/{BRANCH}")
    newer_release(source, monkeypatch, "second update")
    other = other_checkout(target, remote)
    assert update_runner.apply_update(other) == 0
    newer = git(other, "rev-parse", BRANCH)
    git(other, "push", "-q", "--no-verify", "origin", BRANCH)
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=first))
    assert publish(target, monkeypatch) == 1
    assert git(remote, "rev-parse", BRANCH) == newer
    assert "newer Hard Eng update" in capsys.readouterr().out
    assert gh.calls == []


def test_update_pr_reports_a_failing_pr_with_its_fix_steps(
    opened: Path,
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target = opened
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
    target = apply_first_update(feature, monkeypatch)
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


@pytest.mark.parametrize(
    "marker,skill",
    [
        ("appwrite.config.json", "appwrite-backend"),
        ("pubspec.yaml", "building-flutter-apps"),
    ],
)
def test_next_update_adds_the_stack_skill_the_base_branch_now_needs(
    feature: tuple[Path, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
    marker: str,
    skill: str,
) -> None:
    source, target, _ = feature
    (target / marker).write_text("{}\n" if marker.endswith(".json") else "name: app\n")
    commit(target, "plan the stack")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")
    newer_release(source, monkeypatch, "stack update")
    assert update_runner.apply_update(target) == 0
    assert git(target, "ls-tree", "--name-only", BRANCH, f".claude/skills/{skill}")
    assert git(target, "show", f"{BRANCH}:.agents/skills/{skill}/SKILL.md")


def test_setup_rerun_without_a_newer_release_publishes_its_repair(
    feature: tuple[Path, Path, Path],
    gh: FakeGh,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, target, remote = feature
    (target / "appwrite.config.json").write_text("{}\n")
    commit(target, "plan the backend")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    assert "hard-eng.py update-pr" in update_runner.locked_update(target, repair=True)
    assert git(target, "show", f"{BRANCH}:.agents/skills/appwrite-backend/SKILL.md")
    checkout = target.parent / "repair"
    git(target, "worktree", "add", "-q", str(checkout), BRANCH)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert change_size.size_verdict(checkout) == (
        True,
        "only files the verified Hard Eng update wrote",
    )
    git(target, "worktree", "remove", "--force", str(checkout))
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)
    create = next(call for call in gh.calls if call[:2] == ("pr", "create"))
    assert create[create.index("--title") + 1] == "Repair the Hard Eng installation"
    fix_update_branch(target)
    git(target, "worktree", "remove", "--force", str(target.parent / "fixing"))
    (target / "project.txt").write_text("base moved\n")
    commit(target, "base moved")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == git(target, "rev-parse", BRANCH)
    land(target, squash_merge)
    update_runner.locked_update(target, repair=True)
    assert publish(target, monkeypatch) == 0
    gh.pulls = []
    published = git(remote, "rev-parse", BRANCH)
    retire_fix(target)
    assert publish(target, monkeypatch) == 0
    assert git(remote, "rev-parse", BRANCH) == published
    assert gh.verbs().count("pr create") == 1


def test_setup_rerun_repair_adds_the_workflow_checks_with_the_workflow(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, target, _ = feature
    git(target, "rm", "-rq", ".github")
    gates = target / "hard-eng.gates.json"
    config = json.loads(gates.read_text())
    config["shared"] = [
        check
        for check in config["shared"]
        if check.get("role") not in {"workflows", "ci-security"}
    ]
    gates.write_text(json.dumps(config, indent=2) + "\n")
    commit(target, "install before the shipping policy")
    config["shipping"] = default_policy()
    gates.write_text(json.dumps(config, indent=2) + "\n")
    commit(target, "add the shipping policy")
    git(target, "push", "-q", "--no-verify", "origin", "HEAD:main")
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    update_runner.locked_update(target, repair=True)
    assert git(target, "show", f"{BRANCH}:.github/workflows/hard-eng.yml")
    repaired = json.loads(git(target, "show", f"{BRANCH}:hard-eng.gates.json"))
    assert {"workflows", "ci-security"} <= {
        check.get("role") for check in repaired["shared"]
    }


def test_setup_rerun_restores_a_missing_pre_push_hook_before_the_first_push(
    release: tuple[Path, Path, str],
) -> None:
    _, target, _ = release
    hook = target / ".git/hooks/pre-push"
    hook.unlink(missing_ok=True)
    assert (
        update_runner.locked_update(target, repair=True) == update_runner.NOT_PUBLISHED
    )
    assert hook.is_file()


def test_setup_rerun_restores_the_checkouts_missing_pre_push_hook_when_published(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    _, target, _ = feature
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    hook = target / ".git/hooks/pre-push"
    hook.unlink(missing_ok=True)
    update_runner.locked_update(target, repair=True)
    assert hook.is_file()


def test_setup_rerun_restores_a_huskys_missing_launcher_in_the_checkout(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    husky_project(target)
    select_release(source, monkeypatch)
    update.update(target)
    launcher = target / ".husky/pre-push"
    assert launcher.is_file()
    add_origin(target)
    monkeypatch.setattr(update_runner.signal, "signal", Mock())
    monkeypatch.setattr(update, "latest_verified", Mock(return_value=None))
    launcher.unlink()
    update_runner.locked_update(target, repair=True)
    assert launcher.is_file()
    assert 'hard-eng.py" pre-push' in launcher.read_text()


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


def test_manual_setup_rerun_prints_a_refusal_as_a_message(
    feature: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = feature
    monkeypatch.setenv("UV_OFFLINE", "1")
    with update_runner.lock_file(target).open("a") as handle:
        assert update_runner.exclusive(handle)
        result = subprocess.run(
            ["sh", str(source / "setup.sh"), str(source)],
            cwd=target,
            capture_output=True,
            text=True,
            check=False,
        )
    assert result.returncode == 1, result.stderr
    assert "Another Hard Eng update is already running" in result.stderr
    assert "Traceback" not in result.stderr


def test_update_branch_needs_no_plan_for_files_the_update_wrote(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Issue 299: setup's own edits outside the scaffold made update PRs demand a plan."""
    import change_size

    source, target, _ = release
    ignore = target / ".gitignore"
    current = ignore.read_text()
    ignore.write_text("".join(current.splitlines(keepends=True)[:-1]))
    retired = {"mcpServers": {"context-mode": {"command": "context-mode"}}}
    (target / ".mcp.json").write_text(json.dumps(retired))
    commit(target, "ignore list and MCP file from an older release")
    git(target, "update-ref", "refs/heads/main", "HEAD")
    git(target, "checkout", "-qb", update_runner.UPDATE_BRANCH)
    select_release(source, monkeypatch)
    update.update(target)
    assert ignore.read_text() == current
    assert not (target / ".mcp.json").exists()
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    small, reason = change_size.size_verdict(target)
    assert small, reason
    (target / "package.json").write_text('{"private":true,"type":"module"}')
    commit(target, "project edit beside the update")
    assert change_size.size_verdict(target) == (
        False,
        "it changes package.json, which always needs a plan",
    )
    (target / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    commit(target, "binary file beside the update")
    assert change_size.size_verdict(target) == (
        False,
        "it adds, deletes or renames the file logo.png",
    )


def test_update_branch_check_skips_an_unrelated_draft_plan(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A project's open Draft plan blocked its Hard Eng update PR check."""
    import plans

    source, target, _ = release
    (target / "PLAN.md").write_text("# Later work\n\nStatus: Draft\n")
    commit(target, "draft plan for later work")
    git(target, "update-ref", "refs/heads/main", "HEAD")
    git(target, "checkout", "-qb", update_runner.UPDATE_BRANCH)
    select_release(source, monkeypatch)
    update.update(target)
    monkeypatch.setattr(update, "verified_revision", Mock(return_value=True))
    assert plans.validate_plans(target, "main") == "Complete"
    (target / "app.py").write_text("print('project work')\n")
    commit(target, "project work beside the update")
    with pytest.raises(ValueError, match="PLAN.md: plan needs"):
        plans.validate_plans(target, "main")

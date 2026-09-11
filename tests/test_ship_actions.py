"""Exercise guarded cleanup against actual refs and linked Git worktrees."""

import json
import subprocess
import sys
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import ship_actions
from shipping import Shipment, ShippingPolicy, git


@pytest.fixture
def delivered_worktree(tmp_path: Path, completed_plan: str) -> tuple[Path, Shipment]:
    root, bare, task = (tmp_path / name for name in ("checkout", "origin.git", "task"))
    git(tmp_path, "init", "-q", "-b", "main", str(root))
    git(tmp_path, "init", "--bare", "-q", str(bare))
    git(root, "config", "user.name", "Ship Fixture")
    git(root, "config", "user.email", "ship-fixture@example.test")
    (root / "PLAN.md").write_text(completed_plan + "\nDelivery target: Merge\n")
    (root / ".gitignore").write_text("*.private\n")
    git(root, "add", "PLAN.md", ".gitignore")
    git(root, "commit", "-qm", "baseline")
    git(root, "remote", "add", "origin", str(bare))
    git(root, "push", "-q", "origin", "main")
    git(root, "worktree", "add", "-qb", "feature/ship", str(task))
    (task / "change.txt").write_text("authorized behavior\n")
    git(task, "add", "change.txt")
    git(task, "commit", "-qm", "task behavior")
    head = git(task, "rev-parse", "HEAD").strip()
    git(task, "push", "-q", "origin", "feature/ship")
    git(root, "merge", "--squash", "feature/ship")
    git(root, "commit", "-qm", "land task through squash")
    merged = git(root, "rev-parse", "HEAD").strip()
    git(root, "push", "-q", "origin", "main")
    return root, Shipment(
        root=task,
        plan=task / "PLAN.md",
        pr_url="https://github.com/fixture/project/pull/1",
        repository="fixture/project",
        remote="origin",
        remote_url=str(bare),
        branch="feature/ship",
        head_sha=head,
        base="main",
        merged_sha=merged,
        delivery_target="Merge",
    )


def test_cleanup_removes_only_squash_merged_task(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    assert shipment.head_sha != shipment.merged_sha
    (root / "unrelated.txt").write_text("keep coordinator work")
    ship_actions.cleanup(root, shipment)
    assert not shipment.root.exists()
    assert git(root, "branch", "--list", shipment.branch).strip() == ""
    assert not git(
        root, "for-each-ref", f"refs/remotes/origin/{shipment.branch}"
    ).strip()
    assert ship_actions.remote_branch(root, shipment.remote, shipment.branch) is None
    assert (root / "unrelated.txt").read_text() == "keep coordinator work"
    assert (
        ship_actions.remote_branch(root, shipment.remote, "main") == shipment.merged_sha
    )


@pytest.mark.parametrize("path", ["change.txt", "untracked.txt", "notes.private"])
def test_cleanup_preserves_every_uncommitted_file(
    delivered_worktree: tuple[Path, Shipment], path: str
) -> None:
    root, shipment = delivered_worktree
    (shipment.root / path).write_text("valuable work")
    with pytest.raises(ValueError, match="modified, untracked or ignored"):
        ship_actions.cleanup(root, shipment)
    assert (shipment.root / path).read_text() == "valuable work"
    assert (
        ship_actions.remote_branch(root, "origin", shipment.branch) == shipment.head_sha
    )


def test_cleanup_preserves_locked_and_current_worktrees(
    delivered_worktree: tuple[Path, Shipment], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, shipment = delivered_worktree
    git(root, "worktree", "lock", str(shipment.root))
    with pytest.raises(ValueError, match="unlocked"):
        ship_actions.cleanup(root, shipment)
    git(root, "worktree", "unlock", str(shipment.root))
    monkeypatch.chdir(shipment.root)
    with pytest.raises(ValueError, match="outside"):
        ship_actions.cleanup(root, shipment)
    assert shipment.root.exists()


def test_cleanup_rejects_main_other_repository_and_added_commits(
    delivered_worktree: tuple[Path, Shipment], tmp_path: Path
) -> None:
    root, shipment = delivered_worktree
    with pytest.raises(ValueError, match="main worktree"):
        ship_actions.cleanup(root, replace(shipment, root=root))
    other = tmp_path / "other"
    git(tmp_path, "init", "-q", str(other))
    with pytest.raises(ValueError, match="coordinator's repository"):
        ship_actions.cleanup(other, shipment)
    git(shipment.root, "commit", "--allow-empty", "-qm", "new independent work")
    with pytest.raises(ValueError, match="commits added"):
        ship_actions.cleanup(root, shipment)
    assert shipment.root.exists()


def test_cleanup_preserves_active_git_operation(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    lock = Path(git(shipment.root, "rev-parse", "--git-path", "index.lock").strip())
    lock.write_text("active Git operation")
    with pytest.raises(ValueError, match="active Git index lock"):
        ship_actions.cleanup(root, shipment)
    assert lock.read_text() == "active Git operation"
    assert (
        ship_actions.remote_branch(root, "origin", shipment.branch) == shipment.head_sha
    )


def test_cleanup_preserves_submodules_even_when_git_ignores_them(
    delivered_worktree: tuple[Path, Shipment], tmp_path: Path
) -> None:
    root, shipment = delivered_worktree
    original_head = shipment.head_sha
    module = tmp_path / "module"
    git(tmp_path, "init", "-q", str(module))
    git(module, "config", "user.name", "Ship Fixture")
    git(module, "config", "user.email", "ship-fixture@example.test")
    (module / "work.txt").write_text("baseline")
    git(module, "add", "work.txt")
    git(module, "commit", "-qm", "module baseline")
    git(
        shipment.root,
        "-c",
        "protocol.file.allow=always",
        "submodule",
        "add",
        "-q",
        str(module),
        "component",
    )
    git(shipment.root, "commit", "-qm", "include module")
    shipment = replace(
        shipment, head_sha=git(shipment.root, "rev-parse", "HEAD").strip()
    )
    with pytest.raises(ValueError, match="initialized submodules"):
        ship_actions.cleanup(root, shipment)
    git(shipment.root, "config", "diff.ignoreSubmodules", "all")
    nested = shipment.root / "component/work.txt"
    nested.write_text("valuable nested work")
    assert not git(shipment.root, "status", "--porcelain").strip()
    with pytest.raises(ValueError, match="modified, untracked or ignored"):
        ship_actions.cleanup(root, shipment)
    assert nested.read_text() == "valuable nested work"
    assert ship_actions.remote_branch(root, "origin", shipment.branch) == original_head


def test_cleanup_rejects_remote_branch_reuse(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    git(root, "push", "-q", "--force", "origin", f"main:{shipment.branch}")
    with pytest.raises(ValueError, match="remote branch with additional work"):
        ship_actions.cleanup(root, shipment)
    assert shipment.root.exists()
    assert (
        ship_actions.remote_branch(root, "origin", shipment.branch)
        == shipment.merged_sha
    )


def test_cleanup_preserves_unrelated_branch_at_same_commit(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    git(shipment.root, "branch", "-m", "feature/unrelated")
    with pytest.raises(ValueError, match="no longer owns"):
        ship_actions.cleanup(root, shipment)
    assert shipment.root.exists()
    assert git(root, "rev-parse", "feature/unrelated").strip() == shipment.head_sha


def test_cleanup_handles_already_deleted_remote_branch(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    git(root, "push", "-q", "origin", f":{shipment.branch}")
    ship_actions.cleanup(root, shipment)
    assert not shipment.root.exists()
    assert git(root, "branch", "--list", shipment.branch).strip() == ""


@pytest.mark.parametrize("endpoint", ["fetch", "push", "multiple-push"])
def test_cleanup_preserves_task_after_remote_retargeting(
    delivered_worktree: tuple[Path, Shipment], tmp_path: Path, endpoint: str
) -> None:
    root, shipment = delivered_worktree
    other = tmp_path / "other.git"
    git(root, "clone", "--bare", shipment.remote_url, str(other))
    setting = "url" if endpoint == "fetch" else "pushurl"
    if endpoint == "multiple-push":
        git(root, "config", "remote.origin.pushurl", shipment.remote_url)
    option = "--add" if endpoint == "multiple-push" else "--replace-all"
    git(root, "config", option, f"remote.origin.{setting}", str(other))
    with pytest.raises(ValueError, match="remote changed|different push endpoint"):
        ship_actions.cleanup(root, shipment)
    assert shipment.root.exists()
    for remote in (shipment.remote_url, str(other)):
        assert (
            ship_actions.remote_branch(root, remote, shipment.branch)
            == shipment.head_sha
        )


def test_cleanup_compare_and_delete_preserves_racing_local_ref(
    delivered_worktree: tuple[Path, Shipment], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, shipment = delivered_worktree

    def concurrent_git(directory: Path, *arguments: str) -> str:
        output = git(directory, *arguments)
        if arguments[:2] == ("worktree", "remove"):
            assert shipment.merged_sha is not None
            git(
                root, "update-ref", f"refs/heads/{shipment.branch}", shipment.merged_sha
            )
        return output

    monkeypatch.setattr(ship_actions, "git", concurrent_git)
    with pytest.raises(ValueError, match="git"):
        ship_actions.cleanup(root, shipment)
    assert git(root, "rev-parse", shipment.branch).strip() == shipment.merged_sha


def test_cleanup_hook_cannot_recreate_python_cache_in_task(
    delivered_worktree: tuple[Path, Shipment],
) -> None:
    root, shipment = delivered_worktree
    hook = Path(git(root, "rev-parse", "--git-path", "hooks/pre-push").strip())
    hook = root / hook
    command = [
        sys.executable,
        "-X",
        f"pycache_prefix={shipment.root}/hook-cache",
        "-c",
        "import json",
    ]
    hook.write_text(
        "#!/usr/bin/env python3\nimport subprocess, sys\n"
        f"sys.exit(subprocess.call({command!r}))\n"
    )
    hook.chmod(0o755)
    ship_actions.cleanup(root, shipment)
    assert not shipment.root.exists()
    assert ship_actions.remote_branch(root, "origin", shipment.branch) is None


def test_ship_routes_refuse_wrong_plan_and_unselected_merge(
    delivered_worktree: tuple[Path, Shipment], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, shipment = delivered_worktree
    verified = Mock(return_value=shipment)
    monkeypatch.setattr(ship_actions, "verify", verified)
    for plan, method, message in [
        ("../outside.md", "squash", "inside its worktree"),
        ("PLAN.md", None, "merge method"),
    ]:
        with pytest.raises(ValueError, match=message):
            ship_actions.run(
                root, plan, shipment.pr_url, "merge", str(shipment.root), method
            )
    verified.assert_not_called()


def test_ship_merge_matches_verified_head_and_checks_result(
    delivered_worktree: tuple[Path, Shipment], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, shipment = delivered_worktree
    verified = Mock(return_value=shipment)
    remote = Mock(return_value="Merged")
    monkeypatch.setattr(ship_actions, "verify", verified)
    monkeypatch.setattr(ship_actions, "gh", remote)
    assert (
        ship_actions.run(
            root, "PLAN.md", shipment.pr_url, "merge", str(shipment.root), "squash"
        )
        == 0
    )
    assert verified.call_args_list[-1].args[-1] == "delivered"
    assert remote.call_args.args[-2:] == ("--match-head-commit", shipment.head_sha)
    monkeypatch.setattr(
        ship_actions,
        "verify",
        Mock(return_value=replace(shipment, delivery_target="PR")),
    )
    remote.reset_mock()
    with pytest.raises(ValueError, match="not merging"):
        ship_actions.run(
            root, "PLAN.md", shipment.pr_url, "merge", str(shipment.root), "squash"
        )
    remote.assert_not_called()


def test_pre_push_blocks_base_before_running_commands(
    runner: ModuleType, shipping_policy: ShippingPolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    (runner.ROOT / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": shipping_policy})
    )
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(f"refs/heads/main {'1' * 40} refs/heads/main {'2' * 40}\n"),
    )
    commands = Mock()
    monkeypatch.setattr(runner.subprocess, "run", commands)
    with pytest.raises(ValueError, match="use a PR"):
        runner.pre_push()
    commands.assert_not_called()


def test_pre_push_budget_fails_even_when_commands_pass(
    runner: ModuleType, shipping_policy: ShippingPolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    shipping_policy["pre_push_seconds"] = 1.0
    (runner.ROOT / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": shipping_policy})
    )
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(f"refs/heads/task {'1' * 40} refs/heads/task {'2' * 40}\n"),
    )
    clock = iter([0.0, 2.0])
    monkeypatch.setattr(ship_actions.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(
        runner.subprocess, "run", Mock(return_value=subprocess.CompletedProcess([], 0))
    )
    with pytest.raises(ValueError, match="time budget"):
        runner.pre_push()

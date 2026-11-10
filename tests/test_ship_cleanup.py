from pathlib import Path

import pytest
import ship_actions
from conftest import add_origin, commit, init
from shipping import Shipment, git


def test_cleanup_ignores_only_what_hard_eng_put_in_the_worktree(
    tmp_path: Path,
) -> None:
    root, task = tmp_path / "checkout", tmp_path / "task"
    init(root)
    (root / ".gitignore").write_text("*.private\n.env*\n.husky/_/\n")
    (root / ".husky").mkdir()
    (root / ".husky/pre-push").write_text("hook\n")
    commit(root, "baseline")
    remote = add_origin(root)
    git(root, "config", "core.hooksPath", ".husky/_")
    git(root, "worktree", "add", "-qb", "feature/ship", str(task))
    git(task, "push", "-q", "origin", "feature/ship")
    (root / ".husky/_").mkdir()
    (root / ".husky/_/pre-push").write_text("shim\n")
    (root / ".env.local").write_text("KEY=value\n")
    ship_actions.link_local_files(root, task)
    assert (task / ".env.local").is_symlink()
    assert (task / ".husky/_/pre-push").is_file()
    shipment = Shipment(
        root=task,
        plan=task / "PLAN.md",
        pr_url="https://github.com/fixture/project/pull/1",
        repository="fixture/project",
        remote="origin",
        remote_url=str(remote),
        branch="feature/ship",
        head_sha=git(task, "rev-parse", "HEAD").strip(),
        base="main",
        merged_sha=git(root, "rev-parse", "HEAD").strip(),
        delivery_target="Merge",
    )
    (task / "notes.private").write_text("valuable work")
    with pytest.raises(ValueError, match="modified, untracked or ignored"):
        ship_actions.cleanup(root, shipment)
    (task / "notes.private").unlink()
    ship_actions.cleanup(root, shipment)
    assert not task.exists()

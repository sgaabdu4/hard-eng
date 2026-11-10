from pathlib import Path

import pytest
import ship_actions
from conftest import add_origin, commit, init
from shipping import Shipment, git


@pytest.fixture(
    params=[True, False], ids=["husky ignores itself", "project ignores it"]
)
def shipped(
    tmp_path: Path, request: pytest.FixtureRequest
) -> tuple[Path, Path, Shipment]:
    husky_ignores_itself: bool = request.param
    root, task = tmp_path / "checkout", tmp_path / "task"
    init(root)
    listed = "" if husky_ignores_itself else ".husky/_/\n"
    (root / ".gitignore").write_text("*.private\n.env*\n" + listed)
    (root / ".husky").mkdir()
    (root / ".husky/pre-push").write_text("hook\n")
    commit(root, "baseline")
    remote = add_origin(root)
    git(root, "config", "core.hooksPath", ".husky/_")
    git(root, "worktree", "add", "-qb", "feature/ship", str(task))
    git(task, "push", "-q", "origin", "feature/ship")
    (root / ".husky/_").mkdir()
    (root / ".husky/_/pre-push").write_text("shim\n")
    (root / ".husky/_/h").write_text("shim\n")
    (root / ".husky/_/link").symlink_to("h")
    if husky_ignores_itself:
        (root / ".husky/_/.gitignore").write_text("*\n")
    (root / ".env.local").write_text("KEY=value\n")
    ship_actions.link_local_files(root, task)
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
    return root, task, shipment


def test_cleanup_ignores_only_what_hard_eng_put_in_the_worktree(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    assert (task / ".env.local").is_symlink()
    assert (task / ".husky/_/pre-push").is_file()
    (task / "notes.private").write_text("valuable work")
    with pytest.raises(ValueError, match="modified, untracked or ignored"):
        ship_actions.cleanup(root, shipment)
    (task / "notes.private").unlink()
    link = task / ".env.local"
    link.unlink()
    link.write_text("KEY=changed in the task\n")
    with pytest.raises(ValueError, match="modified, untracked or ignored"):
        ship_actions.cleanup(root, shipment)
    link.unlink()
    link.symlink_to(root / ".env.local")
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


def test_cleanup_keeps_what_the_task_added_or_changed_in_the_copied_hooks_folder(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    added = task / ".husky/_/mine"
    added.write_text("a hook that the task wrote\n")
    with pytest.raises(ValueError, match=r"ignored work: \.husky/_/mine$"):
        ship_actions.cleanup(root, shipment)
    added.unlink()
    shim = task / ".husky/_/h"
    shim.write_text("changed in the task\n")
    with pytest.raises(ValueError, match=r"ignored work: \.husky/_/h$"):
        ship_actions.cleanup(root, shipment)
    shim.write_text("shim\n")
    moved = task / ".husky/_/link"
    moved.unlink()
    moved.symlink_to("pre-push")
    with pytest.raises(ValueError, match=r"ignored work: \.husky/_/link$"):
        ship_actions.cleanup(root, shipment)
    moved.unlink()
    moved.symlink_to("h")
    ship_actions.cleanup(root, shipment)
    assert not task.exists()

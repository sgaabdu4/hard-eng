import json
import shutil
from pathlib import Path

import pytest
import ship_actions
import shipping
from conftest import add_origin, commit, init
from shipping import Shipment, git
from test_shipping import (
    _PR_URL,
    FakeGitHub,
    Fixture,
    _check,
    _fixture,
    _native,
    _patch_gh,
    _pull,
)


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
    (root / ".gitignore").write_text("*.private\n.env*\n__pycache__/\n" + listed)
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
    with pytest.raises(ValueError, match=r"ignored work: \.husky/\."):
        ship_actions.cleanup(root, shipment)
    added.unlink()
    shim = task / ".husky/_/h"
    shim.write_text("changed in the task\n")
    with pytest.raises(ValueError, match=r"ignored work: \.husky/\."):
        ship_actions.cleanup(root, shipment)
    shim.write_text("shim\n")
    moved = task / ".husky/_/link"
    moved.unlink()
    moved.symlink_to("pre-push")
    with pytest.raises(ValueError, match=r"ignored work: \.husky/\."):
        ship_actions.cleanup(root, shipment)
    moved.unlink()
    moved.symlink_to("h")
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


def test_cleanup_does_not_count_compiled_hook_modules(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    compiled = task / ".hooks/__pycache__"
    compiled.mkdir(parents=True)
    (compiled / "hard-eng.cpython-313.pyc").write_bytes(b"compiled")
    other = task / "tools/__pycache__"
    other.mkdir(parents=True)
    (other / "mine.cpython-313.pyc").write_bytes(b"compiled")
    with pytest.raises(ValueError, match=r"ignored work: tools/\."):
        ship_actions.cleanup(root, shipment)
    (other / "mine.cpython-313.pyc").unlink()
    other.rmdir()
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


def keep_proof_in_the_task(root: Path, task: Path) -> Path:
    with (root / ".git/info/exclude").open("a") as exclude:
        exclude.write(".hard-eng/\n")
    proof = task / ".hard-eng/browser"
    proof.mkdir(parents=True)
    (proof / "after-1280.png").write_bytes(b"capture")
    (proof / "after-1280.json").write_text("{}")
    return proof


def test_cleanup_removes_the_proof_folder_instead_of_asking_for_its_deletion(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    keep_proof_in_the_task(root, task)
    (task / "notes.private").write_text("valuable work")
    with pytest.raises(ValueError, match=r"ignored work: notes\.private\.") as refusal:
        ship_actions.cleanup(root, shipment)
    assert ".hard-eng" not in str(refusal.value)
    (task / "notes.private").unlink()
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


def test_cleanup_keeps_private_files_that_other_skills_put_in_the_proof_folder(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    keep_proof_in_the_task(root, task)
    report = task / ".hard-eng/client-report/2026-11-25/report.html"
    report.parent.mkdir(parents=True)
    report.write_text("a private report")
    with pytest.raises(ValueError, match=r"ignored work: \.hard-eng/\."):
        ship_actions.cleanup(root, shipment)
    assert report.is_file()
    shutil.rmtree(task / ".hard-eng/client-report")
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


def test_cleanup_keeps_the_proof_when_delivered_does_not_pass(
    shipped: tuple[Path, Path, Shipment], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, task, shipment = shipped
    proof = keep_proof_in_the_task(root, task)

    def pending(*_: object) -> Shipment:
        raise shipping.ShippingError("base-branch CI has not finished")

    monkeypatch.setattr(ship_actions, "verify", pending)
    with pytest.raises(shipping.ShippingError, match="has not finished"):
        ship_actions.run(root, None, shipment.pr_url, "cleanup", str(task), None)
    assert (proof / "after-1280.png").is_file()


def test_cleanup_with_no_worktree_names_the_option(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    with pytest.raises(ValueError, match="Cleanup needs --worktree <path of the task"):
        ship_actions.run(root, None, shipment.pr_url, "cleanup", None, None)
    assert task.exists()


def test_the_cleanup_refusal_names_every_kept_path_and_the_step(
    shipped: tuple[Path, Path, Shipment],
) -> None:
    root, task, shipment = shipped
    for name in (".coverage", "coverage/a.json", "coverage/b.json", ".venv/x/y.py"):
        (task / name).parent.mkdir(parents=True, exist_ok=True)
        (task / name).write_text("x")
    (task / "notes.private").write_text("valuable work")
    with pytest.raises(ValueError) as refusal:
        ship_actions.cleanup(root, shipment)
    message = str(refusal.value)
    for kept in (
        " .coverage, ",
        " coverage/, ",
        " .venv/, ",
        " notes.private.",
    ):
        assert message.count(kept) == 1
    assert message.endswith(
        "In that worktree, `git status --ignored --untracked-files=all` lists "
        "each file under those paths. Delete the generated files that nobody "
        "needs and move the others out of the worktree. Copy an edited tracked file "
        "out, then undo its edit. Then run cleanup again."
    )
    assert task.exists()
    (task / ".coverage").unlink()
    shutil.rmtree(task / "coverage")
    shutil.rmtree(task / ".venv")
    (task / "notes.private").rename(root.parent / "notes.private")
    ship_actions.cleanup(root, shipment)
    assert not task.exists()


@pytest.mark.parametrize("stage", ["ready", "delivered"])
def test_a_leftover_file_in_a_merged_small_task_gets_the_clean_checkout_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    fixture = _fixture(tmp_path)
    (fixture.root / "source.txt").write_text("fixture\nsmall fix\n")
    _native(fixture.root, "commit", "-qam", "small fix")
    head = _native(fixture.root, "rev-parse", "HEAD")
    merged = {"state": "closed", "merged": True, "merged_at": "2026-09-10T11:00:00Z"}
    changes = merged | {"merge_commit_sha": head} if stage == "delivered" else {}
    fixture = Fixture(fixture.root, fixture.plan, head)
    _patch_gh(monkeypatch, FakeGitHub(_pull(fixture, **changes), [_check(head)]))
    (fixture.root / "scratch.txt").write_text("left behind\n")
    with pytest.raises(shipping.ShippingError, match="clean task checkout"):
        shipping.verify(fixture.root, None, _PR_URL, stage)


def test_cleanup_reads_a_policy_that_a_newer_release_gave_more_keys(
    delivered_worktree: tuple[Path, Shipment],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, shipment = delivered_worktree
    held = tmp_path / "newer-policy"
    held.mkdir()
    policy = {
        "base": "main",
        "checks": ["build"],
        "ui_paths": [],
        "ci_seconds": 180,
        "pre_push_seconds": 180,
        "delivery": [],
        "added_by_a_newer_release": True,
    }
    (held / "hard-eng.gates.json").write_text(json.dumps({"shipping": policy}))

    def verify(*_arguments: object) -> Shipment:
        shipping.load_policy(held)
        return shipment

    monkeypatch.setattr(ship_actions, "verify", verify)
    with pytest.raises(shipping.ShippingError, match="unknown or missing keys"):
        ship_actions.run(root, None, shipment.pr_url, "delivered", None, None)
    assert shipment.root.exists()
    ship_actions.run(root, None, shipment.pr_url, "cleanup", str(shipment.root), None)
    assert not shipment.root.exists()

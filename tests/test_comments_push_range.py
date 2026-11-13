"""The assertion count judges the whole branch when a later push range shows a net loss."""

import subprocess
from pathlib import Path

import pytest
from comments import validate_suppressions
from conftest import commit, git, init
from shipping import ShippingPolicy
from test_comments import pre_push_repo

OFF = "A change must not switch a check off"
KEPT = "def test_kept():\n    assert a() == 1\n    assert b() == 2\n"
ADDED = "def test_added():\n    assert c() == 3\n    assert d() == 4\n"


def branch_root(tmp_path: Path, base_files: dict[str, str]) -> Path:
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    for name, text in base_files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    commit(root, "baseline")
    git(root, "branch", "-M", "main")
    git(root, "switch", "-qc", "feature")
    return root


def test_a_test_the_branch_added_and_a_later_push_deleted_loses_nothing(
    tmp_path: Path,
) -> None:
    root = branch_root(tmp_path, {"tests/test_a.py": KEPT})
    (root / "tests/test_new.py").write_text(ADDED)
    pushed = commit(root, "add a test")
    (root / "tests/test_new.py").unlink()
    commit(root, "delete it")
    validate_suppressions(root, pushed)


def test_a_removed_test_recorded_in_an_earlier_push_passes_a_later_push(
    tmp_path: Path,
) -> None:
    root = branch_root(tmp_path, {"tests/test_a.py": KEPT})
    (root / "tests/test_new.py").write_text(ADDED)
    record = "Removed test: tests/test_new.py :: test_added :: test_kept proves it"
    (root / "features/x").mkdir(parents=True)
    (root / "features/x/PLAN.md").write_text(f"# Plan\n\n{record}\n")
    pushed = commit(root, "add a test and its record")
    (root / "tests/test_new.py").unlink()
    commit(root, "delete the test")
    validate_suppressions(root, pushed)


def test_assertions_moved_between_test_files_across_two_pushes_pass(
    tmp_path: Path,
) -> None:
    root = branch_root(tmp_path, {"tests/test_a.py": KEPT})
    (root / "tests/test_b.py").write_text(KEPT.replace("test_kept", "test_moved"))
    pushed = commit(root, "copy the test to a new file")
    (root / "tests/test_a.py").write_text("")
    commit(root, "drop it from the old file")
    validate_suppressions(root, pushed)


def refused_later_push(tmp_path: Path) -> tuple[Path, str]:
    root = branch_root(tmp_path, {"tests/test_a.py": KEPT})
    (root / "NOTES.md").write_text("notes\n")
    pushed = commit(root, "an unrelated first push")
    (root / "tests/test_a.py").write_text(KEPT.replace("    assert b() == 2\n", ""))
    commit(root, "drop an assertion")
    with pytest.raises(ValueError, match=OFF) as error:
        validate_suppressions(root, pushed)
    return root, str(error.value)


def test_a_net_loss_from_the_branch_point_still_fails_a_later_push(
    tmp_path: Path,
) -> None:
    _, message = refused_later_push(tmp_path)
    assert "tests lose 1 assertion lines net (1 removed, 0 added)" in message


def test_the_loss_message_names_the_range_it_judged(tmp_path: Path) -> None:
    root, message = refused_later_push(tmp_path)
    assert f"since {git(root, 'rev-parse', 'main')[:12]}" in message


def test_pre_push_accepts_a_test_the_branch_added_then_deleted(
    tmp_path: Path, completed_plan: str, shipping_policy: ShippingPolicy
) -> None:
    root = pre_push_repo(tmp_path, shipping_policy)
    git(root, "switch", "-qc", "feature")
    (root / "PLAN.md").write_text(completed_plan)
    (root / "tests").mkdir()
    (root / "tests/test_new.py").write_text(ADDED)
    commit(root, "add a test")
    push = ["git", "push", "-q", "origin", "feature"]
    first = subprocess.run(push, cwd=root, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr[-2000:]
    (root / "tests/test_new.py").unlink()
    git(root, "commit", "-qam", "delete the test")
    second = subprocess.run(push, cwd=root, capture_output=True, text=True, check=False)
    assert second.returncode == 0, second.stderr[-2000:]

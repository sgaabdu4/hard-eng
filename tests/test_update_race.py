"""The update's private worktree goes away even when a git hook left a child that still writes in it."""

import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
import update
import update_pr
import update_runner
from conftest import SOURCE, add_origin, git
from test_update_runner import install_hook, pushed_release
from test_updates import select_release

WRITER = (
    "( i=0; while [ $i -lt 20000 ]; do echo x > writer-$i.txt; i=$((i+1)); done )"
    " >/dev/null 2>&1 &\n"
)
WORKER = """
import sys
from pathlib import Path
sys.path.insert(0, {hooks!r})
import update, update_runner
update.latest_verified = lambda previous: {revision!r}
update_runner.update_command = lambda *options: [
    sys.executable, {me!r}, "apply" if options else "supervise"
]
root = Path.cwd()
if sys.argv[1] == "apply":
    raise SystemExit(update_runner.apply_update(root))
raise SystemExit(update_runner.run_update(root))
"""


def private_folders() -> list[Path]:
    return list(Path(tempfile.gettempdir()).glob("hard-eng-update-*"))


def test_a_hook_child_in_the_private_worktree_does_not_fail_the_update(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    install_hook(target, "post-commit", WRITER)
    assert update_runner.apply_update(target) == 0
    result = update_runner.last_result(target)
    assert "failed" not in result and "ready on hard-eng/update" in result
    assert private_folders() == []
    assert str(Path(tempfile.gettempdir())) not in git(target, "worktree", "list")


def test_the_check_of_the_update_branch_leaves_no_child_in_its_worktree(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    install_hook(target, "post-checkout", WRITER)
    update_pr.tip_refusal(target)
    assert private_folders() == []


def test_two_session_starts_together_run_one_update_and_print_no_failure(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source, target, _ = release
    add_origin(target)
    select_release(source, monkeypatch)
    revision = update.latest_verified("x")
    assert isinstance(revision, str)
    install_hook(target, "post-commit", WRITER)
    script = tmp_path / "worker.py"
    script.write_text(
        WORKER.format(hooks=str(SOURCE / ".hooks"), revision=revision, me=str(script))
    )

    def command(*options: str) -> list[str]:
        return [sys.executable, str(script), "apply" if options else "supervise"]

    monkeypatch.setattr(update_runner, "update_command", command)
    other = tmp_path / "other"
    git(target, "worktree", "add", "-q", "--detach", str(other))
    roots = [target, other]
    gate = threading.Barrier(2)

    def start(root: Path) -> None:
        gate.wait()
        update_runner.start_update(root)

    threads = [threading.Thread(target=start, args=(root,)) for root in roots]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    deadline = time.monotonic() + 240
    time.sleep(1)
    while any(update_runner.update_running(root) for root in roots):
        assert time.monotonic() < deadline, "the update did not end"
        time.sleep(0.2)
    results = [update_runner.last_result(root) for root in roots]
    assert not any("failed" in result for result in results), results
    assert sum("ready on hard-eng/update" in result for result in results) == 1
    assert git(target, "rev-list", "--count", "origin/main..hard-eng/update") == "1"
    assert private_folders() == []

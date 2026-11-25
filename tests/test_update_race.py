"""The update's private worktree goes away even when a git hook left a child that still writes in it."""

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
import tidy_guards
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


def workers_running(script: Path) -> bool:
    """Some process still runs the worker script: the supervisor, its update or the tidy that follows."""
    listing = subprocess.run(
        ["ps", "-axo", "command="], capture_output=True, text=True, check=True
    ).stdout
    return str(script) in listing


def test_a_stop_signals_a_child_that_a_stopped_process_forked_meanwhile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inside = str(tmp_path / "candidate" / "f")
    scans = iter([[(11, inside)], [(11, inside), (12, inside)], [(12, inside)], []])
    sent: list[tuple[int, int]] = []

    def listing(own: bool = False) -> list[tuple[int, str]]:
        return next(scans, [])

    def kill(pid: int, signum: int) -> None:
        sent.append((pid, signum))

    monkeypatch.setattr(tidy_guards, "open_files", listing)
    monkeypatch.setattr(tidy_guards.os, "kill", kill)
    (tmp_path / "candidate").mkdir()
    tidy_guards.stop_inside(tmp_path / "candidate")
    assert (12, signal.SIGTERM) in sent


def test_a_slow_scan_still_signals_the_processes_that_it_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scans = iter([[(11, str(tmp_path / "f"))], [(11, str(tmp_path / "f"))], []])
    sent: list[tuple[int, int]] = []

    def listing(own: bool = False) -> list[tuple[int, str]]:
        return next(scans, [])

    def kill(pid: int, signum: int) -> None:
        sent.append((pid, signum))

    monkeypatch.setattr(tidy_guards, "open_files", listing)
    monkeypatch.setattr(tidy_guards.os, "kill", kill)
    tidy_guards.stop_inside(tmp_path, seconds=0)
    assert [signum for _, signum in sent] == [signal.SIGTERM, signal.SIGKILL]
    assert next(scans) == []


def test_a_host_that_cannot_list_processes_still_lets_the_removal_go_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(own: bool = False) -> list[tuple[int, str]]:
        raise tidy_guards.TidyStop("`lsof` exited 2")

    monkeypatch.setattr(tidy_guards, "open_files", broken)
    tidy_guards.stop_inside(tmp_path)


def test_a_process_of_another_account_does_not_hide_ours(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proc = tmp_path / "proc"
    for number in ("100", "200"):
        (proc / number).mkdir(parents=True)
        (proc / number / "cwd").symlink_to(f"/work/{number}")
    real = os.readlink

    def readlink(path: str | os.PathLike[str]) -> str:
        if "200" in str(path):
            raise PermissionError(path)
        return real(path)

    def foreign(process: Path) -> bool:
        return process.name == "200"

    def ours(process: Path) -> bool:
        return process.name == "100"

    monkeypatch.setattr(tidy_guards.os, "readlink", readlink)
    monkeypatch.setattr(tidy_guards, "foreign_user", foreign)
    monkeypatch.setattr(tidy_guards, "mine", ours)
    assert tidy_guards.proc_files(proc) is None
    assert tidy_guards.proc_files(proc, own=True) == [(100, "/work/100")]


def test_the_private_worktree_is_unlocked_only_after_its_processes_stop(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    target = pushed_release(release, monkeypatch)
    locked_when_stopped: list[bool] = []

    def stop(path: Path) -> None:
        records = git(target, "worktree", "list", "--porcelain").split("\n\n")
        locked_when_stopped.append(
            any("locked" in record for record in records if "candidate" in record)
        )

    monkeypatch.setattr(tidy_guards, "stop_inside", stop)
    with update_runner.candidate_worktree(target, "HEAD", claim=True):
        pass
    assert locked_when_stopped == [True]


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
    while workers_running(script):
        assert time.monotonic() < deadline, "the update did not end"
        time.sleep(0.2)
    results = [update_runner.last_result(root) for root in roots]
    assert not any("failed" in result for result in results), results
    assert any("ready on hard-eng/update" in result for result in results)
    assert git(target, "rev-list", "--count", "origin/main..hard-eng/update") == "1"
    assert private_folders() == []

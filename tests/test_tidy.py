"""The background run removes merged, idle worktrees and branches and idle cargo build folders."""

import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest
import ship_actions
import stale_updates
import tidy_guards
import update
import update_runner
from conftest import (
    OLD,
    SOURCE,
    age_branch,
    commit,
    git,
    git_path,
    init,
    old_log,
)

CARGO_TAG = "Signature: 8a477f597d28d172789f06886806bc55\n# cache\n"


def age(path: Path) -> None:
    """Make every file of the worktree, its HEAD log and its branch log three days old."""
    for folder, names, files in os.walk(path):
        names[:] = [name for name in names if name != ".git"]
        for name in [*names, *files]:
            if name != ".git":
                os.utime(Path(folder) / name, (OLD, OLD), follow_symlinks=False)
    old_log(git_path(path, "logs/HEAD"))
    branch = git(path, "branch", "--show-current")
    if branch:
        old_log(git_path(path, f"logs/refs/heads/{branch}"))


def age_folders(target: Path) -> None:
    for folder in [target, *(p for p in target.rglob("*") if p.is_dir())]:
        os.utime(folder, (OLD, OLD))


def add_vendor(primary: Path, tmp_path: Path) -> list[str]:
    """Add a submodule at vendor/ and return the Git options that let a local clone work."""
    library = tmp_path / "library"
    init(library)
    (library / "lib.txt").write_text("lib\n")
    (library / ".gitignore").write_text("*.secret\n")
    commit(library, "lib")
    allow = ["-c", "protocol.file.allow=always"]
    git(primary, *allow, "submodule", "add", "-q", str(library), "vendor")
    commit(primary, "add vendor")
    git(primary, "push", "-q", "origin", "main")
    return allow


def linked(primary: Path, name: str, where: str = "sibling") -> Path:
    if where == "claude":
        path = primary / ".claude/worktrees" / name
    else:
        path = primary.parent / f"wt-{name}"
    git(primary, "worktree", "add", "-q", "-b", name, str(path), "main")
    age(path)
    return path


def sparse_worktree(primary: Path) -> Path:
    """A worktree that a sparse checkout left without its lib folder."""
    (primary / "lib").mkdir()
    (primary / "lib/b.txt").write_text("b\n")
    commit(primary, "a folder")
    git(primary, "push", "-q", "origin", "main")
    sparse = linked(primary, "sparse")
    git(sparse, "update-index", "--refresh")
    git(sparse, "sparse-checkout", "set", "--cone")
    assert not (sparse / "lib").exists()
    age(sparse)
    return sparse


def unmerged(path: Path) -> None:
    (path / "own.txt").write_text("own\n")
    commit(path, "own work")
    age(path)


def fake_gh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    answers: Mapping[str, object] | None = None,
) -> Path:
    folder = tmp_path / "fake-gh"
    folder.mkdir()
    (folder / "answers.json").write_text(json.dumps(answers or {}))
    script = folder / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import json, sys\n"
        "here = __file__.rsplit('/', 1)[0]\n"
        "args = sys.argv[1:]\n"
        "open(here + '/calls', 'a').write(' '.join(args) + '\\n')\n"
        "config = json.load(open(here + '/answers.json'))\n"
        "if config.get('fail'):\n"
        "    sys.exit(1)\n"
        "def value(flag):\n"
        "    return args[args.index(flag) + 1] if flag in args else ''\n"
        "state, head, base = value('--state'), value('--head'), value('--base')\n"
        "key = head + '|' + base if state == 'merged' else head\n"
        "print(json.dumps(config.get(state, {}).get(key, [])))\n"
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")
    return folder / "calls"


def update_as(*words: str) -> Callable[..., list[str]]:
    def command(*options: str) -> list[str]:
        return list(words)

    return command


def tidy_running(root: Path) -> bool:
    import fcntl

    with (stale_updates.common_dir(root) / "hard-eng-tidy.lock").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
    return False


def tidy(root: Path) -> None:
    stale_updates.tidy(root)


def branches(root: Path) -> set[str]:
    return set(
        git(root, "for-each-ref", "--format=%(refname:short)", "refs/heads").split()
    )


@contextmanager
def process_inside(
    path: Path, how: str, tmp_path: Path, via_link: bool
) -> Generator[subprocess.Popen[str]]:
    place = path
    if via_link:
        place = tmp_path / "link"
        place.symlink_to(path, target_is_directory=True)
    if how == "cwd":
        command, folder = ["sleep", "60"], place
    else:
        command = [
            sys.executable,
            "-c",
            "import sys, time; f = open(sys.argv[1]); print('ready', flush=True); time.sleep(60)",
            str(place / "tracked.txt"),
        ]
        folder = tmp_path
    child = subprocess.Popen(command, cwd=folder, stdout=subprocess.PIPE, text=True)
    if child.stdout is not None and how != "cwd":
        assert child.stdout.readline().strip() == "ready"
    try:
        yield child
    finally:
        child.kill()
        child.wait()


def retire_after_merge(primary: Path, work: Path, name: str) -> None:
    """Remove the worktree of a branch that the base took, age what remains, and run the tidy from a new session."""
    git(primary, "push", "-q", "origin", "main")
    git(primary, "worktree", "remove", "--force", str(work))
    age_branch(primary, name)
    age(primary)
    tidy(linked(primary, "session"))


def squash_merged_steps(primary: Path, name: str, steps: int) -> str:
    work = linked(primary, name)
    for number in range(steps):
        (work / f"f{number}.txt").write_text("x\n")
        commit(work, f"step {number}")
    tip = git(work, "rev-parse", "HEAD")
    git(primary, "merge", "-q", "--squash", name)
    git(primary, "commit", "-qm", f"squash of {name}")
    retire_after_merge(primary, work, name)
    return tip


def merged_branch(root: Path, name: str) -> str:
    git(root, "branch", name, "main")
    age_branch(root, name)
    return git(root, "rev-parse", name)


def test_tidy_removes_a_merged_idle_branch(
    primary: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tip = merged_branch(primary, "done")
    current = linked(primary, "current")
    tidy(current)
    assert f"removed branch done at {tip}" in capsys.readouterr().err
    assert primary.is_dir() and current.is_dir()
    assert branches(primary) == {"main", "current"}


def test_tidy_keeps_the_primary_checkout(primary: Path) -> None:
    git(primary, "switch", "-qc", "parking")
    age(primary)
    merged_branch(primary, "gone")
    tidy(linked(primary, "current"))
    assert "gone" not in branches(primary)
    assert primary.is_dir()
    assert "parking" in branches(primary)


def test_tidy_keeps_the_current_worktree(primary: Path) -> None:
    current = linked(primary, "current")
    tidy(current)
    assert current.is_dir()
    assert "current" in branches(primary)


def test_tidy_keeps_an_unmerged_branch(primary: Path) -> None:
    kept = linked(primary, "kept")
    unmerged(kept)
    solo = linked(primary, "solo")
    unmerged(solo)
    git(primary, "worktree", "remove", "--force", str(solo))
    tidy(primary)
    assert kept.is_dir()
    assert {"kept", "solo"} <= branches(primary)


def test_tidy_deletes_rebase_and_squash_merged_branches(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(primary, "switch", "-qc", "rebased")
    (primary / "r.txt").write_text("r\n")
    commit(primary, "r")
    git(primary, "switch", "-qc", "squashed", "main")
    for name in ("s1.txt", "s2.txt"):
        (primary / name).write_text("s\n")
        commit(primary, name)
    head = git(primary, "rev-parse", "squashed")
    git(primary, "switch", "-q", "main")
    git(primary, "cherry-pick", "rebased")
    git(primary, "merge", "--squash", "squashed")
    git(primary, "commit", "-qm", "squash")
    (primary / "s1.txt").write_text("later edit on the base\n")
    commit(primary, "later edit")
    git(primary, "push", "-q", "origin", "main")
    git(primary, "switch", "-qc", "parking")
    for name in ("rebased", "squashed", "parking"):
        age_branch(primary, name)
    age(primary)
    answers = {"merged": {"squashed|main": [{"headRefOid": head}]}}
    calls = fake_gh(tmp_path, monkeypatch, answers)
    session = linked(primary, "session")
    tidy(session)
    assert not {"rebased", "squashed"} & branches(primary)
    assert "--base main" in calls.read_text()


def test_tidy_keeps_branches_that_only_look_merged(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(primary, "switch", "-qc", "side")
    (primary / "s.txt").write_text("s\n")
    commit(primary, "side")
    git(primary, "switch", "-q", "main")
    git(primary, "cherry-pick", "side")
    git(primary, "switch", "-qc", "lookalike", "main")
    git(primary, "merge", "--no-ff", "--no-commit", "side")
    (primary / "m.txt").write_text("own edit in the merge\n")
    commit(primary, "merge with an edit")
    git(primary, "switch", "-qc", "elsewhere", "main")
    (primary / "e.txt").write_text("e\n")
    commit(primary, "e")
    head = git(primary, "rev-parse", "elsewhere")
    git(primary, "switch", "-qc", "parking", "main")
    for name in ("side", "lookalike", "elsewhere", "parking"):
        age_branch(primary, name)
    age(primary)
    fake_gh(
        tmp_path, monkeypatch, {"merged": {"elsewhere|release": [{"headRefOid": head}]}}
    )
    session = linked(primary, "session")
    tidy(session)
    assert {"lookalike", "elsewhere"} <= branches(primary)


def test_tidy_keeps_a_branch_with_an_open_pr_or_no_pr_answer(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("with-pr", "no-pr", "unpushed"):
        git(primary, "branch", name, "main")
        age_branch(primary, name)
    git(primary, "push", "-q", "origin", "with-pr", "no-pr")
    calls = fake_gh(tmp_path, monkeypatch, {"open": {"with-pr": [{"number": 7}]}})
    session = linked(primary, "session")
    tidy(session)
    assert {"with-pr"} <= branches(primary)
    assert not {"no-pr", "unpushed"} & branches(primary)
    lines = calls.read_text().splitlines()
    assert any("--head with-pr" in line and "--state open" in line for line in lines)
    assert not any("unpushed" in line for line in lines)
    (tmp_path / "fake-gh/answers.json").write_text(json.dumps({"fail": True}))
    git(primary, "branch", "silent", "main")
    git(primary, "push", "-q", "origin", "silent")
    age_branch(primary, "silent")
    tidy(session)
    assert "silent" in branches(primary)


def stand_in_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, test: str, action: str = "exit 1"
) -> None:
    """A git that runs the action when the shell test holds, such as `[ "$1" = for-each-ref ]`."""
    folder = tmp_path / "stand-in"
    folder.mkdir()
    script = folder / "git"
    script.write_text(
        f'#!/bin/sh\nif {test}; then echo "injected failure" >&2; {action}; fi\n'
        f'exec {shutil.which("git")} "$@"\n'
    )
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{folder}{os.pathsep}{os.environ['PATH']}")


def quick_git_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    real = tidy_guards.tidy_run

    def quick_git(
        cwd: Path,
        limit: float,
        *command: str,
        env: dict[str, str] | None = None,
        lines: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return real(
            cwd, 2 if command[0] == "git" else limit, *command, env=env, lines=lines
        )

    monkeypatch.setattr(tidy_guards, "tidy_run", quick_git)
    monkeypatch.setattr(stale_updates, "tidy_run", quick_git)


@pytest.mark.parametrize("hangs", [False, True], ids=["fails", "hangs"])
def test_tidy_keeps_the_item_whose_command_fails_or_hangs_and_goes_on(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    hangs: bool,
) -> None:
    merged_branch(primary, "aaa-bad")
    merged_branch(primary, "zzz-good")
    if hangs:
        quick_git_limits(monkeypatch)
        stand_in_git(
            tmp_path,
            monkeypatch,
            '[ "$1" = "log" ] && echo "$@" | grep -q aaa-bad',
            "sleep 30",
        )
    else:
        stand_in_git(
            tmp_path,
            monkeypatch,
            '[ "$1 $2" = "update-ref -d" ] && echo "$@" | grep -q aaa-bad',
        )
    tidy(primary)
    err = capsys.readouterr().err
    assert "aaa-bad" in branches(primary) and "zzz-good" not in branches(primary)
    assert "kept branch" in err and "aaa-bad" in err and "stopped" not in err


def test_tidy_stops_the_repository_when_a_repository_level_command_fails(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    idle = linked(primary, "idle")
    unmerged(idle)
    target = make_target(idle)
    age(primary)
    git(primary, "branch", "extra", "main")
    age_branch(primary, "extra")
    path = os.environ["PATH"]
    stand_in_git(tmp_path, monkeypatch, '[ "$1" = "for-each-ref" ]')
    tidy(primary)
    monkeypatch.setenv("PATH", path)
    assert "extra" in branches(primary)
    assert target.is_dir()
    assert "stopped for this repository" in capsys.readouterr().err


def installed(primary: Path) -> Path:
    marker = primary / update.SOURCE_FILE
    marker.parent.mkdir(exist_ok=True)
    marker.write_text(json.dumps({"revision": "a" * 40}))
    commit(primary, "installed")
    git(primary, "push", "-q", "origin", "main")
    age(primary)
    return primary


def stop_when_ready() -> None:
    """Send SIGTERM to this process once the update run has installed its handler."""
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if signal.getsignal(signal.SIGTERM) is update_runner.interrupt_update:
            time.sleep(0.5)
            os.kill(os.getpid(), signal.SIGTERM)
            return
        time.sleep(0.05)


def test_tidy_uses_its_own_lock_and_skips_after_an_interrupt(
    primary: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import fcntl

    root = installed(primary)
    merged_branch(root, "gone")
    with (stale_updates.common_dir(root) / "hard-eng-tidy.lock").open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        tidy(root)
    assert "gone" in branches(root)

    monkeypatch.setattr(update_runner, "update_command", update_as("sleep", "60"))
    previous = signal.getsignal(signal.SIGTERM)
    stopper = threading.Thread(target=stop_when_ready, daemon=True)
    stopper.start()
    try:
        update_runner.run_update(root)
    finally:
        signal.signal(signal.SIGTERM, previous)
        stopper.join(timeout=60)
    assert "gone" in branches(root)
    assert not update_runner.update_running(root)

    seen: list[bool] = []
    real = stale_updates.tidy

    def watching(checkout: Path) -> None:
        seen.append(update_runner.update_running(checkout))
        real(checkout)

    monkeypatch.setattr(stale_updates, "tidy", watching)
    monkeypatch.setattr(update_runner, "update_command", update_as("true"))
    try:
        update_runner.run_update(root)
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert seen == [False]
    assert "gone" not in branches(root)


def test_tidy_reads_real_worktree_record_shapes(primary: Path, tmp_path: Path) -> None:
    locked = linked(primary, "locked")
    git(primary, "worktree", "lock", "--reason", "in use", str(locked))
    detached = tmp_path / "detached"
    git(primary, "worktree", "add", "-q", "--detach", str(detached), "main")
    vanished = linked(primary, "vanished")
    shutil.rmtree(vanished)
    records = {Path(r["worktree"]).name: r for r in ship_actions.worktrees(primary)}
    assert "branch" in records["repository"] and "locked" not in records["repository"]
    assert records[locked.name]["locked"] == "in use"
    assert "detached" in records["detached"] and "branch" not in records["detached"]
    assert "prunable" in records[vanished.name]
    bare = tmp_path / "bare.git"
    git(primary, "clone", "-q", "--bare", str(primary), str(bare))
    assert "bare" in ship_actions.worktrees(bare)[0]
    with process_inside(detached, "cwd", tmp_path, False) as child:
        names = tidy_guards.open_paths()
        assert names is not None
        assert str(detached.resolve()) in names
        assert tidy_guards.inside(detached, names)
        assert child.pid > 0


def test_tidy_keeps_protected_branches(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(primary, "branch", "stable", "main")
    git(primary, "push", "-q", "origin", "stable")
    git(
        primary,
        "symbolic-ref",
        "refs/remotes/origin/HEAD",
        "refs/remotes/origin/stable",
    )
    for name in ("master", "develop", "hard-eng/update", "plain"):
        git(primary, "branch", name, "main")
    git(primary, "switch", "-qc", "parking")
    for name in ("master", "develop", "hard-eng/update", "plain", "stable", "parking"):
        age_branch(primary, name)
    age(primary)
    fake_gh(tmp_path, monkeypatch, {"open": {}})
    session = linked(primary, "session")
    tidy(session)
    assert {"main", "master", "develop", "hard-eng/update", "stable"} <= branches(
        primary
    )
    assert "plain" not in branches(primary)


def test_tidy_touches_only_its_own_repository(primary: Path, tmp_path: Path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    init(other / "repo")
    git(other / "repo", "commit", "--allow-empty", "-qm", "base")
    git(other / "repo", "branch", "-M", "main")
    git(
        other / "repo",
        "worktree",
        "add",
        "-q",
        "-b",
        "idle",
        str(other / "idle"),
        "main",
    )
    age(other / "idle")
    merged_branch(primary, "mine")
    tidy(primary)
    assert "mine" not in branches(primary)
    assert (other / "idle").is_dir()
    assert "idle" in branches(other / "repo")


def make_target(path: Path, tagged: bool = True) -> Path:
    target = path / "target"
    (target / "debug/deps").mkdir(parents=True)
    (target / "debug/deps/a.rlib").write_text("x\n")
    if tagged:
        (target / "CACHEDIR.TAG").write_text(CARGO_TAG)
    age_folders(target)
    return target


def test_tidy_removes_idle_cargo_build_folders_only(
    primary: Path, tmp_path: Path
) -> None:
    session = linked(primary, "session")
    unmerged(session)
    idle = linked(primary, "idle")
    unmerged(idle)
    busy = linked(primary, "busy")
    unmerged(busy)
    untagged = linked(primary, "untagged")
    unmerged(untagged)
    recent = linked(primary, "recent")
    unmerged(recent)
    age(primary)
    targets = {
        name: make_target(path, name != "untagged")
        for name, path in {
            "session": session,
            "idle": idle,
            "busy": busy,
            "untagged": untagged,
            "recent": recent,
            "primary": primary,
        }.items()
    }
    os.utime(targets["recent"] / "debug", None)
    with process_inside(busy, "cwd", tmp_path, False):
        tidy(session)
    assert not targets["idle"].exists()
    assert not targets["primary"].exists()
    for name in ("session", "busy", "untagged", "recent"):
        assert targets[name].is_dir(), name


def test_tidy_reports_one_line_only_when_it_removed_something(primary: Path) -> None:
    root = installed(primary)
    result = root / update_runner.RESULT_FILE
    update_runner.record_result(root, "Updated Hard Eng")
    tidy(root)
    assert result.read_text().count("\n") == 1
    merged_branch(root, "gone")
    tidy(root)
    lines = result.read_text().splitlines()
    assert lines[1] == (
        f"Tidy: removed 1 branches, 0 build folders ({update_runner.LOG_FILE})."
    )
    assert len(lines) == 2
    assert update_runner.freshness_note(root) == ""


def test_tidy_runs_after_a_failed_update_and_stops_on_a_failed_fetch(
    primary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = installed(primary)
    merged_branch(root, "first")
    monkeypatch.setattr(update_runner, "update_command", update_as("false"))
    previous = signal.getsignal(signal.SIGTERM)
    try:
        assert update_runner.run_update(root) == 1
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert "first" not in branches(root)
    merged_branch(root, "second")
    git(root, "config", "--unset", f"url.{tmp_path / 'origin.git'}.insteadOf")
    git(root, "remote", "set-url", "origin", str(tmp_path / "missing.git"))
    capsys.readouterr()
    tidy(root)
    assert "second" in branches(root)
    assert "fetch of the base branch failed" in capsys.readouterr().err


def test_session_start_tidies_in_the_background_and_reports_at_the_next_start(
    primary: Path,
) -> None:
    shutil.copytree(
        SOURCE / ".hooks",
        primary / ".hooks",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    root = installed(primary)
    merged_branch(root, "gone")
    payload = json.dumps({"session_id": "journey"})

    def start() -> str:
        started = subprocess.run(
            [sys.executable, ".hooks/hard-eng.py", "session", "claude"],
            cwd=root,
            input=payload,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert started.returncode == 0, started.stderr
        return started.stdout

    first = start()
    assert "started in the background" in first
    deadline = time.monotonic() + 120
    while "Tidy:" not in update_runner.last_result(root):
        assert time.monotonic() < deadline, "the background run did not finish"
        time.sleep(0.2)
    assert "gone" not in branches(root)
    assert "Tidy: removed 1 branches" in start()
    while update_runner.update_running(root) or tidy_running(root):
        assert time.monotonic() < deadline, "the second background run did not finish"
        time.sleep(0.2)


def test_session_start_loads_no_tidy_module(primary: Path) -> None:
    program = (
        "import sys\n"
        f"sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
        "import agent_hooks, update_runner\n"
        "update_runner.start_update = lambda root: 'started'\n"
        "from pathlib import Path\n"
        "agent_hooks.handle_event(Path.cwd(), 'session', 'claude')\n"
        "print(sorted({'stale_updates', 'ship_actions'} & set(sys.modules)))\n"
    )
    ran = subprocess.run(
        [sys.executable, "-c", program],
        cwd=primary,
        input=json.dumps({"session_id": "guard"}),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert ran.stdout.rstrip().endswith("[]"), ran.stdout + ran.stderr


def test_tidy_keeps_a_branch_that_a_worktree_checks_out_during_the_checks(
    primary: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    git(primary, "branch", "late", "main")
    git(primary, "branch", "plain", "main")
    age_branch(primary, "late")
    age_branch(primary, "plain")
    session = linked(primary, "session")
    late = tmp_path / "wt-late"
    real = stale_updates.Tidy.branch_reason

    def checking_out(
        self: stale_updates.Tidy, name: str, tip: str, checked_out: set[str]
    ) -> str | None:
        reason = real(self, name, tip, checked_out)
        if name == "late" and reason is None:
            git(primary, "worktree", "add", "-q", str(late), "late")
        return reason

    monkeypatch.setattr(stale_updates.Tidy, "branch_reason", checking_out)
    tidy(session)
    assert late.is_dir()
    assert "late" in branches(primary)
    assert "plain" not in branches(primary)


@pytest.mark.parametrize("foreign", [True, False], ids=["other-person", "system"])
def test_an_unreadable_process_counts_as_unknown_only_for_another_person(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, foreign: bool
) -> None:
    proc = tmp_path / "proc"
    for number in ("100", "200"):
        (proc / number / "fd").mkdir(parents=True)
        (proc / number / "cwd").symlink_to(f"/work/{number}")
    real = os.readlink

    def readlink(path: str | os.PathLike[str]) -> str:
        if "200" in str(path):
            raise PermissionError(path)
        return real(path)

    monkeypatch.setattr(tidy_guards.os, "readlink", readlink)

    def other_person(process: Path) -> bool:
        return foreign

    monkeypatch.setattr(tidy_guards, "foreign_user", other_person)
    found = tidy_guards.proc_paths(proc)
    assert found == (None if foreign else {"/work/100"})

"""Prove the push check reads the policy of the pushed commit and reuses a passed full check."""

import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable
from contextlib import nullcontext
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
import ship_actions
from conftest import commit, configure, default_policy, gate, git, init
from shipping import ShippingError, ShippingPolicy


def write_policy(root: Path, **changes: object) -> None:
    policy = default_policy() | changes
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shipping": policy})
    )


def project(tmp_path: Path, **changes: object) -> Path:
    root = tmp_path / "project"
    init(root)
    git(root, "branch", "-M", "main")
    (root / ".hooks").mkdir()
    (root / ".hooks/hard-eng.py").write_text("")
    write_policy(root, **changes)
    commit(root, "start")
    return root


def push_input(monkeypatch: pytest.MonkeyPatch, *lines: str) -> None:
    monkeypatch.setattr("sys.stdin", StringIO("".join(f"{line}\n" for line in lines)))


def new_branch_line(branch: str, revision: str) -> str:
    return f"refs/heads/{branch} {revision} refs/heads/{branch} {'0' * 40}"


def update_line(branch: str, revision: str, old: str) -> str:
    return f"refs/heads/{branch} {revision} refs/heads/{branch} {old}"


def stub_snapshot(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, status: int = 0
) -> Mock:
    checkout = tmp_path / "snapshot"
    init(checkout)
    (checkout / ".hooks").mkdir()
    (checkout / ".hooks/hard-eng.py").write_text("")

    def snapshot(*_args: object) -> nullcontext[Path]:
        return nullcontext(checkout)

    monkeypatch.setattr(ship_actions, "snapshot", snapshot)
    hard_eng = Mock(return_value=status)
    monkeypatch.setattr(ship_actions, "run_hard_eng", hard_eng)
    return hard_eng


def no_snapshot(monkeypatch: pytest.MonkeyPatch) -> Mock:
    started = Mock(side_effect=AssertionError("no snapshot may start"))
    monkeypatch.setattr(ship_actions, "snapshot", started)
    monkeypatch.setattr(ship_actions, "run_hard_eng", started)
    return started


@pytest.mark.parametrize("row", ["dirty-checkout", "other-branch"])
def test_a_direct_push_to_the_base_named_by_the_pushed_commit_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: str
) -> None:
    root = project(tmp_path)
    if row == "dirty-checkout":
        write_policy(root, base="trunk")
        revision = commit(root, "name another base")
        write_policy(root, base="main")
    else:
        git(root, "switch", "-qc", "other")
        write_policy(root, base="trunk")
        revision = commit(root, "name another base")
        git(root, "switch", "-q", "main")
    started = no_snapshot(monkeypatch)
    push_input(monkeypatch, update_line("trunk", revision, "1" * 40))
    with pytest.raises(ValueError, match="use a PR"):
        ship_actions.pre_push(root)
    started.assert_not_called()


def test_the_mutation_budget_comes_from_the_pushed_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    parent = git(root, "rev-parse", "HEAD").strip()
    git(root, "switch", "-qc", "task")
    write_policy(root, pre_push_mutation_seconds=0.0)
    revision = commit(root, "turn the mutation budget off")
    git(root, "switch", "-q", "main")
    hard_eng = stub_snapshot(monkeypatch, tmp_path)
    push_input(monkeypatch, update_line("task", revision, parent))
    assert ship_actions.pre_push(root) == 0
    assert [call.args[1][0] for call in hard_eng.call_args_list] == ["check"]


def narrow_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    script: str,
    module: str | None,
) -> list[str]:
    root = project(tmp_path)
    parent = git(root, "rev-parse", "HEAD").strip()
    (root / "change.txt").write_text("change")
    revision = commit(root, "change")
    hard_eng = stub_snapshot(monkeypatch, tmp_path)
    hooks = tmp_path / "snapshot/.hooks"
    (hooks / "hard-eng.py").write_text(script)
    if module is not None:
        (hooks / "gate_runner.py").write_text(module)
    push_input(monkeypatch, update_line("task", revision, parent))
    assert ship_actions.pre_push(root) == 0
    return hard_eng.call_args_list[0].args[1][3:]


def test_a_pushed_revision_with_the_runner_module_gets_the_narrow_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    options = narrow_options(
        tmp_path, monkeypatch, "", "--without-dependents --related-tests"
    )
    assert options == ["--without-dependents", "--related-tests"]


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        (
            "--without-dependents --related-tests",
            ["--without-dependents", "--related-tests"],
        ),
        ("--without-dependents", ["--without-dependents"]),
        ("", []),
    ],
)
def test_an_older_pushed_revision_keeps_its_own_options(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, script: str, expected: list[str]
) -> None:
    assert narrow_options(tmp_path, monkeypatch, script, None) == expected


@pytest.mark.parametrize("row", ["no-block", "no-file", "invalid-json"])
def test_a_pushed_commit_without_a_shipping_policy_is_refused_with_the_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, row: str
) -> None:
    root = project(tmp_path)
    git(root, "switch", "-qc", "task")
    gates = root / "hard-eng.gates.json"
    if row == "no-file":
        gates.unlink()
        (root / "other.txt").write_text("x")
    else:
        gates.write_text('{"packages": []}' if row == "no-block" else "{")
    revision = commit(root, "commit without a policy")
    write_policy(root)
    started = no_snapshot(monkeypatch)
    push_input(monkeypatch, new_branch_line("task", revision))
    with pytest.raises(
        ShippingError, match=rf"Pushed commit {revision[:12]} has"
    ) as refused:
        ship_actions.pre_push(root)
    assert "commit it and push again" in str(refused.value)
    started.assert_not_called()


def test_a_pushed_commit_with_a_policy_passes_from_a_checkout_without_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    parent = git(root, "rev-parse", "HEAD").strip()
    (root / "change.txt").write_text("change")
    revision = commit(root, "change")
    git(root, "switch", "-q", "--detach", parent)
    (root / "hard-eng.gates.json").unlink()
    hard_eng = stub_snapshot(monkeypatch, tmp_path)
    push_input(monkeypatch, update_line("task", revision, parent))
    assert ship_actions.pre_push(root) == 0
    assert hard_eng.call_args_list[0].args[1][0] == "check"


def test_a_direct_base_push_is_refused_before_any_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = project(tmp_path)
    revision = git(root, "rev-parse", "HEAD").strip()
    started = no_snapshot(monkeypatch)
    push_input(monkeypatch, update_line("main", revision, "2" * 40))
    with pytest.raises(ValueError, match="use a PR"):
        ship_actions.pre_push(root)
    started.assert_not_called()


GATE_CODE = (
    "import os, pathlib, sys\n"
    "pathlib.Path({counter!r}).open('a').write('x')\n"
    "if os.environ.get('PASS_FAILS'):\n"
    "    sys.exit(1)\n"
    "if os.environ.get('PASS_LEAKS'):\n"
    "    pathlib.Path('leak.txt').write_text('x')\n"
)


class Pushed:
    def __init__(
        self,
        runner: ModuleType,
        tmp_path: Path,
        policy: ShippingPolicy,
        extra: list[dict[str, object]] | None = None,
    ) -> None:
        self.extra = extra or []
        self.root = tmp_path
        self.counter = tmp_path.parent / f"{tmp_path.name}-counter"
        self.bare = tmp_path.parent / f"{tmp_path.name}-origin.git"
        self.policy = policy
        git(self.root, "init", "--bare", "-q", str(self.bare))
        git(self.root, "config", "user.name", "Pass Fixture")
        git(self.root, "config", "user.email", "pass@example.invalid")
        git(self.root, "branch", "-M", "main")
        hooks = self.root / ".hooks"
        hooks.mkdir()
        for source in (Path(__file__).resolve().parents[1] / ".hooks").glob("*.py"):
            (hooks / source.name).write_bytes(source.read_bytes())
        (self.root / ".gitignore").write_text("__pycache__/\ninstalled.flag\n")
        self.write_config()
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", "initial base")
        self.base = git(self.root, "rev-parse", "HEAD").strip()
        git(self.root, "remote", "add", "origin", str(self.bare))
        git(self.root, "push", "-q", "origin", "main")
        git(self.root, "switch", "-qc", "feature/pass")

    def write_config(self, **changes: object) -> None:
        config: dict[str, object] = {
            "packages": [],
            "shipping": self.policy,
            "shared": [
                {
                    "name": "counted-check",
                    "command": [
                        sys.executable,
                        "-c",
                        GATE_CODE.format(counter=str(self.counter)),
                    ],
                },
                *self.extra,
            ],
        } | changes
        (self.root / "hard-eng.gates.json").write_text(json.dumps(config))

    def task(self, text: str = "committed") -> str:
        plan = self.root / "PLAN.md"
        plan.write_text(plan.read_text() + f"\nTask change {text}.\n")
        (self.root / "task.txt").write_text(text)
        git(self.root, "add", ".")
        git(self.root, "commit", "-qm", f"task {text}")
        return git(self.root, "rev-parse", "HEAD").strip()

    def check(
        self,
        *arguments: str,
        base: str | None = None,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> int:
        base = self.base if base is None else base
        command = [sys.executable, ".hooks/hard-eng.py", "check", *arguments]
        if base:
            command += ["--base", base]
        return subprocess.run(
            command, cwd=cwd or self.root, env=os.environ | (env or {}), check=False
        ).returncode

    def add_submodule(self, tmp_path: Path) -> Path:
        library = tmp_path.parent / f"{tmp_path.name}-library"
        init(library)
        (library / "lib.txt").write_text("library")
        commit(library, "library")
        git(
            self.root,
            *("-c", "protocol.file.allow=always"),
            *("submodule", "add", "-q", library.as_uri(), "component"),
        )
        return self.root / "component"

    def runs(self) -> int:
        return len(self.counter.read_text()) if self.counter.exists() else 0

    def record(self) -> Path:
        return self.root / ".git/hard-eng-passed"

    def push(
        self, monkeypatch: pytest.MonkeyPatch, revision: str, old: str | None = None
    ) -> int:
        line = update_line("feature/pass", revision, old or "0" * 40)
        push_input(monkeypatch, line)
        return ship_actions.pre_push(self.root)


@pytest.fixture
def pushed(
    runner: ModuleType,
    tmp_path: Path,
    shipping_policy: ShippingPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> Pushed:
    monkeypatch.delenv("CI", raising=False)
    shipping_policy["pre_push_mutation_seconds"] = 0.0
    return Pushed(runner, tmp_path, shipping_policy)


def test_a_full_check_that_passed_on_the_pushed_commit_spares_the_push_check(
    pushed: Pushed,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    revision = pushed.task()
    assert pushed.check() == 0
    assert pushed.runs() == 1
    capsys.readouterr()
    assert pushed.push(monkeypatch, revision) == 0
    output = capsys.readouterr().out
    assert pushed.runs() == 1
    assert re.search(
        r"Hard Eng: the full check passed on this exact commit and base \d+ min ago; "
        r"not repeating it\.\n",
        output,
    )
    assert len(ship_actions.worktrees(pushed.root)) == 1


MISSES = [
    "tracked-edit",
    "untracked-file",
    "untracked-hidden",
    "gate-leaves-file",
    "submodule-moved",
    "submodule-edited",
    "amended",
    "later-push",
    "no-base",
    "quick",
    "only-language",
    "stage-ready",
    "old-record",
    "future-record",
    "unreadable-record",
]


def rewrite_record(pushed: Pushed, row: str) -> None:
    saved = json.loads(pushed.record().read_text())
    if row == "old-record":
        saved["time"] = time.time() - 1860
    elif row == "future-record":
        saved["time"] = time.time() + 3600
    else:
        pushed.record().write_text("{")
        return
    pushed.record().write_text(json.dumps(saved))


@pytest.mark.parametrize("row", MISSES)
def test_the_push_check_runs_when_the_pass_does_not_cover_the_pushed_commit(
    pushed: Pushed, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, row: str
) -> None:
    component = pushed.add_submodule(tmp_path) if row.startswith("submodule") else None
    revision, old = pushed.task(), None
    env: dict[str, str] = {}
    if row == "later-push":
        git(pushed.root, "push", "-q", "origin", "feature/pass")
        old, revision = revision, pushed.task("second")
    if row == "tracked-edit":
        (pushed.root / "task.txt").write_text("edited after the commit")
    if row == "untracked-hidden":
        git(pushed.root, "config", "status.showUntrackedFiles", "no")
    if row in {"untracked-file", "untracked-hidden"}:
        (pushed.root / "scratch.txt").write_text("scratch")
    if row == "submodule-moved":
        assert component
        git(component, "config", "user.name", "Pass Fixture")
        git(component, "config", "user.email", "pass@example.invalid")
        (component / "next.txt").write_text("next")
        commit(component, "move the submodule")
    if row == "submodule-edited":
        assert component
        (component / "lib.txt").write_text("edited")
    if row == "gate-leaves-file":
        env = {"PASS_LEAKS": "1"}
    arguments = {
        "quick": ["--quick"],
        "only-language": ["--only-language", "python"],
        "stage-ready": ["--plan-stage", "Ready"],
    }.get(row, [])
    base = "" if row == "no-base" else pushed.base
    assert pushed.check(*arguments, base=base, env=env) == 0
    before = pushed.runs()
    covers = row in {"amended", "later-push"} or row.endswith("-record")
    assert pushed.record().is_file() is covers
    if row.endswith("-record"):
        rewrite_record(pushed, row)
    if row == "amended":
        git(pushed.root, "commit", "--amend", "-qm", "task amended")
        revision = git(pushed.root, "rev-parse", "HEAD").strip()
    assert pushed.push(monkeypatch, revision, old) == 0
    assert pushed.runs() == before + 1


def test_a_failed_full_check_removes_the_earlier_pass(
    pushed: Pushed, monkeypatch: pytest.MonkeyPatch
) -> None:
    revision = pushed.task()
    assert pushed.check() == 0
    assert pushed.record().is_file()
    assert pushed.check(env={"PASS_FAILS": "1"}) == 1
    assert not pushed.record().exists()
    before = pushed.runs()
    assert pushed.push(monkeypatch, revision) == 0
    assert pushed.runs() == before + 1


def test_a_push_from_a_linked_worktree_uses_only_that_worktree_pass(
    pushed: Pushed, tmp_path: Path
) -> None:
    revision = pushed.task()
    hook = pushed.root / ".git/hooks/pre-push"
    hook.write_text(f"#!/bin/sh\nexec {sys.executable} .hooks/hard-eng.py pre-push\n")
    hook.chmod(0o755)
    linked = tmp_path.parent / f"{tmp_path.name}-linked"
    git(pushed.root, "worktree", "add", "-q", "--detach", str(linked), revision)
    assert pushed.check() == 0
    assert pushed.record().is_file()
    git(linked, "push", "-q", "origin", "HEAD:refs/heads/feature/one")
    assert pushed.runs() == 2
    assert pushed.check(cwd=linked) == 0
    git(linked, "push", "-q", "origin", "HEAD:refs/heads/feature/two")
    assert pushed.runs() == 3


STARTED: list[list[str]] = []
COUNTING: list[bool] = []


def record_start(event: str, arguments: tuple[object, ...]) -> None:
    if COUNTING and event == "subprocess.Popen":
        command = arguments[1]
        assert isinstance(command, list)
        if Path(str(arguments[0])).name == "git":
            STARTED.append([str(part) for part in command])


sys.addaudithook(record_start)


def git_starts(run: Callable[[], int]) -> list[list[str]]:
    STARTED.clear()
    COUNTING.append(True)
    try:
        assert run() == 0
    finally:
        COUNTING.clear()
    return list(STARTED)


def test_the_quick_check_starts_no_git_for_the_pass_record(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CI", raising=False)
    configure(tmp_path, [gate("suite", "pass")])
    (tmp_path / ".gitignore").write_text("__pycache__/\n")
    git(tmp_path, "config", "user.name", "Pass Fixture")
    git(tmp_path, "config", "user.email", "pass@example.invalid")
    base = commit(tmp_path, "start")
    resolve = ["rev-parse", "--verify", "-q", f"{base}^{{commit}}"]
    old = tmp_path / ".git/hard-eng-passed"

    def starts(kept: bool = True, **options: bool) -> tuple[int, int]:
        old.write_text("{}")
        found = git_starts(lambda: runner.check(base=base, **options))
        assert (old.read_text() == "{}") is kept
        return (
            len([c for c in found if "--porcelain=v2" in c]),
            [c[1:] for c in found].count(resolve),
        )

    quick = starts(quick=True)
    assert quick[0] == 0
    assert starts(dependents=False) == quick
    assert starts(related_tests=True) == quick
    monkeypatch.setenv("CI", "true")
    assert starts() == quick
    monkeypatch.delenv("CI")
    statuses, resolves = starts(kept=False)
    assert statuses == 2
    assert resolves - quick[1] == 1


def test_after_a_spared_check_the_mutation_report_runs_on_installed_dependencies(
    runner: ModuleType,
    tmp_path: Path,
    shipping_policy: ShippingPolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install: dict[str, object] = {
        "name": "install",
        "role": "lockfiles",
        "command": [sys.executable, "-c", "open('installed.flag', 'w').write('x')"],
    }
    monkeypatch.delenv("CI", raising=False)
    pushed = Pushed(runner, tmp_path, shipping_policy, [install])
    revision = pushed.task()
    assert pushed.check() == 0
    assert pushed.record().is_file()
    calls: list[list[str]] = []
    installed: list[bool] = []
    run_check = ship_actions.run_hard_eng

    def run(checkout: Path, arguments: list[str], environment: dict[str, str]) -> int:
        calls.append(arguments)
        if arguments[0] == "check":
            return run_check(checkout, arguments, environment)
        installed.append((checkout / "installed.flag").is_file())
        return 0

    monkeypatch.setattr(ship_actions, "run_hard_eng", run)
    runs = pushed.runs()
    assert pushed.push(monkeypatch, revision) == 0
    assert calls[0] == ["check", "--base", pushed.base, "--quick"]
    assert [call[0] for call in calls] == ["check", "mutation"]
    assert installed == [True]
    assert pushed.runs() == runs

"""A Stop must not repeat a full check that passed on the same commit, base and clean tree."""

import fcntl
import json
import time
from pathlib import Path
from types import ModuleType

import agent_hooks
import plans
import pytest
from conftest import add_origin, commit, git
from gate_config import JsonObject
from shipping import ShippingPolicy
from test_push_check import git_starts, prepared
from test_stop_checks import install_check

EARLIER = "Hard Eng: the full check passed on this exact commit from an earlier base 3 min ago; not repeating it."
SENTENCE = "Hard Eng: the full check passed on this exact commit and base 3 min ago; not repeating it."


def committed_task(repository: Path) -> tuple[Path, JsonObject, str, str]:
    """A session that began at the branch point of a task branch with one commit that is not pushed."""
    runs = install_check(repository, "raise SystemExit(0)\n")
    add_origin(repository)
    git(repository, "push", "-q", "origin", "main")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    base = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-qb", "task")
    (repository / "work.py").write_text("value = 1\n")
    return runs, payload, base, commit(repository, "This task")


def record_pass(repository: Path, head: str, base: str, age: float = 200.0) -> None:
    (repository / ".git/hard-eng-passed").write_text(
        json.dumps({"head": head, "base": base, "time": time.time() - age})
    )


@pytest.mark.parametrize("update_found", [True, False])
def test_a_plain_check_of_a_hard_eng_update_writes_no_pass_record(
    runner: ModuleType,
    tmp_path: Path,
    shipping_policy: ShippingPolicy,
    monkeypatch: pytest.MonkeyPatch,
    update_found: bool,
) -> None:
    pushed = prepared(runner, tmp_path, shipping_policy, monkeypatch)
    source = tmp_path / ".hooks/hard-eng-source.json"
    source.write_text(json.dumps({"revision": "a" * 40}))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "install")
    git(tmp_path, "push", "-q", "origin", "HEAD:main")
    if update_found:
        source.write_text(json.dumps({"revision": "b" * 40}))
    pushed.task()
    assert pushed.check(base="") == 0
    assert pushed.record().is_file() is not update_found


def test_a_stop_reuses_a_full_pass_of_this_commit_base_and_tree(
    repository: Path,
) -> None:
    runs, payload, base, head = committed_task(repository)
    record_pass(repository, head, base)
    assert agent_hooks.completion(repository, payload, "claude") == {
        "systemMessage": SENTENCE
    }
    assert "not rerun" in str(agent_hooks.completion(repository, payload, "claude"))
    assert not runs.exists()


@pytest.mark.parametrize(
    ("case", "statuses"),
    [
        ("another commit", 0),
        ("another base", 0),
        ("old", 0),
        ("absent", 0),
        ("new file", 0),
        ("build", 0),
        ("changed file", 1),
    ],
)
def test_a_stop_runs_its_check_when_no_full_pass_covers_it(
    repository: Path, monkeypatch: pytest.MonkeyPatch, case: str, statuses: int
) -> None:
    runs, payload, base, head = committed_task(repository)
    if case != "absent":
        record_pass(
            repository,
            base if case == "another commit" else head,
            head if case == "another base" else base,
            1900.0 if case == "old" else 200.0,
        )
    if case == "new file":
        (repository / "new.py").write_text("value = 1\n")
    if case == "changed file":
        (repository / "work.py").write_text("value = 2\n")
    if case == "build":

        def building(*_: object) -> bool:
            return True

        monkeypatch.setattr(plans, "build_in_progress", building)
    shown: list[JsonObject] = []

    def stop() -> int:
        shown.append(agent_hooks.completion(repository, payload, "claude"))
        return 0

    started = git_starts(stop)
    assert runs.read_text().count("run") == 1
    assert SENTENCE[:40] not in str(shown)
    assert len([c for c in started if "--porcelain=v2" in c]) == statuses


def test_a_held_check_lock_blocks_a_stop_with_a_full_pass(repository: Path) -> None:
    runs, payload, base, head = committed_task(repository)
    record_pass(repository, head, base)
    with (repository / ".git/hard-eng-check.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        blocked = agent_hooks.completion(repository, payload, "claude")
    assert blocked["decision"] == "block"
    assert "holds this checkout's lock" in str(blocked["reason"])
    assert not runs.exists()


@pytest.mark.parametrize("bad", ["--help", "-h", 5, None, ["x"]])
def test_a_pass_record_whose_base_is_no_commit_is_not_reused(
    repository: Path, bad: object
) -> None:
    runs, payload, _base, head = committed_task(repository)
    (repository / ".git/hard-eng-passed").write_text(
        json.dumps({"head": head, "base": bad, "time": time.time() - 200.0})
    )
    shown = agent_hooks.completion(repository, payload, "claude")
    assert runs.read_text().count("run") == 1
    assert "could not run" not in str(shown)
    assert SENTENCE[:40] not in str(shown)
    assert EARLIER[:40] not in str(shown)


@pytest.mark.parametrize("ancestor", [True, False])
def test_a_stop_reuses_a_full_pass_from_an_earlier_base(
    repository: Path, ancestor: bool
) -> None:
    git(repository, "commit", "--allow-empty", "-qm", "second")
    runs, payload, _base, head = committed_task(repository)
    root = git(repository, "rev-list", "--max-parents=0", "HEAD")
    if not ancestor:
        tree = git(repository, "rev-parse", f"{root}^{{tree}}")
        root = git(repository, "commit-tree", tree, "-p", root, "-m", "elsewhere")
    record_pass(repository, head, root)
    shown = agent_hooks.completion(repository, payload, "claude")
    assert (shown == {"systemMessage": EARLIER}) is ancestor
    assert runs.exists() is not ancestor


@pytest.mark.parametrize("row", ["plain", "ci", "quick", "ready"])
def test_a_full_check_with_no_base_writes_the_pass_record(
    runner: ModuleType,
    tmp_path: Path,
    shipping_policy: ShippingPolicy,
    monkeypatch: pytest.MonkeyPatch,
    row: str,
) -> None:
    pushed = prepared(runner, tmp_path, shipping_policy, monkeypatch)
    head = pushed.task()
    if row == "ci":
        monkeypatch.setenv("CI", "1")
    arguments = {"quick": ["--quick"], "ready": ["--plan-stage", "Ready"]}.get(row, [])
    assert pushed.check(*arguments, base="") == 0
    assert pushed.record().is_file() is (row == "plain")
    if row == "plain":
        saved = json.loads(pushed.record().read_text())
        assert (saved["head"], saved["base"]) == (head, pushed.base)

"""A Stop must not repeat a full check that passed on the same commit, base and clean tree."""

import fcntl
import json
import time
from pathlib import Path

import agent_hooks
import plans
import pytest
from conftest import add_origin, commit, git
from gate_config import JsonObject
from test_push_check import git_starts
from test_stop_checks import install_check

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

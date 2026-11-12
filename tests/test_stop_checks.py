"""Ending a turn must not rerun a passing check or leave an interrupted one running."""

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import agent_hooks
import debt
import failures
import process_group
import pytest
from conftest import SOURCE, add_origin, commit, git, gone, plan_document
from gate_config import Gate, Group, JsonObject
from test_plans import install_native_hooks
from test_push_check import git_starts


def install_check(repository: Path, script: str) -> Path:
    runs = repository.parent / "runs.txt"
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text(
        f"with open({str(runs)!r}, 'a') as runs:\n    runs.write('run\\n')\n" + script
    )
    (repository / ".git/info/exclude").write_text(".hard-eng/\n.hooks/\n")
    return runs


def test_a_stop_lists_the_untracked_files_while_it_finds_the_session_base(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "both"}
    monkeypatch.setattr(process_group, "process_table", list)
    agent_hooks.session_context(repository, payload)
    listing, scoped = threading.Event(), threading.Event()
    untracked, session_scope = agent_hooks.untracked, agent_hooks.session_scope

    def listed(root: Path) -> list[str]:
        listing.set()
        assert scoped.wait(timeout=5), "the listing ended before the base search"
        return untracked(root)

    def scope(root: Path, base: str, recorded: bool) -> tuple[str, str]:
        assert listing.wait(timeout=5), "the base search waited for the listing"
        scoped.set()
        return session_scope(root, base, recorded)

    monkeypatch.setattr(agent_hooks, "untracked", listed)
    monkeypatch.setattr(agent_hooks, "session_scope", scope)
    assert "no code checks run" in str(agent_hooks.completion(repository, payload))


def test_a_stop_gives_the_reason_when_the_listing_of_untracked_files_fails(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "reason"}
    monkeypatch.setattr(process_group, "process_table", list)
    agent_hooks.session_context(repository, payload)

    def listed(_root: Path) -> list[str]:
        return [b"caf\xe9.txt".decode()]

    monkeypatch.setattr(agent_hooks, "untracked", listed)
    blocked = agent_hooks.completion(repository, payload)
    assert blocked["decision"] == "block"
    assert "can't decode byte 0xe9" in str(blocked["reason"])


def test_unchanged_turn_after_a_passing_check_does_not_rerun_it(
    repository: Path,
) -> None:
    runs = install_check(repository, "raise SystemExit(0)\n")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    assert "decision" not in agent_hooks.completion(repository, payload)
    assert "not rerun" in str(agent_hooks.completion(repository, payload))
    assert runs.read_text().count("run") == 1
    (repository / "work.py").write_text("value = 2\n")
    assert "not rerun" not in str(agent_hooks.completion(repository, payload))
    assert runs.read_text().count("run") == 2


def test_unchanged_turn_during_a_build_reuses_the_pass_for_that_stage(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import plans

    def building(*_: object) -> bool:
        return True

    def finished(*_: object) -> bool:
        return False

    runs = install_check(repository, "raise SystemExit(0)\n")
    monkeypatch.setattr(plans, "build_in_progress", building)
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    assert "build in progress" in str(agent_hooks.completion(repository, payload))
    assert "not rerun" in str(agent_hooks.completion(repository, payload))
    assert runs.read_text().count("run") == 1
    monkeypatch.setattr(plans, "build_in_progress", finished)
    assert "not rerun" not in str(agent_hooks.completion(repository, payload))
    assert runs.read_text().count("run") == 2


@pytest.mark.parametrize("building", [True, False])
def test_the_lock_message_names_the_check_that_runs_gates_in_a_build(
    repository: Path, monkeypatch: pytest.MonkeyPatch, building: bool
) -> None:
    import fcntl

    import plans

    def build_state(*_: object) -> bool:
        return building

    monkeypatch.setattr(plans, "build_in_progress", build_state)
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "busy"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    with (repository / ".git/hard-eng-check.lock").open("w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        reason = str(agent_hooks.completion(repository, payload)["reason"])
    assert ("check --plan-stage Ready" in reason) == building
    assert "`python3 .hooks/hard-eng.py check" in reason


def test_work_merged_by_others_after_the_session_started_is_not_checked(
    repository: Path,
) -> None:
    runs = install_check(repository, "raise SystemExit(1)\n")
    add_origin(repository)
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "other.py").write_text("value = \n")
    commit(repository, "Merged by someone else")
    git(repository, "push", "-q", "origin", "main")
    assert "decision" not in agent_hooks.completion(repository, payload)
    assert not runs.exists()
    (repository / "work.py").write_text("value = 1\n")
    assert agent_hooks.completion(repository, payload)["decision"] == "block"
    assert runs.read_text().count("run") == 1


def test_a_branch_on_a_shared_branch_checks_only_its_own_commits(
    repository: Path,
) -> None:
    seen = repository.parent / "argv.txt"
    install_check(
        repository,
        f"import sys\nopen({str(seen)!r}, 'w').write(' '.join(sys.argv))\n",
    )
    add_origin(repository)
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    git(repository, "checkout", "-qb", "develop")
    (repository / "other.py").write_text("value = 1\n")
    shared = commit(repository, "Another task")
    git(repository, "push", "-q", "origin", "develop")
    git(repository, "checkout", "-qb", "task")
    (repository / "work.py").write_text("value = 1\n")
    commit(repository, "This task")
    agent_hooks.completion(repository, payload)
    assert f"--base {shared}" in seen.read_text()


def unpushed_task(repository: Path) -> tuple[Path, Path, JsonObject, str, str]:
    """A task branch with one unpushed commit and a session id that has no record."""
    seen = repository.parent / "argv.txt"
    runs = install_check(
        repository,
        f"import sys\nopen({str(seen)!r}, 'w').write(' '.join(sys.argv))\n",
    )
    add_origin(repository)
    git(repository, "push", "-q", "origin", "main")
    parent = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-qb", "task")
    (repository / "work.py").write_text("value = 1\n")
    commit(repository, "This task")
    return runs, seen, {"session_id": "unknown"}, parent, "task"


def test_a_stop_with_no_session_record_checks_the_commits_that_are_not_pushed(
    repository: Path,
) -> None:
    runs, seen, payload, parent, _ = unpushed_task(repository)
    answer = agent_hooks.completion(repository, payload)
    assert "no code checks run" not in str(answer)
    assert runs.read_text().count("run") == 1
    assert f"--base {parent}" in seen.read_text()


def test_the_first_pass_of_a_stop_with_no_record_keeps_the_base_of_the_commits_that_are_not_pushed(
    repository: Path,
) -> None:
    runs, _, payload, parent, _ = unpushed_task(repository)
    agent_hooks.completion(repository, payload)
    state = repository / ".hard-eng/sessions/unknown.json"
    assert json.loads(state.read_text())["base"] == parent
    again = agent_hooks.completion(repository, payload)
    assert "unchanged since last passing check" in str(again)
    assert runs.read_text().count("run") == 1


def searched(repository: Path, base: str) -> tuple[tuple[str, str], int]:
    """The answer of the base search and the number of Git processes that it started."""
    found: list[tuple[str, str]] = []

    def search() -> int:
        found.append(agent_hooks.session_scope(repository, base))
        return 0

    started = len(git_starts(search))
    return found[0], started


def test_the_base_search_asks_git_one_time_at_the_branch_point(
    repository: Path,
) -> None:
    add_origin(repository)
    git(repository, "push", "-q", "origin", "main")
    base = git(repository, "rev-parse", "HEAD")
    git(repository, "checkout", "-qb", "task")
    (repository / "work.py").write_text("value = 1\n")
    first = commit(repository, "This task")
    assert searched(repository, base) == ((base, first), 1)
    (repository / "work.py").write_text("value = 2\n")
    second = commit(repository, "More of this task")
    assert searched(repository, first) == ((first, second), 2)


def test_the_base_search_gives_the_base_and_the_commit_of_each_history(
    repository: Path,
) -> None:
    root = git(repository, "rev-parse", "HEAD")
    (repository / "work.py").write_text("value = 1\n")
    local = commit(repository, "No remote yet")
    assert searched(repository, root)[0] == (root, local)
    add_origin(repository)
    git(repository, "push", "-q", "origin", "main")
    assert searched(repository, root)[0] == (local, local)
    git(repository, "checkout", "-qb", "task")
    (repository / "work.py").write_text("value = 2\n")
    pushed = commit(repository, "Pushed part")
    git(repository, "push", "-q", "origin", "task")
    (repository / "work.py").write_text("value = 3\n")
    tip = commit(repository, "Part that is not pushed")
    assert searched(repository, local)[0] == (pushed, tip)
    assert searched(repository, tip)[0] == (tip, tip)
    git(repository, "checkout", "-q", "main")
    (repository / "other.py").write_text("value = 1\n")
    moved = commit(repository, "The base moves")
    git(repository, "push", "-q", "origin", "main")
    git(repository, "checkout", "-qb", "late", pushed)
    git(repository, "merge", "-q", "--no-ff", "-m", "Merge the base", "main")
    merged = git(repository, "rev-parse", "HEAD")
    assert searched(repository, local)[0] == (pushed, merged)
    assert moved != merged


def recorded_session(repository: Path) -> JsonObject:
    install_check(repository, "raise SystemExit(0)\n")
    add_origin(repository)
    git(repository, "push", "-q", "origin", "main")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    return payload


def test_a_stop_asks_git_for_no_answer_that_it_holds(repository: Path) -> None:
    payload = recorded_session(repository)
    shown: list[JsonObject] = []

    def stop() -> int:
        shown.append(agent_hooks.completion(repository, payload))
        return 0

    clean = git_starts(stop)
    assert "no code checks run" in str(shown[-1])
    assert len(clean) == 5
    assert not [command for command in clean if "--end-of-options" in command]
    (repository / "work.py").write_text("value = 1\n")
    changed = git_starts(stop)
    assert "decision" not in shown[-1]
    assert len(changed) == 7
    assert len([command for command in changed if ":(icase)plan.md" in command]) == 1


@pytest.mark.parametrize("remote", [True, False])
def test_a_stop_blocks_when_git_cannot_read_the_session_base(
    repository: Path, remote: bool
) -> None:
    payload: JsonObject = {"session_id": "known"}
    if remote:
        payload = recorded_session(repository)
    else:
        assert agent_hooks.record_session(repository, payload)
    state = repository / ".hard-eng/sessions/known.json"
    state.write_text(json.dumps({"base": "0" * 39 + "1", "dirty": {}}))
    blocked = agent_hooks.completion(repository, payload)
    assert blocked["decision"] == "block"
    assert "Verification could not run" in str(blocked["reason"])


def test_a_session_record_asks_git_only_for_what_it_needs(repository: Path) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    (repository / "kept.py").write_text("value = 1\n")
    head = commit(repository, "A tracked file")

    def recorded(session: str) -> tuple[JsonObject, int]:
        payload: JsonObject = {"session_id": session}

        def record() -> int:
            return int(not agent_hooks.record_session(repository, payload))

        started = len(git_starts(record))
        state = repository / f".hard-eng/sessions/{session}.json"
        return json.loads(state.read_text()), started

    assert recorded("clean") == ({"base": head, "dirty": {}}, 1)
    assert recorded("clean") == ({"base": head, "dirty": {}}, 0)
    (repository / "kept.py").write_text("value = 2\n")
    (repository / "new.py").write_text("value = 1\n")
    saved, started = recorded("dirty")
    dirty = saved["dirty"]
    assert saved["base"] == head
    assert isinstance(dirty, dict)
    assert sorted(dirty) == ["kept.py", "new.py"]
    assert started == 3


def test_failed_check_is_rerun_on_the_next_turn(repository: Path) -> None:
    runs = install_check(repository, "raise SystemExit(1)\n")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    for _ in range(2):
        assert agent_hooks.completion(repository, payload)["decision"] == "block"
    assert runs.read_text().count("run") == 2


def test_turn_end_waits_for_running_background_agents_before_checking(
    repository: Path,
) -> None:
    runs = install_check(repository, "raise SystemExit(1)\n")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = \n")
    for kind in ("subagent", "workflow", "teammate"):
        waiting: JsonObject = {
            **payload,
            "background_tasks": [{"id": "1", "type": kind}],
        }
        result = agent_hooks.completion(repository, waiting)
        assert "decision" not in result
        assert "background" in str(result["systemMessage"])
    assert not runs.exists()
    shell: JsonObject = {
        **payload,
        "background_tasks": [{"id": "2", "type": "shell"}],
    }
    assert agent_hooks.completion(repository, shell)["decision"] == "block"


def test_interrupted_stop_hook_stops_every_check_process(
    repository: Path, tmp_path: Path
) -> None:
    tool = tmp_path / "tool.pid"
    install_check(
        repository,
        "import subprocess, time\n"
        f"open({str(tool)!r}, 'w').write(str(subprocess.Popen(['sleep', '60']).pid))\n"
        "time.sleep(60)\n",
    )
    hook = subprocess.Popen(
        [
            sys.executable,
            "-c",
            (
                f"import sys; sys.path.insert(0, {str(SOURCE / '.hooks')!r})\n"
                "import agent_hooks\n"
                "from pathlib import Path\n"
                "print(agent_hooks.run_check(Path.cwd(), 'HEAD', False)[0])\n"
            ),
        ],
        cwd=repository,
        stdout=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 30
    while not tool.is_file() or not tool.read_text():
        assert time.monotonic() < deadline and hook.poll() is None
        time.sleep(0.05)
    hook.terminate()
    output, _ = hook.communicate(timeout=30)
    assert output.strip() != "0"
    assert gone(tool)


def test_stop_hook_runs_the_quick_check(repository: Path) -> None:
    seen = repository.parent / "argv.txt"
    install_check(
        repository,
        f"import sys\nopen({str(seen)!r}, 'w').write(' '.join(sys.argv))\n",
    )
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    agent_hooks.completion(repository, payload)
    assert "check --quick --base" in seen.read_text()


def test_failure_reason_lists_failed_gates_and_starts_at_the_first_error(
    repository: Path,
) -> None:
    install_check(
        repository,
        "print('OUTPUT ./lint')\n"
        "print('FIRST ERROR')\n"
        "print('x' * 30000)\n"
        "print('FAIL lint (exit 1; elapsed 1.0s)')\n"
        "print('OUTPUT ./types')\n"
        "print('second error')\n"
        "print('FAIL types (exit 1; elapsed 1.0s)')\n"
        "raise SystemExit(1)\n",
    )
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    reason = str(agent_hooks.completion(repository, payload)["reason"])
    assert reason.startswith("Failed gates: lint, types")
    assert reason.index("FIRST ERROR") < reason.index("Verification failed")
    assert "second error" not in reason
    assert len(reason) < 10000
    assert "[gate output cut; rerun check for the full log]" in reason


def test_failure_reason_shows_the_failing_packages_output_not_a_passing_one_of_the_same_gate(
    repository: Path,
) -> None:
    install_check(
        repository,
        "print('CHECK a/lint')\n"
        "print('CHECK b/lint')\n"
        "print('OUTPUT a/lint')\n"
        "print('a is clean')\n"
        "print('OUTPUT b/lint')\n"
        "print('b is broken')\n"
        "print('PASS lint (exit 0; elapsed 1.0s) @ a')\n"
        "print('FAIL lint (exit 1; elapsed 1.0s) @ b')\n"
        "raise SystemExit(1)\n",
    )
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    reason = str(agent_hooks.completion(repository, payload)["reason"])
    assert "b is broken" in reason
    assert "a is clean" not in reason


def stop_reason(repository: Path, script: str) -> str:
    install_check(repository, script)
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "work.py").write_text("value = 1\n")
    return str(agent_hooks.completion(repository, payload)["reason"])


def test_stop_lists_only_gates_with_findings_beyond_the_debt(
    repository: Path,
) -> None:
    reason = stop_reason(
        repository,
        "print('OUTPUT ./lint')\n"
        "print('old lint finding')\n"
        "print('FAIL lint (exit 1; elapsed 1.0s) @ .')\n"
        "print('DEBT lint @ .: the failure above holds only the 1 lines recorded')\n"
        "print('OUTPUT ./types')\n"
        "print('types noise')\n"
        "print('FAIL types (exit 1; elapsed 1.0s) @ .')\n"
        "print('FAIL types @ .: findings beyond hard-eng.debt.json:')\n"
        "print('  new.py:N bad type')\n"
        "raise SystemExit(1)\n",
    )
    assert reason.startswith("Failed gates: types\n")
    assert "old lint finding" not in reason
    assert "findings beyond hard-eng.debt.json:\n  new.py:N bad type" in reason


def test_stop_keeps_the_debt_line_of_a_failed_gate() -> None:
    log = (
        "OUTPUT ./lint\nold lint finding\n"
        "OUTPUT ./types\ntypes finding\n"
        "FAIL lint (exit 1; elapsed 1.0s) @ .\n"
        "FAIL types (exit 1; elapsed 1.0s) @ .\n"
        "DEBT lint @ .: the failure above holds only the 1 lines recorded\n"
    )
    summary = agent_hooks.failure_summary(log)
    assert summary.startswith("Failed gates: types\n")
    assert (
        "FAIL lint (exit 1; elapsed 1.0s) @ .\n"
        "DEBT lint @ .: the failure above holds only the 1 lines recorded\n"
    ) in summary


def test_stop_keeps_a_failed_gate_whose_name_another_package_had_forgiven(
    repository: Path,
) -> None:
    reason = stop_reason(
        repository,
        "print('OUTPUT api/types')\n"
        "print('old api finding')\n"
        "print('FAIL types (exit 1; elapsed 1.0s) @ api')\n"
        "print('DEBT types @ api: the failure above holds only the 1 lines recorded')\n"
        "print('OUTPUT web/types')\n"
        "print('web finding')\n"
        "print('FAIL types (exit 1; elapsed 1.0s) @ web')\n"
        "raise SystemExit(1)\n",
    )
    assert reason.startswith("Failed gates: types @ web\n")
    assert "web finding" in reason
    assert "old api finding" not in reason


def test_stop_shows_the_new_debt_findings_of_the_package_whose_output_it_shows(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["lint"]}
    groups: list[Group] = [{"path": name, "checks": [lint]} for name in ("api", "web")]
    recorded = {f"{name}/lint": {"old finding": 1} for name in ("api", "web")}
    (tmp_path / debt.DEBT_FILE).write_text(
        json.dumps({"version": 1, "gates": recorded})
    )
    log = "".join(
        f"OUTPUT {name}/lint\nold finding\nFAIL lint (exit 1; elapsed 1.0s) @ {name}\n"
        for name in ("api", "web")
    )
    for group in reversed(groups):
        output = f"old finding\nnew in {group['path']}\n"
        assert debt.judge(tmp_path, group, lint, True, output) is True
    summary = agent_hooks.failure_summary(log + capsys.readouterr().out)
    assert "  new in api\n" in summary
    assert "new in web" not in summary


def test_stop_shows_the_adopt_step_when_recorded_lines_are_fixed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["lint"]}
    group: Group = {"path": ".", "checks": [lint]}
    recorded = "a.py:3:1: F841 unused x\nb.py:2:1: F841 unused y\n"
    assert debt.record(tmp_path, [group], {"./lint"}, {"./lint": recorded}) == 0
    output = "b.py:2:1: F841 unused y\n"
    printed = f"OUTPUT ./lint\n{output}FAIL lint (exit 1; elapsed 1.0s) @ .\n"
    assert debt.judge(tmp_path, group, lint, True, output) is True
    summary = agent_hooks.failure_summary(printed + capsys.readouterr().out)
    step = "run `python3 .hooks/hard-eng.py adopt`"
    assert f"FAIL lint @ .: 1 recorded lines are fixed; {step}" in summary
    assert debt.record(tmp_path, [group], {"./lint"}, {"./lint": output}) == 0
    assert debt.judge(tmp_path, group, lint, True, output) is False


def test_stop_text_has_no_link_codes() -> None:
    biome = (Path(__file__).parent / "fixtures/debt/biome-two.txt").read_text()
    assert "\x1b]8;;https://biomejs.dev" in biome
    log = f"OUTPUT ./lint\n{biome}FAIL lint (exit 1; elapsed 1.0s) @ .\n"
    summary = agent_hooks.failure_summary(log)
    assert "\x1b" not in summary
    assert "lint/suspicious/noVar" in summary


def test_stop_names_the_package_of_each_failed_gate() -> None:
    log = "".join(
        f"OUTPUT {name}/lint\n{name} finding\nFAIL lint (exit 1; elapsed 1.0s) @ {name}\n"
        for name in ("alpha", "beta")
    )
    assert agent_hooks.failure_summary(log).startswith(
        "Failed gates: lint @ alpha, lint @ beta\n"
    )


def test_stop_text_has_no_colour_codes(repository: Path) -> None:
    reason = stop_reason(
        repository,
        "print('OUTPUT ./lint')\n"
        "print('\\x1b[31ma\\x1b[0m' * 8500)\n"
        "print('FAIL lint (exit 1; elapsed 1.0s) @ .')\n"
        "raise SystemExit(1)\n",
    )
    assert "\x1b" not in reason
    assert "a" * 8000 in reason


def decision_record(repository: Path, status: str, applies: str = "") -> None:
    (repository / "docs/adr").mkdir(parents=True)
    (repository / "docs/adr/0001-pay.md").write_text(
        f"# 0001 — Pay\n\nStatus: {status}\n{applies}\n## Decision\nUse the ledger.\n"
    )
    (repository / "src/payments").mkdir(parents=True)
    (repository / "src/payments/a.py").write_text("x = 1\n")
    (repository / ".git/info/exclude").write_text(".hard-eng/\n.hooks/\n")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "adr"], cwd=repository, check=True)


def decision_turn(repository: Path, path: str = "src/payments/a.py") -> JsonObject:
    payload: JsonObject = {"session_id": "known"}
    state = repository / ".hard-eng/sessions/known.json"
    if not state.exists():
        install_check(repository, "raise SystemExit(0)\n")
        assert agent_hooks.record_session(repository, payload)
    (repository / path).write_text(f"x = {time.monotonic_ns()}\n")
    return agent_hooks.completion(repository, payload)


def test_matching_decision_blocks_once_per_session(repository: Path) -> None:
    decision_record(repository, "Accepted", "Applies to: `src/payments/`\n")
    first = decision_turn(repository)
    assert first["decision"] == "block"
    assert "Use the ledger." in str(first["reason"])
    assert "decision" not in decision_turn(repository)


def test_decision_text_joins_a_failed_check(repository: Path) -> None:
    decision_record(repository, "Accepted", "Applies to: `src/payments/`\n")
    install_check(repository, "print('FAIL gate')\nraise SystemExit(1)\n")
    payload: JsonObject = {"session_id": "known"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "src/payments/a.py").write_text("x = 2\n")
    reason = str(agent_hooks.completion(repository, payload)["reason"])
    assert "Verification failed" in reason
    assert "Use the ledger." in reason
    (repository / "src/payments/a.py").write_text("x = 3\n")
    assert "Use the ledger." not in str(agent_hooks.completion(repository, payload))


@pytest.mark.parametrize(
    ("status", "applies", "path"),
    [
        ("Accepted", "Applies to: `src/payments/`\n", "other.py"),
        (
            "Superseded by [0002](0002-x.md)",
            "Applies to: `src/payments/`\n",
            "src/payments/a.py",
        ),
        ("Proposed", "Applies to: `src/payments/`\n", "src/payments/a.py"),
        ("Accepted", "", "src/payments/a.py"),
    ],
)
def test_unmatched_or_inactive_decisions_do_not_block(
    repository: Path, status: str, applies: str, path: str
) -> None:
    decision_record(repository, status, applies)
    assert "decision" not in decision_turn(repository, path)


def test_a_failure_seen_before_in_this_checkout_is_named_as_a_repeat(
    repository: Path,
) -> None:
    failing = repository.parent / "failing.txt"
    failing.write_text("tests/test_a.py::test_one")
    install_check(
        repository,
        f"import time\nname = open({str(failing)!r}).read()\n"
        "print(f'FAIL tests (exit 1; elapsed {time.time()}s) @ .')\n"
        "print(f'FAILED {name} - assert {time.time_ns()} == 0')\n"
        "raise SystemExit(1)\n",
    )
    (repository / "work.py").write_text("value = 1\n")
    reasons = []
    for session in ("first", "second", "third"):
        payload: JsonObject = {"session_id": session}
        assert agent_hooks.record_session(repository, payload)
        (repository / "work.py").write_text(f"value = '{session}'\n")
        reasons.append(str(agent_hooks.completion(repository, payload)["reason"]))
        if session == "second":
            failing.write_text("tests/test_a.py::test_two")
    assert "Repeat failure" not in reasons[0]
    assert "Repeat failure: seen 2 times" in reasons[1]
    assert "Repeat failure" not in reasons[2]


def test_failures_without_a_fail_or_error_line_keep_their_own_count(
    tmp_path: Path,
) -> None:
    missing = "Hard Eng: a/PLAN.md: acceptance names tests that do not exist: t::x"
    stage = "Hard Eng: b/PLAN.md: plan is Ready; this check requires Complete"
    assert failures.repeat_note(tmp_path, missing) == ""
    assert failures.repeat_note(tmp_path, stage) == ""
    assert "Repeat failure: seen 2 times" in failures.repeat_note(tmp_path, stage)


def test_different_lint_findings_are_not_one_repeat(tmp_path: Path) -> None:
    def lint(code: str, message: str, place: str) -> str:
        return (
            "FAIL lint (exit 1; elapsed 0.2s) @ .\n"
            f"{code} [*] {message}\n --> {place}\n  |\nhelp: fix it\n\nFound 1 error.\n"
        )

    unused_import = lint("F401", "`os` imported but unused", "a.py:1:8")
    unused_name = lint(
        "F841", "Local variable `x` is assigned to but never used", "b.py:4:5"
    )
    assert failures.repeat_note(tmp_path, unused_import) == ""
    assert failures.repeat_note(tmp_path, unused_name) == ""
    assert "Repeat failure: seen 2 times" in failures.repeat_note(tmp_path, unused_name)


def test_failures_with_no_output_are_not_counted_as_repeats(tmp_path: Path) -> None:
    for output in ("", "\n  \n", ""):
        assert failures.repeat_note(tmp_path, output) == ""
    assert not (tmp_path / ".hard-eng/failures.json").exists()


@pytest.mark.parametrize("status", ["Draft", "Ready"])
def test_stop_passes_a_small_change_when_the_base_holds_an_open_plan(
    repository: Path, status: str
) -> None:
    plan = (
        plan_document()
        .replace("Status: Complete", f"Status: {status}")
        .replace("## Verification\nResult: Passed", "## Verification\nResult: Pending")
    )
    response = small_edit_after_plan(repository, plan, own_plan=False)
    message = str(response)
    assert "decision" not in response
    assert "build in progress" not in message
    assert "Planning incomplete" not in message


UNFINISHED_BASELINE = "## Baseline + execution\nResult: Pending"


def small_edit_after_plan(repository: Path, plan: str, *, own_plan: bool) -> JsonObject:
    """Stop after a 3-line edit; the plan is on the base, or the branch adds it before the session."""
    install_native_hooks(repository, "")
    (repository / ".git/info/exclude").write_text(".hard-eng/\n__pycache__/\n")
    (repository / "a.py").write_text("".join(f"line {n}\n" for n in range(30)))
    if not own_plan:
        (repository / "PLAN.md").write_text(plan)
    commit(repository, "the base")
    add_origin(repository)
    git(repository, "fetch", "-q", "origin")
    git(repository, "switch", "-qc", "work")
    if own_plan:
        (repository / "PLAN.md").write_text(plan)
        commit(repository, "the branch plan")
    payload: JsonObject = {"session_id": "small"}
    assert agent_hooks.record_session(repository, payload)
    (repository / "a.py").write_text(
        "".join(f"changed {n}\n" for n in range(3))
        + "".join(f"line {n}\n" for n in range(3, 30))
    )
    return agent_hooks.completion(repository, payload, "claude")


def test_stop_does_not_block_a_small_change_for_an_unfinished_draft_plan_of_the_base(
    repository: Path,
) -> None:
    plan = plan_document().replace("Status: Complete", "Status: Draft")
    response = small_edit_after_plan(
        repository,
        plan.replace("## Baseline + execution\nResult: Passed", UNFINISHED_BASELINE),
        own_plan=False,
    )
    assert "decision" not in response
    assert "Planning incomplete" not in str(response)
    assert "quick checks passed" in str(response)


def test_stop_still_blocks_when_the_branch_holds_its_own_unfinished_draft_plan(
    repository: Path,
) -> None:
    plan = plan_document().replace("Status: Complete", "Status: Draft")
    response = small_edit_after_plan(
        repository,
        plan.replace("## Baseline + execution\nResult: Passed", UNFINISHED_BASELINE),
        own_plan=True,
    )
    assert response["decision"] == "block"
    assert "Planning incomplete" in str(response)


def test_stop_shows_the_quick_check_line_for_a_small_change_when_the_base_holds_a_ready_plan(
    repository: Path,
) -> None:
    plan = (
        plan_document()
        .replace("Status: Complete", "Status: Ready")
        .replace("## Verification\nResult: Passed", "## Verification\nResult: Pending")
    )
    message = str(small_edit_after_plan(repository, plan, own_plan=False))
    assert "quick checks passed" in message
    assert "planning checks passed" not in message

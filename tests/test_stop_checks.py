"""Ending a turn must not rerun a passing check or leave an interrupted one running."""

import subprocess
import sys
import time
from pathlib import Path

import agent_hooks
import pytest
from conftest import SOURCE
from gate_config import JsonObject


def install_check(repository: Path, script: str) -> Path:
    runs = repository.parent / "runs.txt"
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text(
        f"with open({str(runs)!r}, 'a') as runs:\n    runs.write('run\\n')\n" + script
    )
    (repository / ".git/info/exclude").write_text(".hard-eng/\n.hooks/\n")
    return runs


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
    deadline = time.monotonic() + 10
    while subprocess.run(["kill", "-0", tool.read_text()], check=False).returncode == 0:
        assert time.monotonic() < deadline
        time.sleep(0.05)


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

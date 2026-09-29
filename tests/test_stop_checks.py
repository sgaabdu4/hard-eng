"""Ending a turn must not rerun a passing check or leave an interrupted one running."""

import subprocess
import sys
import time
from pathlib import Path

import agent_hooks
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

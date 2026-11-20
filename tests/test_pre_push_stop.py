import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import SOURCE, commit, default_policy, init

SLEEPER = (
    "import os, pathlib, time\n"
    "pathlib.Path(os.environ['MARKER']).write_text('up')\n"
    "time.sleep(60)\n"
)
EXITING = "import sys\nsys.exit({code})\n"
RESET = (
    "import os, signal, sys; signal.signal(signal.SIGHUP, signal.SIG_DFL); "
    "os.execv(sys.executable, [sys.executable, *sys.argv[1:]])"
)


def start_hook(tmp_path: Path, check: str) -> tuple[subprocess.Popen[str], Path]:
    root, marker = tmp_path / "repo", tmp_path / "started"
    init(root)
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"shipping": default_policy()})
    )
    (root / ".hooks").mkdir()
    (root / ".hooks/hard-eng.py").write_text(check)
    revision = commit(root, "slow check").strip()
    for source in (SOURCE / ".hooks").glob("*.py"):
        (root / ".hooks" / source.name).write_bytes(source.read_bytes())
    pushed = tmp_path / "pushed"
    pushed.write_text(f"refs/heads/task {revision} refs/heads/task {revision}\n")
    with pushed.open() as lines:
        hook = subprocess.Popen(
            [sys.executable, "-c", RESET, str(root / ".hooks/hard-eng.py"), "pre-push"],
            cwd=root,
            stdin=lines,
            stdout=subprocess.PIPE,
            text=True,
            env={**os.environ, "MARKER": str(marker)},
        )
    return hook, marker


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGHUP])
def test_a_pre_push_stopped_by_a_signal_says_the_check_did_not_finish(
    tmp_path: Path, signal_number: signal.Signals
) -> None:
    hook, marker = start_hook(tmp_path, SLEEPER)
    deadline = time.monotonic() + 60
    while not marker.exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    hook.send_signal(signal_number)
    output, _ = hook.communicate(timeout=30)
    assert hook.returncode == 128 + signal_number
    assert (
        f"Hard Eng: the pre-push check was stopped by {signal_number.name} before it finished. "
        "No check failed, so this is not a fault in the project: run the push again."
    ) in output


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGHUP])
def test_a_check_that_the_signal_reached_first_gets_the_same_line(
    tmp_path: Path, signal_number: signal.Signals
) -> None:
    hook, _ = start_hook(tmp_path, EXITING.format(code=128 + signal_number))
    output, _ = hook.communicate(timeout=60)
    assert hook.returncode == 128 + signal_number
    assert f"stopped by {signal_number.name} before it finished" in output


@pytest.mark.parametrize("signal_number", [signal.SIGTERM, signal.SIGHUP])
def test_a_check_that_a_signal_ended_before_its_handlers_start_gets_the_same_line(
    tmp_path: Path, signal_number: signal.Signals
) -> None:
    hook, _ = start_hook(
        tmp_path,
        "import os, signal\n"
        "signal.signal(signal.SIGHUP, signal.SIG_DFL)\n"
        f"os.kill(os.getpid(), signal.{signal_number.name})\n",
    )
    output, _ = hook.communicate(timeout=60)
    assert f"stopped by {signal_number.name} before it finished" in output


def test_an_interrupted_mutation_report_does_not_ask_for_another_push(
    tmp_path: Path,
) -> None:
    hook, _ = start_hook(
        tmp_path, 'import sys\nsys.exit(143 if sys.argv[1] == "mutation" else 0)\n'
    )
    output, _ = hook.communicate(timeout=60)
    assert hook.returncode == 0
    assert "stopped by" not in output


def test_a_check_that_fails_on_its_own_gets_no_stop_line(tmp_path: Path) -> None:
    hook, _ = start_hook(tmp_path, EXITING.format(code=1))
    output, _ = hook.communicate(timeout=60)
    assert hook.returncode == 1
    assert "stopped by" not in output

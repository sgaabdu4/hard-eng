"""HE-NO-FOREGROUND-POLL: the Claude shell hook denies foreground sleep waits."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import SOURCE

HOOK = SOURCE / ".hooks/polling.py"


def run(payload: object, hook: Path = HOOK) -> str:
    return subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def bash(command: str, **extra: object) -> dict[str, object]:
    return {"tool_name": "Bash", "tool_input": {"command": command, **extra}}


@pytest.mark.parametrize(
    "command",
    [
        "until grep -q done log; do sleep 5; done",
        "while kill -0 123; do sleep 1; done; cat out",
        "sleep 600; cat log",
        "sleep 2m && tail log",
        "python3 -c 'import time\nwhile True: time.sleep(5)'",
        "perl -e 'while (1) { select(undef, undef, undef, 3) }'",
    ],
)
def test_foreground_sleep_wait_is_denied(command: str) -> None:
    """HE-NO-FOREGROUND-POLL denies a main-session sleep loop or long sleep."""
    output = json.loads(run(bash(command)))["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"
    assert "run_in_background" in output["permissionDecisionReason"]


@pytest.mark.parametrize(
    "payload",
    [
        bash("until grep -q done log; do sleep 5; done", run_in_background=True),
        {**bash("sleep 600; cat log"), "agent_id": "worker"},
        bash("while kill -0 123; do sleep 0.2; done"),
        bash("for i in 1 2 3; do git push && break; sleep 8; done"),
        bash("npm start & sleep 3; curl localhost:3000"),
        bash("pytest -x"),
        {"tool_name": "Read", "tool_input": {"file_path": "sleep 600"}},
    ],
)
def test_background_subagent_and_short_waits_pass(payload: object) -> None:
    """A background job, a subagent, a short settle wait or a bounded retry is allowed."""
    assert run(payload) == ""


def test_registered_hook_allows_commands_outside_a_repository(tmp_path: Path) -> None:
    """A shell call outside any repository is never blocked by a missing hook script."""
    import agent_hooks

    result = subprocess.run(
        ["sh", "-c", agent_hooks.POLL_COMMAND],
        cwd=tmp_path,
        input=json.dumps(bash("sleep 600")),
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "GIT_CEILING_DIRECTORIES": str(tmp_path)},
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

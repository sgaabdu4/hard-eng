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
        "sleep 25; git status; sleep 25",
        "python3 -c 'import time; time.sleep(600)'",
        "python3 - <<'EOF'\nimport time\ntime.sleep(600)\nEOF",
        'bash -lc "sleep 45"',
        "python3 -c 'import time; time.sleep(20); time.sleep(20)'",
        'ssh build-host "while ! test -f done; do sleep 5; done"',
        'eval "sleep 40"',
        "ssh build-host <<'EOF'\nsleep 40\nEOF",
        "# wait, don't spam\nuntil curl -s localhost; do sleep 2; done\necho 'ready'",
        'out="$(until test -f done; do sleep 2; done)"',
        "python3 - <<'EOF'\n# don't stop\nimport time\ntime.sleep(60)\nprint('done')\nEOF",
        "ruby -e 'sleep 60'",
        "if test -f x; then until test -f done; do sleep 5; done; fi",
    ],
)
def test_foreground_sleep_wait_is_denied(command: str) -> None:
    """HE-NO-FOREGROUND-POLL denies a main-session sleep loop or a long wait in total."""
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


@pytest.mark.parametrize(
    "command",
    [
        'grep -rn "sleep 600" .hooks',
        'git commit -m "Stop the retry loop; sleep 60 was too long while CI runs"',
        "cat > notes.md <<'EOF'\nuntil the job ends, sleep 600\nEOF",
        "cat > docs/python/notes.md <<'EOF'\nuntil the job ends, sleep 600\nEOF",
        (
            "gh issue create --title \"Fix the bash hook\" --body-file - <<'EOF'\n"
            "The hook denies `while true; do sleep 5; done`.\nEOF"
        ),
        "sleep 2; grep -c while notes.md",
    ],
)
def test_sleep_and_loop_words_as_data_pass(command: str) -> None:
    """A search pattern, a message or a file body that names a wait is not a wait."""
    assert run(bash(command)) == ""


@pytest.mark.parametrize(
    "command",
    ['echo "open quote; sleep 60', "cat <<EOF\nsleep 600"],
)
def test_odd_shell_text_never_crashes_the_hook(command: str) -> None:
    """An open quote or an unclosed heredoc is read as commands, so the wait in it is denied."""
    output = json.loads(run(bash(command)))["hookSpecificOutput"]
    assert output["permissionDecision"] == "deny"


def test_registered_hook_allows_commands_outside_a_repository(tmp_path: Path) -> None:
    """A shell call outside any repository is never blocked by a missing hook script."""
    import agent_hooks

    result = subprocess.run(
        ["sh", "-c", agent_hooks.POLL_COMMAND],
        cwd=tmp_path,
        input=json.dumps(bash("sleep 600")),
        capture_output=True,
        text=True,
        env={"PATH": os.environ["PATH"], "CLAUDE_PROJECT_DIR": str(tmp_path)},
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")

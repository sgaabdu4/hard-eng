"""HE-REAL-APP-PREVIEW: the Claude Artifact hook notes real-app previews without blocking."""

import json
import os
import subprocess
from pathlib import Path

import agent_hooks
import pytest
from conftest import SOURCE
from test_polling import run

HOOK = SOURCE / ".hooks/previews.py"


def artifact(**tool_input: object) -> dict[str, object]:
    return {"tool_name": "Artifact", "tool_input": tool_input}


@pytest.mark.parametrize(
    "payload",
    [
        artifact(file_path="mock.html", icon="layout"),
        artifact(
            action="publish", file_path="mock.html", url="https://claude.ai/artifact/x"
        ),
        artifact(action="quickstart", intent="other", design_systems=False),
        {**artifact(file_path="mock.html"), "agent_id": "worker"},
    ],
)
def test_notes_artifact_page_calls(payload: object) -> None:
    """HE-REAL-APP-PREVIEW: a page call proceeds with a note to capture the real app."""
    output = json.loads(run(payload, HOOK))["hookSpecificOutput"]
    assert "permissionDecision" not in output
    note = output["additionalContext"]
    assert note.startswith("HE-REAL-APP-PREVIEW")


@pytest.mark.parametrize(
    "payload",
    [
        artifact(action="read", url="https://claude.ai/artifact/x"),
        {"tool_name": "Bash", "tool_input": {"command": "ls"}},
        {"tool_name": "Artifact", "tool_input": "mock.html"},
        ["Artifact"],
    ],
)
def test_ignores_artifact_reads_and_other_tools(payload: object) -> None:
    """Reads, other tools and malformed input get no note."""
    assert run(payload, HOOK) == ""


def test_installed_command_adds_the_note(tmp_path: Path) -> None:
    """The registered command finds the hook from the host's project folder and never fails outside one."""
    environment = {"PATH": os.environ["PATH"]}
    inside = subprocess.run(
        ["sh", "-c", agent_hooks.PREVIEW_COMMAND],
        cwd=SOURCE,
        input=json.dumps(artifact(file_path="mock.html")),
        capture_output=True,
        text=True,
        env={**environment, "CLAUDE_PROJECT_DIR": str(SOURCE)},
        check=True,
    )
    assert (
        "HE-REAL-APP-PREVIEW"
        in json.loads(inside.stdout)["hookSpecificOutput"]["additionalContext"]
    )
    outside = subprocess.run(
        ["sh", "-c", agent_hooks.PREVIEW_COMMAND],
        cwd=tmp_path,
        input=json.dumps(artifact(file_path="mock.html")),
        capture_output=True,
        text=True,
        env={**environment, "CLAUDE_PROJECT_DIR": str(tmp_path)},
        check=False,
    )
    assert (outside.returncode, outside.stdout, outside.stderr) == (0, "", "")

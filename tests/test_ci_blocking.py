"""The Hard Eng workflow must block: its job and its check step cannot be made to pass on failure."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

WORKFLOW = ".github/workflows/hard-eng.yml"
JOB = "jobs:\n  hard-eng:\n    name: hard-eng\n    runs-on: ubuntu-latest\n"
STEP = "    steps:\n      - run: python3 .hooks/hard-eng.py check\n"


@pytest.mark.parametrize(
    "text",
    [
        JOB + "    continue-on-error: true\n" + STEP,
        JOB + STEP + "        continue-on-error: true\n",
        JOB + "    continue-on-error: ${{ github.ref != 'refs/heads/main' }}\n" + STEP,
        JOB + "    steps:\n      - run: python3 .hooks/hard-eng.py check || true\n",
        JOB + "    steps:\n      - run: python3 .hooks/hard-eng.py check || :\n",
        JOB + "    steps:\n      - run: python3 .hooks/hard-eng.py check; true\n",
        JOB + "    steps:\n      - run: python3 .hooks/hard-eng.py check;true\n",
    ],
)
def test_a_hard_eng_workflow_that_cannot_fail_is_refused(
    tmp_path: Path, text: str
) -> None:
    """HE-NO-SWITCH-OFF: `continue-on-error` or a trailing `|| true` turns a failing check into a green job."""
    message = refusal(project(tmp_path, {WORKFLOW: text}))
    assert f"{WORKFLOW}:" in message
    assert "blocking" in message


@pytest.mark.parametrize(
    ("name", "text"),
    [
        (WORKFLOW, JOB + "    continue-on-error: false\n" + STEP),
        (
            WORKFLOW,
            JOB
            + "    steps:\n      - run: python3 .hooks/hard-eng.py impact --base x >> out || echo runner=a >> out\n",
        ),
        (".github/workflows/other.yml", JOB + "    continue-on-error: true\n"),
    ],
)
def test_a_blocking_workflow_and_other_workflows_pass(
    tmp_path: Path, name: str, text: str
) -> None:
    validate_whole_project(project(tmp_path, {name: text}))

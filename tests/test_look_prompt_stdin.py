"""The reviewer prompt goes to the agent on stdin, so a prompt over the one-argument limit of Linux (131,072 bytes) still reaches it whole."""

import json
from pathlib import Path

import look_reviewer
import pytest
from test_look import install_agent, look_project

project = pytest.fixture(look_project)

ARGUMENT_LIMIT = 131_072


@pytest.mark.parametrize("reviewer", ["claude", "codex"])
def test_a_prompt_over_the_argument_limit_reaches_the_reviewer_whole_through_stdin(
    tmp_path: Path, project: Path, reviewer: str
) -> None:
    prompt = "A" * (ARGUMENT_LIMIT + 5_000) + "\nEND-OF-THE-PROMPT\n"
    log = install_agent(tmp_path, reviewer, 0, "answer")
    folder = tmp_path / "work"
    folder.mkdir()
    result, problem, _ = look_reviewer.run_reviewer(reviewer, folder, prompt, project)
    assert problem == "" and result is not None
    seen = json.loads(log.read_text())
    assert seen["stdin"] == prompt
    assert max(len(part) for part in seen["argv"]) < 1_000
    assert "END-OF-THE-PROMPT" not in " ".join(seen["argv"])

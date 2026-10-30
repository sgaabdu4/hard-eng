"""A tool error warns only once it repeats, and refusals never count."""

import io
import json
import sys
from pathlib import Path

import agent_hooks
import pytest
from gate_config import JsonObject


def failure_outputs(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payloads: list[JsonObject],
) -> list[JsonObject]:
    outputs = []
    for payload in payloads:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        assert agent_hooks.handle_event(repository, "failure", "claude") == 0
        outputs.append(json.loads(capsys.readouterr().out))
    return outputs


def test_failure_hook_warns_on_the_third_identical_error(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session: JsonObject = {"session_id": "loop"}
    assert agent_hooks.record_session(repository, session)
    lock: list[JsonObject] = [
        {
            **session,
            "tool_name": "Bash",
            "error": f"Exit code 1\nERROR: lock held by pid {pid}",
        }
        for pid in (4242, 5151, 6060, 7171)
    ]
    other_tool: JsonObject = {**lock[0], "tool_name": "Read"}
    outputs = failure_outputs(
        repository,
        monkeypatch,
        capsys,
        [lock[0], lock[1], other_tool, lock[2], lock[3]],
    )
    assert outputs[:3] == [{}, {}, {}]
    for output, count in ((outputs[3], 3), (outputs[4], 4)):
        context = output["hookSpecificOutput"]
        assert isinstance(context, dict)
        assert context["hookEventName"] == "PostToolUseFailure"
        assert f"Same tool error {count} times" in str(context["additionalContext"])
        assert "lock held" not in json.dumps(output)
    state = agent_hooks.session_state(repository, session)
    assert agent_hooks.saved_session(state)[0] != "HEAD"


@pytest.mark.parametrize(
    "failure",
    [
        {"error": "The user doesn't want to proceed with this tool use."},
        {"error": "Permission for this action was denied by the classifier."},
        {"error": "PreToolUse:Bash hook error: blocked"},
        {"error": "Command timed out after 2m 0s"},
        {"error": "Exit code 1"},
        {"error": "ERROR: lock held", "is_interrupt": True},
    ],
)
def test_failure_hook_ignores_errors_that_are_not_agent_mistakes(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: JsonObject,
) -> None:
    session: JsonObject = {"session_id": "refused"}
    assert agent_hooks.record_session(repository, session)
    payload: JsonObject = {**session, "tool_name": "Bash", **failure}
    assert failure_outputs(repository, monkeypatch, capsys, [payload] * 4) == [{}] * 4


def test_failure_hook_counts_code_errors_that_name_a_timeout(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    session: JsonObject = {"session_id": "named"}
    assert agent_hooks.record_session(repository, session)
    payload: JsonObject = {
        **session,
        "tool_name": "Bash",
        "error": "FAILED tests/test_timeout.py::test_retry - TimeoutError",
    }
    outputs = failure_outputs(repository, monkeypatch, capsys, [payload] * 3)
    assert outputs[:2] == [{}, {}]
    assert "Same tool error 3 times" in json.dumps(outputs[2])

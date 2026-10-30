"""A tool error warns only once it repeats, and refusals never count."""

import io
import json
import subprocess
import sys
from pathlib import Path

import agent_hooks
import failures
import pytest
from gate_config import JsonObject


def failure_outputs(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    payloads: list[JsonObject],
) -> list[JsonObject]:
    outputs: list[JsonObject] = []
    nothing: JsonObject = {}
    for payload in payloads:
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
        assert failures.main(repository) == 0
        printed = capsys.readouterr().out
        outputs.append(json.loads(printed) if printed else nothing)
    return outputs


def test_failure_hook_without_session_state_writes_and_echoes_nothing(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = {
        "prompt": "PRIVATE_USER_STEERING",
        "tool_response": {"isError": True, "content": "UNTRUSTED_TOOL_INSTRUCTION"},
        "error": "PRIVATE_FAILURE_DETAIL",
    }
    for text in (json.dumps(payload), "[]", "{"):
        monkeypatch.setattr(sys, "stdin", io.StringIO(text))
        assert failures.main(repository) == 0
        assert capsys.readouterr().out == ""
    assert not (repository / ".hard-eng").exists()


@pytest.mark.parametrize("identifier", ["../outside", "a/b", ""])
def test_failure_hook_ignores_session_ids_that_leave_the_session_folder(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    identifier: str,
) -> None:
    (repository / ".hard-eng").mkdir()
    outside = repository / ".hard-eng/outside.json"
    outside.write_text("{}")
    payload: JsonObject = {"session_id": identifier, "error": "ERROR: lock held"}
    assert failure_outputs(repository, monkeypatch, capsys, [payload] * 3) == [{}] * 3
    assert outside.read_text() == "{}"


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
        {"error": "Exit code 1"},
        {"error": "ERROR: lock held", "is_interrupt": True},
        {"error": "[Request interrupted by user for tool use]"},
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


@pytest.mark.parametrize(
    "error",
    [
        "FAILED tests/test_timeout.py::test_retry - TimeoutError",
        "ERROR: database connection timed out",
        "Command timed out after 2m 0s",
        "ERROR: connection denied by server",
        "InterruptedError: [Errno 4] Interrupted system call",
    ],
)
def test_failure_hook_counts_errors_that_only_name_a_timeout_denial_or_interrupt(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: str,
) -> None:
    session: JsonObject = {"session_id": "named"}
    assert agent_hooks.record_session(repository, session)
    payload: JsonObject = {**session, "tool_name": "Bash", "error": error}
    outputs = failure_outputs(repository, monkeypatch, capsys, [payload] * 3)
    assert outputs[:2] == [{}, {}]
    assert "Same tool error 3 times" in json.dumps(outputs[2])


def test_failure_hook_loads_no_other_hard_eng_module() -> None:
    hooks = Path(failures.__file__).parent
    listing = (
        "import runpy, sys; runpy.run_path(sys.argv[1]); "
        "print('\\n'.join(getattr(m, '__file__', None) or '' for m in list(sys.modules.values())))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", listing, str(hooks / "failures.py")],
        input="{}",
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    assert [name for name in loaded if name.startswith(str(hooks))] == []

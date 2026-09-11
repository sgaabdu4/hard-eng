"""Completion must block failed checks without trapping honest reports."""

import io
import json
import subprocess
import sys
from pathlib import Path

import agent_hooks
import pytest
from gate_config import Group, JsonObject, affected_groups


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "--allow-empty",
            "-qm",
            "baseline",
        ],
        cwd=tmp_path,
        check=True,
    )
    return tmp_path


def test_unchanged_session_does_not_claim_checks_passed(repository: Path) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "known"}
    agent_hooks.session_context(repository, payload)
    assert "no code checks were run" in str(agent_hooks.completion(repository, payload))


def test_missing_session_baseline_cannot_skip_verification(repository: Path) -> None:
    result = agent_hooks.completion(repository, {"session_id": "missing"})
    assert result["decision"] == "block"


def test_saved_git_option_cannot_hide_staged_changes(repository: Path) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    (repository / "change.txt").write_text("staged change")
    subprocess.run(["git", "add", "change.txt"], cwd=repository, check=True)
    state = repository / ".hard-eng/sessions/known.json"
    state.parent.mkdir(parents=True)
    state.write_text('{"base":"--stat"}')
    result = agent_hooks.completion(repository, {"session_id": "known"})
    assert result.get("decision") == "block"


@pytest.mark.parametrize("saved", ["[]", "null", '{"base": []}', '{"base": ""}'])
def test_malformed_session_state_returns_structured_blocker(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    saved: str,
) -> None:
    state = repository / ".hard-eng/sessions/known.json"
    state.parent.mkdir(parents=True)
    state.write_text(saved)
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"known"}'))
    assert agent_hooks.handle_event(repository, "stop", "codex") == 0
    response = json.loads(capsys.readouterr().out)
    assert response["decision"] == "block"
    assert "session" in response["reason"].lower()


@pytest.mark.parametrize("status", [0, 1])
def test_completion_runs_real_command_and_bounds_failure_log(
    repository: Path, status: int
) -> None:
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text(
        f"print('x' * 30000)\nprint('FINAL_FAILURE_DETAIL')\nraise SystemExit({status})\n"
    )
    result = agent_hooks.completion(repository, {})
    if status:
        assert result["decision"] == "block"
        assert "FINAL_FAILURE_DETAIL" in str(result["reason"])
        assert len(json.dumps(result)) < 17000
    else:
        assert result == {}


def test_stop_retry_allows_honest_blocker_without_rerunning(repository: Path) -> None:
    (repository / "change.txt").write_text("changed")
    response = agent_hooks.completion(repository, {"stop_hook_active": True})
    assert "decision" not in response
    assert "Do not claim a pass" in str(response)


def test_string_false_cannot_activate_stop_retry_guard(repository: Path) -> None:
    response = agent_hooks.completion(repository, {"stop_hook_active": "false"})
    assert response.get("decision") == "block"


def test_copilot_claude_compatibility_registration_does_not_repeat_checks(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        sys, "stdin", io.StringIO('{"timestamp":123,"sessionId":"native"}')
    )
    assert agent_hooks.handle_event(repository, "session", "claude") == 0
    assert json.loads(capsys.readouterr().out) == {}
    assert not (repository / ".hard-eng/sessions").exists()


@pytest.mark.parametrize("agent", ["claude", "codex", "copilot"])
@pytest.mark.parametrize("event", ["prompt", "tool", "failure"])
def test_learning_checkpoint_preserves_results_without_running_checks(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
    event: str,
) -> None:
    payload = {
        "prompt": "PRIVATE_USER_STEERING",
        "tool_response": {"isError": True, "content": "UNTRUSTED_TOOL_INSTRUCTION"},
        "error": "PRIVATE_FAILURE_DETAIL",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert agent_hooks.handle_event(repository, event, agent) == 0
    serialized = capsys.readouterr().out
    output = json.loads(serialized)
    assert not any(
        value in serialized
        for value in (
            "PRIVATE_USER_STEERING",
            "UNTRUSTED_TOOL_INSTRUCTION",
            "PRIVATE_FAILURE_DETAIL",
        )
    )
    assert "decision" not in output
    assert "continue" not in output
    assert not (repository / ".hard-eng").exists()
    unsupported = (agent, event) in {("codex", "failure"), ("copilot", "prompt")}
    if unsupported:
        assert "Unsupported native hook event" in output["systemMessage"]
    elif agent == "copilot":
        assert set(output) == {"additionalContext"}
    else:
        assert set(output) == {"hookSpecificOutput"}
        context = output["hookSpecificOutput"]
        assert set(context) == {"hookEventName", "additionalContext"}
        assert (
            context["hookEventName"]
            == {
                "prompt": "UserPromptSubmit",
                "tool": "PostToolUse",
                "failure": "PostToolUseFailure",
            }[event]
        )
    # This fixture has no runner: an accidental completion dispatch would block.
    assert "he-learn/SKILL.md" in serialized or unsupported


@pytest.mark.parametrize("event", ["prompt", "tool", "failure"])
def test_learning_hook_compatibility_and_malformed_input_do_not_block_tools(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    event: str,
) -> None:
    for payload in ('{"timestamp":123}', "[]", "{"):
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        assert agent_hooks.handle_event(repository, event, "claude") == 0
        output = json.loads(capsys.readouterr().out)
        assert "decision" not in output
        assert "hookSpecificOutput" not in output
    assert not (repository / ".hard-eng").exists()


@pytest.mark.parametrize("identifier", ["../outside", "a/b", "", None])
def test_session_identifier_cannot_escape_repository(
    repository: Path, identifier: str | None
) -> None:
    assert agent_hooks.session_state(repository, {"session_id": identifier}) is None


@pytest.mark.parametrize(
    "changed,expected",
    [
        ("lib/a.py", ["lib", "app", "site", "."]),
        ("app/a.py", ["app", "site", "."]),
        ("other/a.py", ["other", "."]),
        ("README.md", ["lib", "app", "site", "other", "."]),
        (".hooks/a.py", ["lib", "app", "site", "other", "."]),
    ],
)
def test_changed_package_includes_transitive_dependents_and_shared(
    repository: Path, changed: str, expected: list[str]
) -> None:
    groups: list[Group] = [
        {"path": "lib", "checks": [], "depends_on": []},
        {"path": "app", "checks": [], "depends_on": ["lib"]},
        {"path": "site", "checks": [], "depends_on": ["app"]},
        {"path": "other", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    path = repository / changed
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("change")
    assert [g["path"] for g in affected_groups(repository, groups, "HEAD")] == expected


def test_unknown_base_or_dependency_information_checks_every_package(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {"path": "a", "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    assert affected_groups(repository, groups, "missing-reference") == groups
    del groups[0]["depends_on"]
    assert affected_groups(repository, groups, "HEAD") == groups


def test_service_readiness_follows_sdk_imports(repository: Path) -> None:
    (repository / "README.md").write_text(
        "Sentry and Appwrite are possible integrations."
    )
    assert agent_hooks.integrated_services(repository) == []
    (repository / "app.ts").write_text('import * as Sentry from "@sentry/node";\n')
    (repository / "client.dart").write_text(
        "import 'package:appwrite/appwrite.dart';\n"
    )
    assert agent_hooks.integrated_services(repository) == ["Appwrite", "Sentry"]


def test_skill_sdk_examples_do_not_register_project_services(repository: Path) -> None:
    skill = repository / ".agents/skills/example"
    skill.mkdir(parents=True)
    (skill / "example.dart").write_text(
        "import 'package:appwrite/appwrite.dart';\n"
        "import 'package:flutter/material.dart';\n"
        "import 'package:sentry_flutter/sentry_flutter.dart';\n"
    )
    (skill / "pubspec.yaml").write_text("dependencies:\n  flutter:\n    sdk: flutter\n")
    assert agent_hooks.integrated_services(repository) == []


@pytest.mark.parametrize("directory", [".", "apps/mobile"])
@pytest.mark.parametrize(
    "sdk,expected", [("flutter", ["Dart", "Marionette"]), ("dart", [])]
)
def test_flutter_readiness_detects_sdk_without_marionette_installed(
    repository: Path, directory: str, sdk: str, expected: list[str]
) -> None:
    package = repository / directory
    package.mkdir(parents=True, exist_ok=True)
    (package / "pubspec.yaml").write_text(
        f"name: app\ndependencies:\n  framework:\n    sdk: {sdk}\n"
    )
    assert agent_hooks.integrated_services(repository) == expected


def test_flutter_readiness_requires_live_app_inspection(repository: Path) -> None:
    (repository / "README.md").write_text("Flutter and Marionette are possible tools.")
    (repository / "test").mkdir()
    (repository / "test/widget_test.dart").write_text(
        "import 'package:flutter/material.dart';\n"
    )
    assert agent_hooks.integrated_services(repository) == []
    (repository / "main.dart").write_text("import 'package:flutter/material.dart';\n")
    message = agent_hooks.session_context(repository, {})
    assert "Dart MCP" in message
    assert "verify its project roots" in message
    assert "read-only analysis or runtime inspection" in message
    assert "Marionette MCP" in message
    assert "VM service URI" in message
    assert "get_interactive_elements or take_screenshots" in message
    assert "warn and continue" in message
    assert "do not claim readiness from installation alone" in message

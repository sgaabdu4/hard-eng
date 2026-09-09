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

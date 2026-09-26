"""Completion must block failed checks without trapping honest reports."""

import io
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import agent_hooks
import pytest
import update
from conftest import SOURCE, commit, git
from gate_config import Gate, Group, JsonObject, affected_groups
from shipping import ShippingPolicy


@pytest.mark.parametrize("existing", ["none", "files", "symlink"])
def test_native_instruction_paths_preserve_project_rules(
    installer: ModuleType, tmp_path: Path, existing: str
) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "package.json").write_text('{"private":true}')
    (tmp_path / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    if existing == "files":
        for name in ("CLAUDE.md", "AGENTS.override.md"):
            (tmp_path / name).write_bytes(b"# Custom rules\r\nPreserve these.\r\n")
    elif existing == "symlink":
        (tmp_path / "AGENTS.md").write_text("# Existing rules\nKeep these.\n")
        (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")
    installer.install(tmp_path)
    names = ["AGENTS.md", "CLAUDE.md"] + (
        ["AGENTS.override.md"] if existing == "files" else []
    )
    before = {name: (tmp_path / name).read_bytes() for name in names}
    installer.install(tmp_path)
    assert before == {name: (tmp_path / name).read_bytes() for name in names}
    if existing == "symlink":
        assert (tmp_path / "CLAUDE.md").is_symlink()
        assert before["CLAUDE.md"] == before["AGENTS.md"]
        assert before["AGENTS.md"].endswith(b"# Existing rules\nKeep these.\n")
    else:
        assert "\n@AGENTS.md\n" in (tmp_path / "CLAUDE.md").read_text()
    if existing == "files":
        for name in ("CLAUDE.md", "AGENTS.override.md"):
            assert before[name].endswith(b"# Custom rules\r\nPreserve these.\r\n")
        assert (
            "[shared instructions](AGENTS.md)"
            in (tmp_path / "AGENTS.override.md").read_text()
        )
    else:
        assert not (tmp_path / "AGENTS.override.md").exists()


def test_child_change_retains_parent_install_and_vulnerability_checks(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {
            "path": ".",
            "depends_on": [],
            "checks": [
                {
                    "name": "install",
                    "role": "lockfiles",
                    "command": ["pnpm", "install"],
                },
                {
                    "name": "audit",
                    "role": "vulnerabilities",
                    "command": ["osv-scanner"],
                },
                {"name": "unrelated", "role": "tests", "command": ["pnpm", "test"]},
            ],
        },
        {"path": "packages/child", "depends_on": ["."], "checks": []},
        {"path": "packages/other", "depends_on": ["."], "checks": []},
        {"path": ".", "checks": []},
    ]
    child = repository / "packages/child/index.js"
    child.parent.mkdir(parents=True)
    child.write_text("export const answer = 42;\n")
    selected = affected_groups(repository, groups, "HEAD")
    assert [g["path"] for g in selected] == [".", "packages/child", "."]
    assert [g["name"] for g in selected[0]["checks"]] == ["install", "audit"]
    assert len(groups[0]["checks"]) == 3


@pytest.mark.parametrize("credentials", ["none", "environment", "cli"])
def test_release_lookup_supports_account_free_setup_and_existing_auth(
    monkeypatch: pytest.MonkeyPatch, credentials: str
) -> None:
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    if credentials == "environment":
        monkeypatch.setenv("GITHUB_TOKEN", "fixture-token")
    monkeypatch.setattr(update.shutil, "which", Mock(return_value="gh"))
    auth = Mock(
        return_value=subprocess.CompletedProcess(
            ["gh", "auth", "token"], 0 if credentials == "cli" else 1, "fixture-token\n"
        )
    )
    monkeypatch.setattr(subprocess, "run", auth)
    request = Mock(return_value=io.StringIO('{"check_runs": []}'))
    monkeypatch.setattr(urllib.request, "urlopen", request)
    assert update.github_json("repos/example/fixture/check-runs") == {"check_runs": []}
    sent = request.call_args.args[0]
    assert sent.full_url == "https://api.github.com/repos/example/fixture/check-runs"
    assert sent.get_header("Authorization") == (
        None if credentials == "none" else "Bearer fixture-token"
    )
    assert auth.call_count == (0 if credentials == "environment" else 1)
    monkeypatch.setattr(urllib.request, "urlopen", Mock(side_effect=OSError("offline")))
    with pytest.raises(OSError, match="offline"):
        update.github_json("repos/example/fixture/check-runs")


@pytest.mark.parametrize("changed", [False, True])
@pytest.mark.parametrize("upstream", [None, "b" * 40, OSError("offline")])
def test_completion_checks_freshness_without_mutating_installation(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed: bool,
    upstream: str | OSError | None,
) -> None:
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text("raise SystemExit(0)\n")
    marker = hooks / "hard-eng-source.json"
    content = json.dumps({"revision": "a" * 40})
    marker.write_text(content)
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    subprocess.run(["git", "add", "."], cwd=repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "installed fixture",
        ],
        cwd=repository,
        check=True,
    )
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repository, text=True
    ).strip()
    state = repository / ".hard-eng/sessions/known.json"
    state.parent.mkdir(parents=True)
    state.write_text(json.dumps({"base": head}))
    if changed:
        (repository / "change.txt").write_text("local work")
    query = (
        Mock(side_effect=upstream)
        if isinstance(upstream, OSError)
        else Mock(return_value=upstream)
    )
    monkeypatch.setattr(update, "latest_verified", query)
    result = agent_hooks.completion(repository, {"session_id": "known"})
    if upstream is None:
        assert result.get("decision") != "block"
    else:
        assert result.get("decision") == "block"
        assert "freshness" in str(result).lower()
    query.assert_called_once_with("a" * 40)
    assert marker.read_text() == content
    assert (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repository, text=True
        ).strip()
        == head
    )


def test_unchanged_session_does_not_claim_checks_passed(repository: Path) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    payload: JsonObject = {"session_id": "known"}
    agent_hooks.session_context(repository, payload)
    assert "no code checks were run" in str(agent_hooks.completion(repository, payload))


def test_work_from_before_the_session_is_not_session_work(repository: Path) -> None:
    (repository / ".git/info/exclude").write_text(".hard-eng/\n")
    (repository / "tracked.py").write_text("value = 1\n")
    git(repository, "add", "tracked.py")
    git(repository, "commit", "-qm", "tracked")
    (repository / "tracked.py").write_text("value = 2\n")
    (repository / "draft.py").write_text("print('draft')\n")
    payload: JsonObject = {"session_id": "known"}
    agent_hooks.session_context(repository, payload)
    assert "no code checks were run" in str(agent_hooks.completion(repository, payload))
    (repository / "draft.py").write_text("print('session edit')\n")
    assert agent_hooks.completion(repository, payload)["decision"] == "block"


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


@pytest.mark.parametrize(
    "saved",
    ["[]", "null", '{"base": []}', '{"base": ""}', '{"base": "HEAD", "dirty": []}'],
)
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


@pytest.mark.parametrize("agent", ["claude", "codex", "copilot"])
def test_completion_surfaces_only_authoritative_stage_handoffs(
    repository: Path, agent: str
) -> None:
    hooks = repository / ".hooks"
    hooks.mkdir()
    (hooks / "hard-eng.py").write_text(
        "print('Hard Eng: build checks passed — ready for ship; remote delivery is not verified by this check.')\n"
    )
    result = agent_hooks.completion(repository, {}, agent)
    if agent == "copilot":
        assert result == {}
    else:
        assert result == {
            "systemMessage": "Hard Eng: build checks passed — ready for ship; remote delivery is not verified by this check."
        }


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
@pytest.mark.parametrize("offline", [False, True])
def test_session_reports_updater_result_once(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
    offline: bool,
) -> None:
    updater = Mock(
        side_effect=OSError("offline") if offline else None,
        return_value="No newer CI-verified Hard Eng revision is available.",
    )
    monkeypatch.setattr(update, "update", updater)
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"session_id":"startup"}'))
    assert agent_hooks.handle_event(repository, "session", agent) == 0
    output = json.loads(capsys.readouterr().out)
    updater.assert_called_once_with(repository)
    context = (
        output["additionalContext"]
        if agent == "copilot"
        else output["hookSpecificOutput"]["additionalContext"]
    )
    expected = (
        "Hard Eng update failed: offline"
        if offline
        else "Hard Eng update result: No newer CI-verified"
    )
    assert context.startswith(expected)
    if agent != "copilot":
        assert output["systemMessage"] == "Hard Eng startup: " + " ".join(
            context.splitlines()[:2]
        )
        assert "Gates: not runnable" in output["systemMessage"]
        assert "Use configured MCPs" not in output["systemMessage"]


def test_session_states_whether_gates_can_run(repository: Path) -> None:
    assert agent_hooks.gate_status(repository).startswith("Gates: not runnable — ")
    for name in ("PRODUCT.md", "DESIGN.md"):
        (repository / name).write_bytes((SOURCE / name).read_bytes())
    (repository / ".hooks").mkdir()
    (repository / update.SOURCE_FILE).write_text("{}\n")
    (repository / "hard-eng.gates.json").write_text(
        '{"families": {"lint": ["ruff", "check"]}}'
    )
    pending = (
        " Uncommitted Hard Eng paths stop updates and are missing from new "
        "worktrees; commit them: .hooks/ hard-eng.gates.json"
    )
    status = agent_hooks.gate_status(repository)
    assert "rerun the Hard Eng installer" in status and status.endswith(pending)
    (repository / "hard-eng.gates.json").write_text(
        json.dumps(
            {
                "packages": [],
                "shared": [{"name": "check", "command": ["python3", "-c", "pass"]}],
            }
        )
    )
    commit(repository, "commit installed files")
    assert agent_hooks.gate_status(repository) == "Gates: configuration valid."
    (repository / update.SOURCE_FILE).write_text('{"edited": true}\n')
    git(repository, "add", update.SOURCE_FILE)
    assert agent_hooks.gate_status(repository) == (
        "Gates: configuration valid. Uncommitted Hard Eng paths stop updates and are "
        "missing from new worktrees; commit them: .hooks/"
    )


@pytest.mark.parametrize("agent", ["claude", "codex", "copilot"])
def test_failure_checkpoint_preserves_results_without_running_checks(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    agent: str,
) -> None:
    payload = {
        "prompt": "PRIVATE_USER_STEERING",
        "tool_response": {"isError": True, "content": "UNTRUSTED_TOOL_INSTRUCTION"},
        "error": "PRIVATE_FAILURE_DETAIL",
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert agent_hooks.handle_event(repository, "failure", agent) == 0
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
    unsupported = agent == "codex"
    if unsupported:
        assert "Unsupported native hook event" in output["systemMessage"]
    elif agent == "copilot":
        assert set(output) == {"additionalContext"}
    else:
        assert set(output) == {"hookSpecificOutput"}
        context = output["hookSpecificOutput"]
        assert set(context) == {"hookEventName", "additionalContext"}
        assert context["hookEventName"] == "PostToolUseFailure"
    # This fixture has no runner: an accidental completion dispatch would block.
    assert "he-learn/SKILL.md" in serialized or unsupported


def test_learning_hook_compatibility_and_malformed_input_do_not_block_tools(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for payload in ('{"timestamp":123}', "[]", "{"):
        monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
        assert agent_hooks.handle_event(repository, "failure", "claude") == 0
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
        ("README.md", ["."]),
        ("AGENTS.md", ["lib", "app", "site", "other", "."]),
        (".agents/skills/x.md", ["lib", "app", "site", "other", "."]),
        ("lib/README.md", ["lib", "app", "site", "."]),
        (".hooks/a.py", ["lib", "app", "site", "other", "."]),
        ("PLAN.md", ["."]),
        ("features/task/PLAN.md", ["."]),
        ("docs/PLAN.md", ["lib", "app", "site", "other", "."]),
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
    for name in ("PLAN.md", "features/task/PLAN.md"):
        plan = repository / name
        plan.parent.mkdir(parents=True, exist_ok=True)
        plan.write_text("Task plan\n")
    assert [g["path"] for g in affected_groups(repository, groups, "HEAD")] == expected


def test_cross_package_fallow_coverage_owner_must_be_selected_with_its_consumer(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {"path": "packages/website", "checks": [], "depends_on": ["packages/api"]},
        {"path": "packages/api", "checks": [], "depends_on": ["packages/website"]},
        {"path": ".", "checks": []},
    ]
    (repository / "packages/api").mkdir(parents=True)
    (repository / "packages/api/change.mjs").write_text(
        "export const changed = true;\n"
    )
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        "packages/website",
        "packages/api",
        ".",
    ]
    groups[0]["depends_on"] = []
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        "packages/api",
        ".",
    ]


def test_unknown_base_or_dependency_information_checks_every_package(
    repository: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    groups: list[Group] = [
        {"path": "a", "checks": [], "depends_on": []},
        {"path": "b", "checks": [], "depends_on": []},
        {"path": ".", "checks": []},
    ]
    assert affected_groups(repository, groups, "missing-reference") == groups
    del groups[0]["depends_on"]
    changed = repository / "a/change.py"
    changed.parent.mkdir()
    changed.write_text("change")
    assert affected_groups(repository, groups, "HEAD") == groups
    output = capsys.readouterr().out
    assert "Package impact is unknown" in output
    assert "depends_on" in output


@pytest.mark.parametrize(
    "docs", [[], ["PLAN.md", "features/task/PLAN.md"], ["README.md", "CHANGELOG.md"]]
)
@pytest.mark.parametrize("root", ["a", "."])
def test_docs_only_change_runs_only_the_secret_scan(
    repository: Path, docs: list[str], root: str
) -> None:
    secrets: Gate = {"name": "secrets", "role": "secrets-files", "command": ["x"]}
    workflows: Gate = {"name": "workflows", "role": "workflows", "command": ["x"]}
    groups: list[Group] = [
        {"path": root, "checks": []},
        {"path": "b", "checks": []},
        {"path": ".", "checks": [secrets, workflows]},
    ]
    for name in docs:
        document = repository / name
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text("Documentation\n")
    assert affected_groups(repository, groups, "HEAD") == [
        {"path": ".", "checks": [secrets]}
    ]


def test_single_package_without_dependency_mapping_checks_full_package(
    repository: Path,
) -> None:
    groups: list[Group] = [
        {"path": "app", "checks": []},
        {"path": ".", "checks": []},
    ]
    changed = repository / "app/change.py"
    changed.parent.mkdir()
    changed.write_text("change")
    assert affected_groups(repository, groups, "HEAD") == groups


def test_root_lockfile_change_includes_reviewed_consumers(repository: Path) -> None:
    groups: list[Group] = [
        {"path": ".", "checks": [], "depends_on": []},
        {"path": "packages/app", "checks": [], "depends_on": ["."]},
        {"path": "packages/site", "checks": [], "depends_on": ["."]},
        {"path": ".", "checks": []},
    ]
    (repository / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
    assert [group["path"] for group in affected_groups(repository, groups, "HEAD")] == [
        ".",
        "packages/app",
        "packages/site",
        ".",
    ]


def test_service_readiness_follows_sdk_imports(repository: Path) -> None:
    (repository / "README.md").write_text(
        "Sentry and Appwrite are possible integrations."
    )
    assert agent_hooks.integrated_services(repository) == []
    (repository / "app.ts").write_text('import * as Sentry from "@sentry/node";\n')
    (repository / "client.dart").write_text(
        "import 'package:appwrite/appwrite.dart';\n"
    )
    assert agent_hooks.integrated_services(repository) == ["Appwrite", "Dart", "Sentry"]


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
@pytest.mark.parametrize("sdk,expected", [("flutter", ["Dart"]), ("dart", ["Dart"])])
def test_flutter_readiness_detects_sdk_without_marionette_installed(
    repository: Path, directory: str, sdk: str, expected: list[str]
) -> None:
    package = repository / directory
    package.mkdir(parents=True, exist_ok=True)
    (package / "pubspec.yaml").write_text(
        f"name: app\ndependencies:\n  framework:\n    sdk: {sdk}\n"
    )
    assert agent_hooks.integrated_services(repository) == expected


def test_session_defers_integration_readiness_until_relevant_use(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scan = Mock(side_effect=AssertionError("Startup must not scan integrations"))
    monkeypatch.setattr(agent_hooks, "integrated_services", scan)
    message = agent_hooks.session_context(repository, {})
    scan.assert_not_called()
    assert "when relevant to the task" in message
    assert "verify a real call" in message
    assert "warn and continue" in message
    assert "registration alone is not readiness" in message


def assert_rerun_keeps_written_hooks(
    repository: Path, installer: ModuleType, path: Path, changes: dict[str, str]
) -> None:
    written = str(path.relative_to(repository))
    path.write_text(changes[written])
    repeated: dict[str, str] = {}
    installer.configure_hooks(repository, repeated)
    assert repeated == {name: text for name, text in changes.items() if name != written}


@pytest.mark.parametrize("agent", ["claude", "codex", "copilot"])
def test_setup_removes_owned_routine_hooks_and_preserves_custom_hooks(
    repository: Path, installer: ModuleType, agent: str
) -> None:
    path = (
        repository
        / {
            "claude": ".claude/settings.json",
            "codex": ".codex/hooks.json",
            "copilot": ".github/hooks/hard-eng.json",
        }[agent]
    )
    path.parent.mkdir(parents=True)
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    hooks: JsonObject = {}
    custom: JsonObject = {"type": "command", "command": "echo custom", "timeout": 10}
    for event, native in (("prompt", "UserPromptSubmit"), ("tool", "PostToolUse")):
        if agent == "copilot" and event == "prompt":
            continue
        handler: JsonObject = {
            "type": "command",
            "command": f"{command} {event} {agent}",
            "timeout": 10,
        }
        hooks[native] = [{"hooks": [handler]}, {"hooks": [custom]}]
        if agent == "copilot":
            hooks = {
                "postToolUse": [
                    {
                        "type": "command",
                        "bash": f"{command} tool copilot",
                        "timeoutSec": 10,
                    },
                    {"type": "command", "bash": "echo custom", "timeoutSec": 10},
                ]
            }
    path.write_text(json.dumps({"hooks": hooks}))
    changes: dict[str, str] = {}
    installer.configure_hooks(repository, changes)
    result = json.loads(changes[str(path.relative_to(repository))])["hooks"]
    for native, entries in hooks.items():
        assert isinstance(entries, list)
        assert result[native] == entries[1:]
    assert_rerun_keeps_written_hooks(repository, installer, path, changes)


@pytest.mark.parametrize(
    "event,native,message",
    [
        ("session", "SessionStart", "Hard Eng: updating project setup"),
        ("stop", "Stop", "Hard Eng: verifying changes"),
    ],
)
def test_setup_migrates_codex_hook_status_without_duplicate(
    repository: Path, installer: ModuleType, event: str, native: str, message: str
) -> None:
    path = repository / ".codex/hooks.json"
    path.parent.mkdir(parents=True)
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    legacy = {
        "hooks": [
            {"type": "command", "command": f"{command} {event} codex", "timeout": 3600}
        ]
    }
    custom = {"hooks": [{"type": "command", "command": "echo custom"}]}
    path.write_text(json.dumps({"hooks": {native: [legacy, custom]}}))

    changes: dict[str, str] = {}
    installer.configure_hooks(repository, changes)
    result = json.loads(changes[str(path.relative_to(repository))])
    stop_hooks = result["hooks"][native]
    assert legacy not in stop_hooks
    assert custom in stop_hooks
    managed = [
        entry
        for entry in stop_hooks
        if entry.get("hooks", [{}])[0].get("statusMessage")
    ]
    assert managed == [
        {
            "hooks": [
                {
                    "type": "command",
                    "command": f"{command} {event} codex",
                    "timeout": 3600,
                    "statusMessage": message,
                }
            ]
        }
    ]

    assert_rerun_keeps_written_hooks(repository, installer, path, changes)


def test_new_branch_zero_base_compares_with_default_branch(
    repository: Path, shipping_policy: ShippingPolicy
) -> None:
    """A branch's first push changes only its own files, not the whole tree."""
    from gate_config import changed_files

    git(repository, "branch", "-M", "main")
    (repository / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [], "shipping": shipping_policy})
    )
    (repository / "shared.py").write_text("shared = 1\n")
    commit(repository, "default branch base")
    bare = repository.parent / "origin.git"
    git(repository, "init", "--bare", "-q", str(bare))
    git(repository, "remote", "add", "origin", str(bare))
    git(repository, "push", "-q", "origin", "main")
    git(repository, "switch", "-qc", "task")
    (repository / "task.py").write_text("task = 1\n")
    commit(repository, "task work")
    git(repository, "switch", "-q", "main")
    (repository / "later.py").write_text("later = 1\n")
    commit(repository, "default branch moved on")
    git(repository, "push", "-q", "origin", "main")
    everything = {"hard-eng.gates.json", "shared.py", "later.py"}
    assert changed_files(repository, "0" * 40) == everything
    git(repository, "switch", "-q", "task")
    assert changed_files(repository, "0" * 40) == {"task.py"}
    git(repository, "update-ref", "-d", "refs/remotes/origin/main")
    assert changed_files(repository, "0" * 40) == {
        "hard-eng.gates.json",
        "shared.py",
        "task.py",
    }

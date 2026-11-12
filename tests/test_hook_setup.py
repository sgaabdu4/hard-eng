"""Codex hook-configuration conflicts preserve target project settings."""

import ast
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import agent_hooks
import pytest
import update
from conftest import (
    CODEBASE_MEMORY,
    SOURCE,
    commit,
    git,
    init,
    isolate_temporary,
    load_module,
)
from gate_config import JsonObject
from test_setup import repository, snapshot
from test_updates import fixed_revision


def installer_project(repository: Path) -> Path:
    (repository / "package.json").write_text('{"private":true}')
    (repository / "bun.lock").write_text('{"lockfileVersion": 1}\n')
    return repository


def test_hook_registrations_invoke_shared_runner(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "project with spaces"
    root.mkdir()
    repository(root)
    installer.install(root)
    (root / ".hooks/hard-eng.py").write_text(
        "import json, sys\nprint(json.dumps(sys.argv[1:]))\n"
    )
    for agent, path, events in (
        ("claude", ".claude/settings.json", "SessionStart Stop"),
        ("codex", ".codex/hooks.json", "SessionStart Stop"),
    ):
        hooks = json.loads((root / path).read_text())["hooks"]
        if agent == "claude":
            assert hooks.pop("PreToolUse") == [
                agent_hooks.POLL_HOOK,
                agent_hooks.PREVIEW_HOOK,
            ]
            assert hooks.pop("PostToolUseFailure") == [agent_hooks.FAILURE_HOOK]
        assert set(hooks) == set(events.split())
        for event, native in zip(("session", "stop"), events.split(), strict=True):
            (registration,) = hooks[native]
            (handler,) = registration["hooks"]
            command = handler["command"]
            result = subprocess.run(
                ["sh", "-c", command],
                cwd=root / ".hooks",
                check=True,
                capture_output=True,
                text=True,
            )
            assert json.loads(result.stdout) == [event, agent]


@pytest.mark.parametrize(
    ("project", "expected"),
    [
        (
            {},
            {
                "advisorModel": "fable",
                "outputStyle": "Plain STE",
                "attribution": {"commit": "", "pr": "", "sessionUrl": False},
                "autoCompactWindow": 500000,
                "bashOutputMaxChars": 10000,
                "subagentPromptCacheTtl": "1h",
                "env": {"CLAUDE_CODE_FORK_SUBAGENT": "0"},
            },
        ),
        (
            {
                "advisorModel": "opus",
                "outputStyle": "Concise",
                "attribution": {"pr": "By the team"},
                "autoCompactWindow": 300000,
                "bashOutputMaxChars": 30000,
                "subagentPromptCacheTtl": "5m",
                "env": {"CLAUDE_CODE_FORK_SUBAGENT": "1", "OTHER": "x"},
            },
            {
                "advisorModel": "opus",
                "outputStyle": "Concise",
                "attribution": {"pr": "By the team"},
                "autoCompactWindow": 300000,
                "bashOutputMaxChars": 30000,
                "subagentPromptCacheTtl": "5m",
                "env": {"CLAUDE_CODE_FORK_SUBAGENT": "1", "OTHER": "x"},
            },
        ),
        (
            {"env": {"OTHER": "x"}},
            {"env": {"OTHER": "x", "CLAUDE_CODE_FORK_SUBAGENT": "0"}},
        ),
    ],
)
def test_claude_settings_default_fable_advisor_plain_style_and_no_attribution(
    installer: ModuleType,
    repository: Path,
    project: dict[str, object],
    expected: dict[str, object],
) -> None:
    root = installer_project(repository)
    settings = root / ".claude/settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps(project))
    installer.install(root)
    current = json.loads(settings.read_text())
    assert {key: current[key] for key in expected} == expected
    style = (root / ".claude/output-styles/plain-ste.md").read_text()
    assert "\nname: Plain STE\n" in style
    assert "\nkeep-coding-instructions: true\n" in style
    config = json.loads((root / ".claude/output-styles/biome.json").read_text())
    markdown_off = {"includes": ["**/*.md"], "formatter": {"enabled": False}}
    assert markdown_off in config["overrides"]


@pytest.mark.parametrize(
    ("features", "setting"),
    [
        ("hooks = false\n", "hooks"),
        ("codex_hooks = false\n", "codex_hooks"),
    ],
)
def test_project_codex_disabled_hooks_conflict_writes_nothing(
    installer: ModuleType, repository: Path, features: str, setting: str
) -> None:
    root = installer_project(repository)
    config = root / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("[features]\n" + features)
    before = snapshot(root)

    with pytest.raises(
        ValueError, match=rf"project-local .codex/config.toml \[features\].{setting}"
    ):
        installer.install(root)

    assert snapshot(root) == before


@pytest.mark.parametrize(
    "features",
    [
        "",
        "hooks = true\n",
        "codex_hooks = true\n",
        "hooks = true\ncodex_hooks = false\n",
    ],
)
def test_project_codex_enabled_or_unset_hooks_are_allowed(
    installer: ModuleType, repository: Path, features: str
) -> None:
    root = installer_project(repository)
    if features:
        config = root / ".codex/config.toml"
        config.parent.mkdir()
        config.write_text("[features]\n" + features)

    installer.install(root)


def test_failure_hook_runs_its_own_script_and_replaces_the_old_entry(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "project with spaces"
    root.mkdir()
    repository(root)
    old = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py" failure claude'
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUseFailure": [
                        {"hooks": [{"type": "command", "command": old, "timeout": 10}]}
                    ]
                }
            }
        )
    )
    installer.install(root)
    hooks = json.loads((root / ".claude/settings.json").read_text())["hooks"]
    assert hooks["PostToolUseFailure"] == [agent_hooks.FAILURE_HOOK]
    (root / ".hard-eng/sessions").mkdir(parents=True)
    (root / ".hard-eng/sessions/s.json").write_text('{"base": "HEAD", "dirty": {}}')
    payload = json.dumps({"session_id": "s", "tool_name": "Bash", "error": "ERROR: x"})
    printed = [
        subprocess.run(
            ["sh", "-c", agent_hooks.FAILURE_COMMAND],
            cwd=root / ".hooks",
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
            input=payload,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        for _ in range(3)
    ]
    assert printed[:2] == ["", ""]
    assert "Same tool error 3 times" in printed[2]


def test_a_changed_timeout_keeps_one_hook_entry(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    repository(root)
    installer.install(root)
    kept: dict[str, str] = {}
    for name in agent_hooks.HOOK_FILES.values():
        settings = (root / name).read_text()
        changed = re.sub(r'"timeout": (\d+)', r'"timeout": \g<1>1', settings)
        assert changed != settings
        (root / name).write_text(changed)
        kept[name] = changed
    installer.install(root)
    for name, changed in kept.items():
        assert json.loads((root / name).read_text()) == json.loads(changed)


def test_setup_replaces_the_old_tool_hook_commands(
    installer: ModuleType, tmp_path: Path
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    repository(root)
    old = 'python3 "$(git rev-parse --show-toplevel 2>/dev/null)/.hooks/{}.py" 2>/dev/null || true'

    def entry(script: str, matcher: str | None) -> JsonObject:
        handler: JsonObject = {
            "type": "command",
            "command": old.format(script),
            "timeout": 5,
        }
        grouped: JsonObject = {"hooks": [handler]}
        if matcher:
            grouped["matcher"] = matcher
        return grouped

    own = {"hooks": [{"type": "command", "command": "project-guard"}]}
    (root / ".claude").mkdir()
    (root / ".claude/settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PreToolUse": [
                        own,
                        entry("polling", "Bash"),
                        entry("previews", "Artifact"),
                    ],
                    "PostToolUseFailure": [entry("failures", None)],
                }
            }
        )
    )
    installer.install(root)
    installer.install(root)
    hooks = json.loads((root / ".claude/settings.json").read_text())["hooks"]
    assert hooks["PreToolUse"] == [own, *agent_hooks.CLAUDE_TOOL_HOOKS]
    assert hooks["PostToolUseFailure"] == [agent_hooks.FAILURE_HOOK]
    for command in (
        agent_hooks.POLL_COMMAND,
        agent_hooks.PREVIEW_COMMAND,
        agent_hooks.FAILURE_COMMAND,
    ):
        assert command.startswith('python3 "$CLAUDE_PROJECT_DIR/.hooks/')
        assert command.endswith('.py" 2>/dev/null || true')


def test_malformed_project_codex_config_fails_before_writes(
    installer: ModuleType, repository: Path
) -> None:
    root = installer_project(repository)
    config = root / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("[features\n")
    before = snapshot(root)

    with pytest.raises(ValueError, match=r"^\.codex/config\.toml is not valid TOML"):
        installer.install(root)

    assert snapshot(root) == before


@pytest.mark.parametrize("agent", ["copilot", "pi", "opencode"])
def test_installed_cli_rejects_retired_agents(
    installer: ModuleType, repository: Path, agent: str
) -> None:
    root = installer_project(repository)
    installer.install(root)
    result = subprocess.run(
        [sys.executable, str(root / ".hooks/hard-eng.py"), "session", agent],
        cwd=root,
        input="{}",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "invalid choice" in result.stderr
    assert "{claude,codex}" in result.stderr
    assert not (root / ".github/hooks/hard-eng.json").exists()
    assert not (root / ".github/mcp.json").exists()


def test_update_retires_generated_copilot_files_and_preserves_supported_owners(
    installer: ModuleType, repository: Path
) -> None:
    root = installer_project(repository)
    installer.install(root)
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    hooks = root / ".github/hooks/hard-eng.json"
    hooks.parent.mkdir(parents=True, exist_ok=True)
    hooks.write_text(
        json.dumps(
            {
                "version": 1,
                "hooks": {
                    native: [
                        {
                            "type": "command",
                            "bash": f"{command} {event} copilot",
                            "timeoutSec": timeout,
                        }
                    ]
                    for event, native, timeout in (
                        ("session", "sessionStart", 3600),
                        ("failure", "postToolUseFailure", 10),
                        ("stop", "agentStop", 3600),
                        ("tool", "postToolUse", 10),
                    )
                },
            }
        )
    )
    mcp = root / ".github/mcp.json"
    mcp.write_text(
        json.dumps(
            {
                "mcpServers": {
                    "codebase-memory-mcp": CODEBASE_MEMORY,
                    "context-mode": {
                        "command": "pnpm",
                        "args": ["dlx", "context-mode@latest"],
                    },
                    "project": {"command": "project-mcp"},
                }
            }
        )
    )
    claude = root / ".mcp.json"
    current = {"mcpServers": {}}
    current["mcpServers"]["project"] = {"command": "project-mcp"}
    claude.write_text(json.dumps(current))
    before = {
        name: (root / name).read_bytes()
        for name in (
            ".mcp.json",
            ".codex/hooks.json",
            ".claude/settings.json",
            "AGENTS.md",
        )
    }
    changes, links, _, retired = update.update_plan(root, SOURCE, SOURCE)
    assert set(retired) == {".github/hooks/hard-eng.json", ".github/mcp.json"}
    assert changes[".github/hooks/hard-eng.json"] is None
    assert changes[".github/mcp.json"] is None
    update.write_changes(root, changes)
    update.write_links(root, links)
    assert not hooks.exists() and not mcp.exists()
    assert before == {name: (root / name).read_bytes() for name in before}
    stable = snapshot(root)
    installer.install(root)
    assert snapshot(root) == stable


@pytest.mark.parametrize("kind", ["hooks", "mcp"])
def test_unique_retired_configuration_blocks_setup_without_writes(
    installer: ModuleType, repository: Path, kind: str
) -> None:
    root = installer_project(repository)
    relative = ".github/hooks/hard-eng.json" if kind == "hooks" else ".github/mcp.json"
    path = root / relative
    path.parent.mkdir(parents=True)
    value = (
        {
            "version": 1,
            "hooks": {"agentStop": [{"type": "command", "bash": "./project-check"}]},
        }
        if kind == "hooks"
        else {"mcpServers": {"project": {"command": "project-mcp"}}}
    )
    path.write_text(json.dumps(value))
    before = snapshot(root)
    with pytest.raises(ValueError, match="Harness migration required"):
        installer.install(root)
    assert snapshot(root) == before


@pytest.mark.parametrize("kind", ["hooks", "mcp"])
def test_retired_harness_symlinks_preserve_shared_configuration(
    installer: ModuleType, repository: Path, kind: str
) -> None:
    root = installer_project(repository)
    relative = ".github/hooks/hard-eng.json" if kind == "hooks" else ".github/mcp.json"
    shared = root.parent / "shared.json"
    content = json.dumps(
        {"version": 1, "hooks": {}} if kind == "hooks" else {"mcpServers": {}}
    )
    shared.write_text(content)
    path = root / relative
    path.parent.mkdir(parents=True)
    path.symlink_to(shared)
    with pytest.raises(ValueError, match="linked retired harness config"):
        installer.install(root)
    assert path.is_symlink()
    assert shared.read_text() == content
    assert not (root / ".hooks").exists()


OLD_PYTHON = (
    "import runpy, sys\n"
    "sys.version_info = (3, 9, 6, 'final', 0)\n"
    "sys.modules['tomllib'] = None\n"
    "sys.argv = sys.argv[1:]\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def on_old_python(event: str, payload: object) -> subprocess.CompletedProcess[str]:
    entry = str(SOURCE / ".hooks/hard-eng.py")
    return subprocess.run(
        [sys.executable, "-c", OLD_PYTHON, entry, event, "claude"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )


def test_old_python_gets_a_plain_refusal_before_any_import() -> None:
    blocked = on_old_python("stop", {})
    again = on_old_python("stop", {"stop_hook_active": True})
    session = on_old_python("session", {})
    check = on_old_python("check", {})
    ast.parse((SOURCE / ".hooks/hard-eng.py").read_text(), feature_version=(3, 9))
    for run in (blocked, again, session, check):
        assert "Traceback" not in run.stderr, run.stderr
    stop = json.loads(blocked.stdout)
    assert stop["decision"] == "block"
    assert "Python 3.12 or later" in stop["reason"]
    assert "3.9" in stop["reason"]
    for run in (again, session):
        assert run.returncode == 0
        (message,) = json.loads(run.stdout).items()
        assert message == ("systemMessage", stop["reason"])
    assert check.returncode == 1
    assert stop["reason"] in check.stderr


LAUNCHER = SOURCE / ".hooks/hard-eng.py"
LAUNCHER_DRIVER = (
    "import json, os, runpy, sys\n"
    "hooks = sys.argv[1]\n"
    "sys.path.insert(0, hooks)\n"
    "import agent_hooks\n"
    "calls = []\n"
    "agent_hooks.handle_event = lambda root, *event: calls.append(event) or 0\n"
    "before = set(sys.modules)\n"
    "sys.argv = [hooks + '/hard-eng.py', *sys.argv[2:]]\n"
    "try:\n"
    "    runpy.run_path(sys.argv[0], run_name='__main__')\n"
    "except SystemExit as stop:\n"
    "    code = stop.code\n"
    "gate = [n for n in set(sys.modules) - before if os.path.isfile(f'{hooks}/{n}.py')]\n"
    "print(json.dumps([code, calls, sorted(gate)]))\n"
)
ERROR_DRIVER = (
    "import runpy, sys\n"
    "hooks = sys.argv[1]\n"
    "sys.path.insert(0, hooks)\n"
    "import gate_runner\n"
    "def main():\n"
    "    raise ValueError('boom')\n"
    "gate_runner.main = main\n"
    "sys.argv = [hooks + '/hard-eng.py', 'check']\n"
    "runpy.run_path(sys.argv[0], run_name='__main__')\n"
)


def drive(driver: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", driver, str(LAUNCHER.parent), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_hook_script_is_a_small_launcher() -> None:
    text = LAUNCHER.read_text()
    assert len(text.splitlines()) <= 45
    assert not [
        node
        for node in ast.walk(ast.parse(text))
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    ]


@pytest.mark.parametrize("event", ["session", "stop"])
def test_a_hook_event_loads_no_gate_module(event: str) -> None:
    run = drive(LAUNCHER_DRIVER, event, "claude")
    assert run.returncode == 0, run.stderr
    code, calls, loaded = json.loads(run.stdout)
    assert (code, calls, loaded) == (0, [[event, "claude"]], [])


EVENT_DRIVER = (
    "import io, json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import agent_hooks\n"
    "sys.stdin = io.StringIO(json.dumps({'session_id': 'loads'}))\n"
    "agent_hooks.handle_event(Path(sys.argv[2]), sys.argv[3], 'claude')\n"
    "print(json.dumps(sorted(set(sys.modules) & set(sys.argv[4:]))))\n"
)
UNUSED_MODULES = ["hashlib", "urllib.request", "ssl", "update", "mcp_setup"]
# A session start gives Git a temporary file of names; a clean Stop does not.
UNUSED_AT_STOP = [*UNUSED_MODULES, "tempfile", "shutil"]


@pytest.mark.parametrize("event", ["session", "stop"])
def test_a_clean_hook_event_loads_no_module_that_it_does_not_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, event: str
) -> None:
    isolate_temporary(tmp_path, monkeypatch)
    root = tmp_path / "project"
    init(root)
    for name in ("PRODUCT.md", "DESIGN.md"):
        (root / name).write_bytes((SOURCE / name).read_bytes())
    (root / ".hooks").mkdir()
    (root / update.SOURCE_FILE).write_text("{}\n")
    gate = {"name": "check", "command": ["python3", "-c", "pass"]}
    (root / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [gate]})
    )
    (root / ".git/info/exclude").write_text(".hard-eng/\n")
    commit(root, "installed files")
    started = drive(EVENT_DRIVER, str(root), "session", *UNUSED_MODULES)
    run = (
        started
        if event == "session"
        else drive(EVENT_DRIVER, str(root), "stop", *UNUSED_AT_STOP)
    )
    assert run.returncode == 0, run.stderr
    output, loaded = run.stdout.splitlines()
    expected = "Gates: ok." if event == "session" else "no code checks run"
    assert expected in output
    assert json.loads(loaded) == []


def test_a_command_runs_through_the_launcher() -> None:
    help_text = drive(
        "import runpy, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "sys.argv = [sys.argv[1] + '/hard-eng.py', '--help']\n"
        "runpy.run_path(sys.argv[0], run_name='__main__')\n"
    )
    assert help_text.returncode == 0, help_text.stderr
    assert "check" in help_text.stdout
    failed = drive(ERROR_DRIVER)
    assert failed.returncode == 1
    assert failed.stderr.splitlines() == ["Hard Eng: boom"]


def test_a_load_of_the_launcher_runs_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_arguments: object) -> int:
        raise AssertionError("a load must run nothing")

    monkeypatch.setattr(agent_hooks, "handle_event", refuse)
    monkeypatch.setitem(sys.modules, "gate_runner", None)
    for arguments in (["check"], ["session", "claude"], ["stop", "codex"]):
        monkeypatch.setattr(sys, "argv", [str(LAUNCHER), *arguments])
        load_module("launcher", LAUNCHER)


def test_an_update_from_a_release_with_the_long_script_installs_the_launcher_and_the_module(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source, target, _ = release
    launcher = (source / ".hooks/hard-eng.py").read_bytes()
    module = (source / ".hooks/gate_runner.py").read_bytes()
    long_script = module + b"\n\nif __name__ == '__main__':\n    run()\n"
    for root in (source, target):
        (root / ".hooks/hard-eng.py").write_bytes(long_script)
        (root / ".hooks/gate_runner.py").unlink()
    git(source, "add", ".hooks")
    git(source, "commit", "-qm", "release with the long script")
    (target / update.SOURCE_FILE).write_text(
        json.dumps({"revision": git(source, "rev-parse", "HEAD")}) + "\n"
    )
    commit(target, "release with the long script")
    (source / ".hooks/hard-eng.py").write_bytes(launcher)
    (source / ".hooks/gate_runner.py").write_bytes(module)
    revision = commit(source, "verified update")
    monkeypatch.setattr(update, "latest_verified", fixed_revision(revision))

    assert "Updated Hard Eng" in update.update(target)
    for name, content in (("hard-eng.py", launcher), ("gate_runner.py", module)):
        assert (target / ".hooks" / name).read_bytes() == content
    first = subprocess.run(
        [sys.executable, ".hooks/hard-eng.py", "impact", "--base", "HEAD"],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    assert first.returncode == 0, first.stderr
    assert "docs_only" in first.stdout


def test_python_floor_has_one_value() -> None:
    major, minor = load_module("launcher", LAUNCHER).PYTHON_FLOOR
    project = tomllib.loads((SOURCE / "pyproject.toml").read_text())["project"]
    assert project["requires-python"] == f">={major}.{minor}"
    assert f"Python {major}.{minor} or later" in (SOURCE / "README.md").read_text()

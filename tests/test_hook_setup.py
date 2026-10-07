"""Codex hook-configuration conflicts preserve target project settings."""

import json
import subprocess
import sys
import tomllib
from pathlib import Path
from types import ModuleType

import pytest
import update
from conftest import CODEBASE_MEMORY, SOURCE
from test_setup import repository, snapshot


def installer_project(repository: Path) -> Path:
    (repository / "package.json").write_text('{"private":true}')
    (repository / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
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
        ("claude", ".claude/settings.json", "SessionStart PostToolUseFailure Stop"),
        ("codex", ".codex/hooks.json", "SessionStart Stop"),
    ):
        hooks = json.loads((root / path).read_text())["hooks"]
        assert set(hooks) == set(events.split())
        calls = {
            "codex": ("session", "stop"),
            "claude": ("session", "failure", "stop"),
        }[agent]
        for event, native in zip(calls, events.split(), strict=True):
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
                "attribution": {"commit": "", "pr": "", "sessionUrl": False},
            },
        ),
        (
            {"advisorModel": "opus", "attribution": {"pr": "By the team"}},
            {"advisorModel": "opus", "attribution": {"pr": "By the team"}},
        ),
    ],
)
def test_claude_settings_default_fable_advisor_and_no_attribution(
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


def test_malformed_project_codex_config_fails_before_writes(
    installer: ModuleType, repository: Path
) -> None:
    root = installer_project(repository)
    config = root / ".codex/config.toml"
    config.parent.mkdir()
    config.write_text("[features\n")
    before = snapshot(root)

    with pytest.raises(tomllib.TOMLDecodeError):
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

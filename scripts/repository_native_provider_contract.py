"""Provider-specific repository-native startup contracts."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from subprocess import CompletedProcess

RepositoryInitializer = Callable[..., None]
GlobalInstaller = Callable[[Path, Path, str], None]
Launcher = Callable[..., CompletedProcess[str]]
Writer = Callable[[Path, str | bytes, int], None]


def assert_provider_adapters(
    root: Path,
    env: dict[str, str],
    release_root: Path,
    init_repository: RepositoryInitializer,
    install_global: GlobalInstaller,
    launcher: Launcher,
    write: Writer,
) -> None:
    for agent in ("claude", "copilot"):
        for global_install in (False, True):
            case = root / f"{agent}-g{int(global_install)}"
            repository = case / "repository"
            home = case / "home"
            home.mkdir(parents=True)
            init_repository(repository, marked=True)
            if global_install:
                install_global(home, release_root, agent)
            value = json.loads(launcher(repository, home, env, agent=agent).stdout)
            assert value["mode"] == ("global" if global_install else "fallback")
            command = value["command"]
            assert ("--mcp-config" if agent == "claude" else "--additional-mcp-config") in command
            if global_install:
                assert not (repository / ".agents/hard-eng").exists()
                if agent == "claude":
                    settings_path = home / ".claude/settings.json"
                    settings = json.loads(settings_path.read_text(encoding="utf-8"))
                    settings["outputStyle"] = "plain-english"
                    settings["unrelatedStyleNote"] = "Plain English"
                    write(settings_path, json.dumps(settings), 0o644)
                    invalid_style = launcher(repository, home, env, agent="claude", check=False)
                    assert invalid_style.returncode == 1
                    assert "plain-English output style is missing" in invalid_style.stderr
                continue
            if agent == "claude":
                assert (repository / ".claude/settings.local.json").is_file()
                assert (repository / "CLAUDE.local.md").read_text(encoding="utf-8") == "@AGENTS.override.md\n"
                claude_settings = json.loads((repository / ".claude/settings.local.json").read_text(encoding="utf-8"))
                assert claude_settings["outputStyle"] == "Plain English"
                invalid_trust = launcher(
                    repository, home, env, agent="claude", trust_repository_hooks=True, check=False
                )
                assert invalid_trust.returncode == 1
                assert "only valid with Copilot" in invalid_trust.stderr
            else:
                assert (repository / ".github/hooks/hard-eng.json").is_file()
                assert (repository / ".agents/hard-eng/copilot-instructions/AGENTS.md").is_file()
                for prompt_arguments in (
                    ("-p", "return only ok"),
                    ("--prompt", "return only ok"),
                    ("--prompt=return only ok",),
                ):
                    untrusted = launcher(
                        repository, home, env, agent="copilot", agent_arguments=prompt_arguments, check=False
                    )
                    assert untrusted.returncode == 1
                    assert "--trust-repository-hooks" in untrusted.stderr
                copilot_bin = case / "copilot-bin"
                copilot_bin.mkdir()
                write(
                    copilot_bin / "copilot",
                    "#!/bin/sh\nprintf '%s\\n' \"${GITHUB_COPILOT_PROMPT_MODE_REPO_HOOKS-unset}\"\n",
                    0o755,
                )
                trusted_environment = dict(env)
                trusted_environment["PATH"] = os.pathsep.join((str(copilot_bin), trusted_environment["PATH"]))
                trusted = launcher(
                    repository,
                    home,
                    trusted_environment,
                    agent="copilot",
                    agent_arguments=("-p", "return only ok"),
                    trust_repository_hooks=True,
                    dry_run=False,
                )
                assert trusted.stdout.strip() == "true"

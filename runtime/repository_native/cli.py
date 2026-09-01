"""Command-line entry for repository-native Hard Eng startup."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
from pathlib import Path

from . import SUPPORTED_AGENTS
from .errors import ConfigurationError, HardEngError
from .models import PreparedState
from .release import installed_status, prepare_release
from .repository import inspect_global, inspect_repository, require_claude_owner
from .wiring import install_wiring, preflight_wiring, uninstall_wiring, verify_wiring


def _home(value: str | None) -> Path:
    selected = Path(value).expanduser() if value else Path.home()
    return selected.resolve()


def _prepare(start: Path, home: Path, agent: str) -> tuple[PreparedState, Path | None]:
    repository = inspect_repository(start)
    if not repository.marked:
        return (PreparedState("pass-through", repository.root, None, None, None, None, None, "not-marked"), None)
    if agent == "claude":
        require_claude_owner(repository.root)
    global_state = inspect_global(home, agent)
    if global_state.mode == "broken":
        details = "\n  - ".join(global_state.problems)
        raise ConfigurationError(
            "a partial or broken global Hard Eng install was found; fallback was not activated.\n"
            f"  - {details}\nRun {global_state.root / 'setup.sh'} install to repair it."
        )
    if global_state.mode == "global":
        return (
            PreparedState(
                "global",
                repository.root,
                global_state.root,
                global_state.identity,
                None,
                repository.policy.channel if repository.policy else None,
                None,
                "global-health-verified",
            ),
            None,
        )
    if repository.policy is None:
        raise ConfigurationError("no global Hard Eng exists and hard-eng.gates.json has no hard_eng release policy")
    preflight_wiring(repository.root)
    active = prepare_release(repository.root, repository.policy, repository.marker_digest or "", agent=agent)
    mcp = install_wiring(repository.root, repository.root / ".agents/hard-eng/current")
    return (
        PreparedState(
            "fallback",
            repository.root,
            active.root,
            active.version,
            active.source_commit,
            repository.policy.channel,
            active.newest_allowed_version,
            active.last_check,
        ),
        mcp,
    )


def _codex_hook_is_exclusive(repository: Path) -> bool:
    path = repository / ".codex/hooks.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    hooks = value.get("hooks") if isinstance(value, dict) else None
    if not isinstance(hooks, dict):
        return False
    commands: list[str] = []
    for entries in hooks.values():
        if not isinstance(entries, list):
            return False
        for entry in entries:
            if not isinstance(entry, dict) or not isinstance(entry.get("hooks"), list):
                return False
            for hook in entry["hooks"]:
                if not isinstance(hook, dict) or not isinstance(hook.get("command"), str):
                    return False
                commands.append(hook["command"])
    expected = repository / ".agents/hard-eng/current/scripts/hooks/agent-hook.sh"

    def points_to_expected(token: str) -> bool:
        path = Path(token)
        if path.name != "agent-hook.sh":
            return False
        try:
            return path.samefile(expected)
        except OSError:
            return False

    for command in commands:
        try:
            tokens = shlex.split(command)
        except ValueError:
            return False
        if not any(points_to_expected(token) for token in tokens):
            return False
    return bool(commands)


def _agent_command(
    agent: str, arguments: list[str], state: PreparedState, mcp: Path | None, isolated_home: Path | None = None
) -> tuple[list[str], dict[str, str]]:
    command = [agent]
    environment = dict(os.environ)
    environment.update(
        {
            "HARD_ENG_MODE": state.mode,
            "HARD_ENG_REPOSITORY": str(state.repository),
            "HARD_ENG_VERSION": state.version or "none",
        }
    )
    if state.hard_eng_root:
        environment["HARD_ENG_ROOT"] = str(state.hard_eng_root)
    if isolated_home is not None:
        environment["HOME"] = str(isolated_home)
        environment["CODEX_HOME"] = str(isolated_home / ".codex")
        environment["CLAUDE_CONFIG_DIR"] = str(isolated_home / ".claude")
        environment["COPILOT_HOME"] = str(isolated_home / ".copilot")
    if state.mode in {"fallback", "global"} and state.hard_eng_root is not None:
        server = state.hard_eng_root / "runtime/repository_native/mcp_server.py"
        inline_mcp = json.dumps(
            {
                "mcpServers": {
                    "hard-eng": {"args": [str(server), "--repo", str(state.repository)], "command": "python3"}
                }
            },
            separators=(",", ":"),
        )
        if agent == "codex":
            if state.mode == "fallback" and _codex_hook_is_exclusive(state.repository):
                command.append("--dangerously-bypass-hook-trust")
            command.extend(
                [
                    "-c",
                    'mcp_servers.hard_eng.command="python3"',
                    "-c",
                    f"mcp_servers.hard_eng.args={json.dumps([str(server), '--repo', str(state.repository)])}",
                ]
            )
        elif agent == "claude":
            command.extend(["--mcp-config", str(mcp) if mcp is not None else inline_mcp])
        elif agent == "copilot":
            command.extend(["--additional-mcp-config", f"@{mcp}" if mcp is not None else inline_mcp])
            if mcp is not None:
                custom = state.repository / ".agents/hard-eng/copilot-instructions"
                existing = environment.get("COPILOT_CUSTOM_INSTRUCTIONS_DIRS")
                environment["COPILOT_CUSTOM_INSTRUCTIONS_DIRS"] = (
                    str(custom) if not existing else os.pathsep.join((str(custom), existing))
                )
    command.extend(arguments)
    return command, environment


def _print_state(state: PreparedState, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(state.json_value(), sort_keys=True, separators=(",", ":")))
        return
    print(f"repository: {state.repository}")
    print(f"mode: {state.mode}")
    print(f"version: {state.version or 'none'}")
    print(f"source commit: {state.source_commit or 'none'}")
    print(f"channel: {state.channel or 'none'}")
    print(f"newest allowed version: {state.newest_allowed_version or 'unknown'}")
    print(f"update check: {state.last_check}")


def _command_prepare(arguments: argparse.Namespace) -> int:
    state, _ = _prepare(Path(arguments.repo or os.getcwd()), _home(arguments.home), arguments.agent)
    _print_state(state, json_output=arguments.json)
    return 0


def _command_start(arguments: argparse.Namespace) -> int:
    selected_home = _home(arguments.home)
    state, mcp = _prepare(Path(arguments.repo or os.getcwd()), selected_home, arguments.agent)
    agent_arguments = list(arguments.agent_arguments)
    if agent_arguments and agent_arguments[0] == "--":
        agent_arguments.pop(0)
    command, environment = _agent_command(
        arguments.agent, agent_arguments, state, mcp, selected_home if arguments.home else None
    )
    if arguments.dry_run:
        value = state.json_value()
        value["command"] = command
        print(json.dumps(value, sort_keys=True, separators=(",", ":")))
        return 0
    if state.last_check.startswith("update-failed-using-verified-cache:"):
        print(f"hard-eng: WARNING: {state.last_check}", file=sys.stderr)
    elif state.last_check == "offline-cache":
        print("hard-eng: WARNING: GitHub was unavailable; using the matching verified cache", file=sys.stderr)
    os.chdir(state.repository)
    try:
        os.execvpe(command[0], command, environment)
    except OSError as error:
        raise ConfigurationError(f"could not start {arguments.agent}: {error}") from error
    return 127


def _command_status(arguments: argparse.Namespace) -> int:
    repository = inspect_repository(Path(arguments.repo or os.getcwd()))
    if not repository.marked:
        state = PreparedState("pass-through", repository.root, None, None, None, None, None, "not-marked")
    else:
        global_state = inspect_global(_home(arguments.home), arguments.agent)
        if global_state.mode == "global":
            state = PreparedState(
                "global",
                repository.root,
                global_state.root,
                global_state.identity,
                None,
                repository.policy.channel if repository.policy else None,
                None,
                "global-health-verified",
            )
        elif global_state.mode == "broken":
            raise ConfigurationError("global Hard Eng is broken: " + "; ".join(global_state.problems))
        else:
            current = repository.root / ".agents/hard-eng/current"
            if current.is_symlink():
                if repository.policy is None or repository.marker_digest is None:
                    raise ConfigurationError("fallback release policy is missing")
                active = installed_status(
                    repository.root / ".agents/hard-eng", repository.policy, repository.marker_digest
                )
                if active is None:
                    raise ConfigurationError("fallback release state is incomplete or changed")
                verify_wiring(repository.root, current)
                state = PreparedState(
                    "fallback",
                    repository.root,
                    active.root,
                    active.version,
                    active.source_commit,
                    repository.policy.channel if repository.policy else None,
                    active.newest_allowed_version,
                    active.last_check,
                )
            else:
                state = PreparedState(
                    "unprotected",
                    repository.root,
                    None,
                    None,
                    None,
                    repository.policy.channel if repository.policy else None,
                    None,
                    "not-prepared",
                )
    _print_state(state, json_output=arguments.json)
    return 0


def _command_uninstall(arguments: argparse.Namespace) -> int:
    repository = inspect_repository(Path(arguments.repo or os.getcwd()))
    local = repository.root / ".agents/hard-eng"
    current = local / "current"
    if not current.is_symlink():
        print("Hard Eng repository fallback is not installed")
        return 0
    payload = current
    uninstall_wiring(repository.root, payload)
    if local.is_symlink() or not local.is_dir():
        raise ConfigurationError(f"fallback root is unsafe: {local}")
    if not current.is_symlink():
        raise ConfigurationError("fallback current link changed during uninstall")
    current.unlink()
    last_check = local / "last-check.json"
    if last_check.is_symlink() or (last_check.exists() and not last_check.is_file()):
        raise ConfigurationError(f"fallback update state is unsafe: {last_check}")
    if last_check.is_file():
        last_check.unlink()
    print(f"deactivated Hard Eng fallback in {repository.root}; verified release cache retained")
    return 0


def _add_common(parser: argparse.ArgumentParser, *, agent: bool = True) -> None:
    parser.add_argument("--repo")
    parser.add_argument("--home")
    if agent:
        parser.add_argument("--agent", choices=SUPPORTED_AGENTS, default="codex")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="hard-eng")
    root.add_argument("--version", action="version", version="hard-eng launcher 1")
    commands = root.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    _add_common(prepare)
    prepare.add_argument("--json", action="store_true")
    prepare.set_defaults(action=_command_prepare)
    start = commands.add_parser("start")
    start.add_argument("agent", choices=SUPPORTED_AGENTS)
    start.add_argument("agent_arguments", nargs=argparse.REMAINDER)
    start.add_argument("--repo")
    start.add_argument("--home")
    start.add_argument("--dry-run", action="store_true")
    start.set_defaults(action=_command_start)
    status = commands.add_parser("status")
    _add_common(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(action=_command_status)
    uninstall = commands.add_parser("uninstall")
    _add_common(uninstall, agent=False)
    uninstall.set_defaults(action=_command_uninstall)
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = parser().parse_args(argv)
        return int(arguments.action(arguments))
    except HardEngError as error:
        print(f"hard-eng: FAIL: {error}", file=sys.stderr)
        return 1

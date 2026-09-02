"""Command-line entry for repository-native Hard Eng."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import SUPPORTED_AGENTS
from .errors import ConfigurationError, HardEngError
from .installer import install_global, install_repository
from .models import PreparedState
from .prepare import prepare, remove_fallback, remove_shared, share, status
from .repository import find_repository, inspect_repository

INSTALL_USAGE = """Usage:
  npx -y github:sgaabdu4/hard-eng --global
  npx -y github:sgaabdu4/hard-eng --repo [--ignore | --shared]

--global installs, updates, or repairs Hard Eng for this computer.
--repo prepares the Git repository and stages its three repository-owned files.
--ignore keeps untracked repository-owned files private to this checkout.
--shared pins one Hard Eng release and stages the bootstrap, hooks, and rules so every clone gets them.
"""


def _home(value: str | None) -> Path:
    selected = Path(value).expanduser() if value else Path.home()
    return selected.resolve()


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
    print(f"wiring: {state.wiring}")


def _command_prepare(arguments: argparse.Namespace) -> int:
    start = Path(arguments.repo or os.getcwd())
    home = _home(arguments.home)
    if arguments.shared:
        state = share(start, home, arguments.agent)
    else:
        state = prepare(start, home, arguments.agent)
    _print_state(state, json_output=arguments.json)
    return 0


def _command_status(arguments: argparse.Namespace) -> int:
    state = status(Path(arguments.repo or os.getcwd()), _home(arguments.home), arguments.agent)
    _print_state(state, json_output=arguments.json)
    return 0


def _command_update(arguments: argparse.Namespace) -> int:
    if not arguments.shared:
        raise ConfigurationError(
            "update moves a shared release pin: add --shared; a global install updates with "
            "`npx -y github:sgaabdu4/hard-eng --global`"
        )
    state = share(Path(arguments.repo or os.getcwd()), _home(arguments.home), arguments.agent, repin=True)
    _print_state(state, json_output=arguments.json)
    return 0


def _command_uninstall(arguments: argparse.Namespace) -> int:
    root = find_repository(Path(arguments.repo or os.getcwd()))
    if arguments.shared:
        if remove_shared(root):
            print(f"removed the shared Hard Eng wiring from {root}; commit the deletions to remove it from every clone")
        else:
            print("Hard Eng shared wiring is not installed")
        return 0
    repository = inspect_repository(root)
    if repository.policy is not None and repository.policy.shared:
        raise ConfigurationError("this repository commits shared Hard Eng wiring; run `hard-eng uninstall --shared`")
    if remove_fallback(root):
        print(f"deactivated Hard Eng fallback in {root}; verified release cache retained")
    else:
        print("Hard Eng repository fallback is not installed")
    return 0


def _command_install(arguments: argparse.Namespace) -> int:
    if arguments.help:
        print(INSTALL_USAGE, end="")
        return 0
    if arguments.global_mode and arguments.repo_mode:
        raise ConfigurationError("choose one of --global or --repo")
    if not arguments.global_mode and not arguments.repo_mode:
        raise ConfigurationError("choose --global or --repo")
    if arguments.ignore and not arguments.repo_mode:
        raise ConfigurationError("--ignore works only with --repo")
    if arguments.shared and not arguments.repo_mode:
        raise ConfigurationError("--shared works only with --repo")
    if arguments.ignore and arguments.shared:
        raise ConfigurationError("choose one of --ignore or --shared")
    home = _home(arguments.home)
    if arguments.global_mode:
        return install_global(home)
    return install_repository(Path(os.getcwd()), home, private=arguments.ignore, shared=arguments.shared)


def _add_common(parser: argparse.ArgumentParser, *, agent: bool = True) -> None:
    parser.add_argument("--repo")
    parser.add_argument("--home")
    if agent:
        parser.add_argument("--agent", choices=SUPPORTED_AGENTS, default="codex")


class _InstallParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        raise ConfigurationError(message.replace("unrecognized arguments:", "unknown option:"))


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="hard-eng")
    root.add_argument("--version", action="version", version="hard-eng launcher 1")
    commands = root.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare")
    _add_common(prepare_parser)
    prepare_parser.add_argument("--json", action="store_true")
    prepare_parser.add_argument("--shared", action="store_true")
    prepare_parser.set_defaults(action=_command_prepare)
    status_parser = commands.add_parser("status")
    _add_common(status_parser)
    status_parser.add_argument("--json", action="store_true")
    status_parser.set_defaults(action=_command_status)
    update = commands.add_parser("update")
    _add_common(update)
    update.add_argument("--json", action="store_true")
    update.add_argument("--shared", action="store_true")
    update.set_defaults(action=_command_update)
    uninstall = commands.add_parser("uninstall")
    _add_common(uninstall, agent=False)
    uninstall.add_argument("--shared", action="store_true")
    uninstall.set_defaults(action=_command_uninstall)
    install = commands.add_parser("install", add_help=False)
    _add_install_options(install)
    install.set_defaults(action=_command_install)
    return root


def _add_install_options(install: argparse.ArgumentParser) -> None:
    install.add_argument("--global", dest="global_mode", action="store_true")
    install.add_argument("--repo", dest="repo_mode", action="store_true")
    install.add_argument("--ignore", action="store_true")
    install.add_argument("--shared", action="store_true")
    install.add_argument("--home")
    install.add_argument("-h", "--help", action="store_true")


def main(argv: list[str] | None = None) -> int:
    selected = list(sys.argv[1:] if argv is None else argv)
    try:
        if selected[:1] == ["install"]:
            arguments = _InstallParser(prog="hard-eng install", add_help=False)
            _add_install_options(arguments)
            return _command_install(arguments.parse_args(selected[1:]))
        parsed = parser().parse_args(selected)
        return int(parsed.action(parsed))
    except HardEngError as error:
        print(f"hard-eng: FAIL: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("hard-eng: interrupted", file=sys.stderr)
        return 130

"""Small public command surface."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from hard_eng import agents, config, git_hooks, hooks, mcp, runner, setup, tools
from hard_eng.common import GateError, checked, parse_json, repository, run


def parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(description="Run repository-owned Hard Eng gates")
    cli.add_argument("--repo", type=Path, default=Path.cwd())
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Run all applicable checks")
    commands.add_parser("validate", help="Validate the repository gate configuration")
    install = commands.add_parser(
        "install", help="Install Hard Eng locally after adapting the gate configuration"
    )
    install.add_argument("--agent", action="append", choices=agents.AGENTS, default=[])
    configure = commands.add_parser("configure", help="Configure a repository-local agent adapter")
    configure.add_argument("agent", choices=agents.AGENTS)
    commands.add_parser("update", help="Install and separately commit the newest verified main revision")
    commands.add_parser("mcp-check", help="Prove real repository-local MCP tool calls")
    commands.add_parser("session", help="Update and verify MCP readiness before project work")
    hook = commands.add_parser("hook", help="Handle a native agent lifecycle event")
    hook.add_argument("agent", choices=agents.AGENTS)
    hook.add_argument("event", choices=agents.EVENTS)
    server = commands.add_parser("mcp", help="Launch a repository-local MCP server over stdio")
    server.add_argument("name", choices=mcp.SERVERS)
    push = commands.add_parser("pre-push", help="Run gates on the actual committed trees being pushed")
    push.add_argument("remote", nargs="?")
    push.add_argument("url", nargs="?")
    tool = commands.add_parser("tool", help="Run the latest managed scanner in a repository-local cache")
    tool.add_argument("name", choices=sorted(tools.PYTHON | tools.NODE | tools.NATIVE))
    tool.add_argument("args", nargs=argparse.REMAINDER)
    return cli


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        root = repository(args.repo)
        if lifecycle(args, root):
            return 0
        if args.command == "pre-push":
            git_hooks.check_push(root, sys.stdin.read())
            return 0
        if args.command == "tool":
            tool = tools.resolve(root, args.name)
            result = run(list(tool.command) + args.args, root, 1800, input_text=sys.stdin.read())
            print(result.stdout, end="")
            print(result.stderr, end="", file=sys.stderr)
            return result.returncode
        project = config.load(root)
        if args.command == "check":
            runner.check_all(project)
        else:
            print(f"PASS: {len(project.packages)} supported packages")
    except (GateError, OSError, ValueError) as error:
        if args.command == "hook" and args.event in {"PreToolUse", "Stop"}:
            print(json.dumps(hooks.output(args.agent, args.event, f"Hard Eng hook failed: {error}", True)))
            return 0
        print(f"hard-eng: {error}", file=sys.stderr)
        return 1
    return 0


def lifecycle(args: argparse.Namespace, root: Path) -> bool:
    if args.command == "hook":
        event = parse_json(sys.stdin.read(), "native hook input")
        print(json.dumps(hooks.handle(root, args.agent, args.event, event)))
    elif args.command == "session":
        print(hooks.session(root))
    elif args.command == "mcp":
        mcp.serve(root, args.name)
    elif args.command == "mcp-check":
        mcp.readiness(root)
    elif args.command == "install":
        install(root, args.agent)
    elif args.command == "configure":
        agents.configure(root, args.agent)
    elif args.command == "update":
        print(setup.update(root))
    else:
        return False
    return True


def install(root: Path, selected: list[str]) -> None:
    setup.install(root)
    for agent in selected or agents.AGENTS:
        agents.configure(root, agent)
        if agent == "claude" and shutil.which("claude"):
            checked(
                ["claude", "plugin", "install", "context-mode@context-mode", "--scope", "project"],
                root,
                180,
            )
    result = run(["python3", str(root / ".agents/hard-eng/bin/hard-eng"), "mcp-check"], root, 240)
    if result.returncode:
        raise GateError("Installed MCP readiness failed; run mcp-check to diagnose and repair it")
    print(result.stdout, end="")

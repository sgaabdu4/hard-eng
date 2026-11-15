"""Start one agent session per client, kept apart from the user's own agent setup."""

import argparse
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Literal, NamedTuple

from agent_actions import Action, claude_actions, codex_actions
from challenge import without_host_markers
from process_group import run_in_group

Access = Literal["grader", "sandboxed", "approved"]


class Agent(NamedTuple):
    """What one client run observably produced; incomplete runs are never judged."""

    completed: bool
    message: str
    settings: dict[str, object]
    problems: list[str]
    actions: list[Action]


class Ready(NamedTuple):
    """The client's version, and why it cannot run, if it cannot."""

    version: str | None
    blocker: str | None


class Client(NamedTuple):
    model: str
    preflight: Callable[[], Ready]
    run: Callable[[Path, Path, argparse.Namespace, str, Access], Agent]
    isolation: str


def events(path: Path) -> list[dict[str, object]]:
    parsed = [
        json.loads(line)
        for line in path.read_text().splitlines()
        if line.startswith("{")
    ]
    return [event for event in parsed if isinstance(event, dict)]


def stream(
    command: list[str],
    root: Path,
    evidence: Path,
    timeout: int,
    overrides: dict[str, str] | None = None,
) -> list[dict[str, object]] | None:
    """The client's JSON event stream, or None when it exceeded the timeout."""
    try:
        with (
            (evidence / "events.jsonl").open("w") as out,
            (evidence / "stderr.log").open("w") as err,
        ):
            run_in_group(
                command,
                cwd=root,
                env={**without_host_markers(), **(overrides or {})},
                stdin=subprocess.DEVNULL,
                stdout=out,
                stderr=err,
                timeout=timeout,
            )
    except subprocess.TimeoutExpired:
        return None
    return events(evidence / "events.jsonl")


def mcp_calls(found: list[dict[str, object]]) -> list[str]:
    """MCP tools the agent actually called, as recorded in its event stream."""
    calls: list[str] = []
    for event in found:
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "mcp_tool_call"
        ):
            calls.append(
                f"{item.get('server')}.{item.get('tool')}: {item.get('status')}"
            )
    return calls


def codex_settings(home: Path, thread: object, evidence: Path) -> dict[str, object]:
    """The model and policies Codex recorded for the turn, with the session copied as evidence."""
    sessions: list[Path] = (
        sorted((home / "sessions").rglob(f"rollout-*{thread}.jsonl"))
        if isinstance(thread, str)
        else []
    )
    if not sessions:
        return {"unavailable": "Codex session record not found"}
    shutil.copyfile(sessions[-1], evidence / "session.jsonl")
    for event in events(sessions[-1]):
        payload = event.get("payload")
        if event.get("type") == "turn_context" and isinstance(payload, dict):
            keys = ("model", "effort", "sandbox_policy", "approval_policy")
            return {key: payload.get(key) for key in keys}
    return {"unavailable": "Codex session record has no turn context"}


def codex_run(
    root: Path, evidence: Path, options: argparse.Namespace, prompt: str, access: Access
) -> Agent:
    # A fresh home shares only the login; user memories, MCP, hooks, plugins and instructions stay out.
    home = root.parent / "codex-home"
    home.mkdir()
    user = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    (home / "auth.json").symlink_to(user / "auth.json")
    (home / "config.toml").write_text(f'[projects."{root}"]\ntrust_level = "trusted"\n')
    command = [
        "codex",
        "exec",
        "--json",
        "--cd",
        str(root),
        "--model",
        options.model,
        "--config",
        f'model_reasoning_effort="{options.effort}"',
        *codex_access(root, access),
        "--output-last-message",
        str(evidence / "last-message.md"),
        prompt,
    ]
    found = stream(command, root, evidence, options.timeout, {"CODEX_HOME": str(home)})
    if found is None:
        return Agent(False, "", {}, [f"codex exec exceeded {options.timeout}s"], [])
    thread = next((e.get("thread_id") for e in found if "thread_id" in e), None)
    settings = codex_settings(home, thread, evidence)
    settings["mcp_calls"] = mcp_calls(found)
    return Agent(
        any(event.get("type") == "turn.completed" for event in found),
        "\n\n".join(
            str(item.get("text"))
            for event in found
            if event.get("type") == "item.completed"
            and isinstance(item := event.get("item"), dict)
            and item.get("type") == "agent_message"
        ),
        settings,
        [
            json.dumps(e)[:500]
            for e in found
            if e.get("type") in {"turn.failed", "error"}
        ],
        codex_actions(found),
    )


def codex_access(root: Path, access: Access) -> list[str]:
    """Agents get a writable .git and unreviewed project hooks; graders read nothing."""
    if access == "grader":
        return ["--sandbox", "read-only", "--skip-git-repo-check", "--ephemeral"]
    flags = ["--add-dir", str(root / ".git"), "--dangerously-bypass-hook-trust"]
    if access == "approved":
        # No sandbox starts Chrome; --approve-for-me sets workspace-write and refuses --sandbox.
        return [*flags, "--approve-for-me"]
    return ["--sandbox", "workspace-write", *flags]


def claude_access(access: Access) -> tuple[str, str]:
    """The settings and permission mode; an approved case may ask auto mode to leave the sandbox."""
    approved = access == "approved"
    return claude_isolation(escape=approved), "auto" if approved else "acceptEdits"


def claude_isolation(*, escape: bool) -> str:
    """Turn off the user's plugins and keep Bash in a sandbox without network."""
    user = Path.home() / ".claude/settings.json"
    plugins = (
        json.loads(user.read_text()).get("enabledPlugins") if user.exists() else None
    )
    return json.dumps(
        {
            "enabledPlugins": dict.fromkeys(plugins, False)
            if isinstance(plugins, dict)
            else {},
            "sandbox": {
                "enabled": True,
                "autoAllowBashIfSandboxed": True,
                "allowUnsandboxedCommands": escape,
            },
        }
    )


def claude_run(
    root: Path, evidence: Path, options: argparse.Namespace, prompt: str, access: Access
) -> Agent:
    isolation, permission = claude_access(access)
    command = [
        "claude",
        "--print",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        options.model,
        "--effort",
        options.effort,
        # Project settings load the installed hooks; user settings, memory and MCP stay out.
        "--setting-sources",
        "project,local",
        "--strict-mcp-config",
        "--settings",
        isolation,
        "--permission-mode",
        permission,
        "--no-session-persistence",
        *([] if access != "grader" else ["--tools", ""]),
    ]
    found = stream(command, root, evidence, options.timeout)
    if found is None:
        return Agent(False, "", {}, [f"claude --print exceeded {options.timeout}s"], [])
    nothing: dict[str, object] = {}
    start = next((e for e in found if e.get("subtype") == "init"), nothing)
    keys = ("model", "permissionMode", "claude_code_version", "mcp_servers", "plugins")
    settings: dict[str, object] = {key: start.get(key) for key in keys}
    result = next((e for e in found if e.get("type") == "result"), nothing)
    text = result.get("result")
    message = text if isinstance(text, str) else ""
    (evidence / "last-message.md").write_text(message)
    usage = result.get("modelUsage")
    used: list[str] = sorted(usage) if isinstance(usage, dict) else []
    settings["models_used"] = used
    completed = result.get("is_error") is False
    problems = [] if completed else [message or "claude --print returned no result"]
    return Agent(completed, message, settings, problems, claude_actions(found))


def output(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def codex_preflight() -> Ready:
    if shutil.which("codex") is None:
        return Ready(None, "codex is not on PATH")
    version = output(["codex", "--version"]).stdout.strip()
    login = output(["codex", "login", "status"])
    return Ready(
        version,
        None
        if login.returncode == 0
        else "codex is not logged in: " + (login.stdout + login.stderr).strip(),
    )


def claude_preflight() -> Ready:
    if shutil.which("claude") is None:
        return Ready(None, "claude is not on PATH")
    version = output(["claude", "--version"]).stdout.strip()
    try:
        status = json.loads(output(["claude", "auth", "status"]).stdout)
        logged_in = status.get("loggedIn") is True
    except (json.JSONDecodeError, AttributeError):
        logged_in = False
    return Ready(version, None if logged_in else "claude is not logged in")


CLIENTS = {
    "codex": Client(
        "gpt-6-astra",
        codex_preflight,
        codex_run,
        "codex exec; workspace-write sandbox plus writable .git; fresh CODEX_HOME sharing only the login; fixture trusted; project hooks run without review; an approved case adds --approve-for-me",
    ),
    "claude": Client(
        "claude-opus-5-5",
        claude_preflight,
        claude_run,
        "claude --print; project and local settings only; user plugins off; no MCP; acceptEdits with sandboxed, network-less Bash; an approved case runs in auto mode and may ask to leave the sandbox",
    ),
}

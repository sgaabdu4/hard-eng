"""Copy the Hard Eng scaffold into an existing Git repository."""

import argparse
import json
import os
import subprocess
import tomllib
from pathlib import Path

SOURCE = Path(__file__).resolve().parent
START, END = "<!-- hard-eng:start -->", "<!-- hard-eng:end -->"
LANGUAGES = {"pyproject.toml": "python", "package.json": "javascript", "pubspec.yaml": "dart"}


def merge(current, additions):
    for key, value in additions.items():
        if key not in current:
            current[key] = value
        elif isinstance(value, dict):
            merge(current[key], value)
        elif isinstance(value, list):
            for item in value:
                if item not in current[key]:
                    current[key].append(item)
        elif current[key] != value:
            raise ValueError(f"Conflicting setting {key}; preserve it and ask before changing it")
    return current


def gate_config(root):
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=root,
                            capture_output=True, text=True, check=True)
    packages, shared = [], []
    for name in sorted(set(result.stdout.splitlines())):
        path = Path(name)
        if path.name not in LANGUAGES or ".agents" in path.parts:
            continue
        template = json.loads((SOURCE / ".agents/skills/he/templates" / f"hard-eng.{LANGUAGES[path.name]}.json").read_text())
        package = template["packages"][0]
        package["name"] = package["path"] = str(path.parent)
        packages.append(package)
        for gate in template["shared"]:
            if gate["role"] in {"secrets-files", "secrets-history"}:
                if gate not in shared:
                    shared.append(gate)
            else:
                package["checks"].insert(0, gate)
    if not packages:
        raise ValueError("No supported project manifest found")
    return {"version": 1, "packages": packages, "shared": shared}


def install(root):
    if root == SOURCE:
        raise ValueError("Run setup against the target project, not the scaffold source")
    subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, check=True)
    changes = {".hooks/hard-eng.py": (SOURCE / ".hooks/hard-eng.py").read_text()}
    for path in (SOURCE / ".agents/skills").rglob("*"):
        if path.is_file():
            changes[str(path.relative_to(SOURCE))] = path.read_text()
    for name, content in changes.items():
        target = root / name
        if target.exists() and target.read_text() != content:
            raise ValueError(f"{name} already differs; ask before replacing it")
    agents = root / "AGENTS.md"
    existing = agents.read_text() if agents.exists() else ""
    if START in existing or END in existing:
        if existing.count(START) != 1 or existing.count(END) != 1 or not existing.startswith(START):
            raise ValueError("Resolve conflicting Hard Eng markers in AGENTS.md first")
        existing = existing.split(END, 1)[1].lstrip("\n")
    changes["AGENTS.md"] = f"{START}\n{(SOURCE / 'AGENTS.md').read_text().rstrip()}\n{END}\n\n{existing}"
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    for agent, name in (("claude", ".claude/settings.json"), ("codex", ".codex/hooks.json"), ("copilot", ".github/hooks/hard-eng.json")):
        hooks = {}
        for event, native in (("session", "SessionStart"), ("stop", "Stop")):
            call = f"{command} {event} {agent}"
            hooks[native] = [{"hooks": [{"type": "command", "command": call, "timeout": 3600}]}]
            if agent == "copilot":
                del hooks[native]
                hooks["sessionStart" if event == "session" else "agentStop"] = [{"type": "command", "bash": call, "timeoutSec": 3600}]
        target = root / name
        current = json.loads(target.read_text()) if target.exists() else {}
        if current.get("disableAllHooks"):
            raise ValueError(f"{agent} hooks are disabled; ask before changing that")
        additions = {"hooks": hooks}
        if agent == "copilot":
            additions["version"] = 1
        if agent == "claude":
            additions.update({"extraKnownMarketplaces": {"context-mode": {"source": {"source": "github", "repo": "mksglu/context-mode"}}}, "enabledPlugins": {"context-mode@context-mode": True}})
        changes[name] = json.dumps(merge(current, additions), indent=2) + "\n"
    for name in (".mcp.json", ".github/mcp.json"):
        target = root / name
        current = json.loads(target.read_text()) if target.exists() else {}
        plugins = ["codebase-memory-mcp"] if name == ".mcp.json" else ["context-mode", "codebase-memory-mcp"]
        servers = {plugin: {"command": "npx", "args": ["--yes", f"{plugin}@latest"]} for plugin in plugins}
        changes[name] = json.dumps(merge(current, {"mcpServers": servers}), indent=2) + "\n"
    target = root / ".codex/config.toml"
    current = target.read_text() if target.exists() else ""
    parsed = tomllib.loads(current)
    for plugin in ("context-mode", "codebase-memory-mcp"):
        expected = {"command": "npx", "args": ["--yes", f"{plugin}@latest"]}
        existing_server = parsed.get("mcp_servers", {}).get(plugin)
        if existing_server is not None and existing_server != expected:
            raise ValueError(f"Conflicting Codex {plugin} settings")
        if existing_server is None:
            current += f'\n[mcp_servers."{plugin}"]\ncommand = "npx"\nargs = ["--yes", "{plugin}@latest"]\n'
    changes[".codex/config.toml"] = current
    if not (root / "hard-eng.gates.json").exists():
        changes["hard-eng.gates.json"] = json.dumps(gate_config(root), indent=2) + "\n"
    hook = Path(subprocess.check_output(["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=root, text=True).strip())
    hook = hook if hook.is_absolute() else root / hook
    if not hook.parent.resolve().is_relative_to(root):
        raise ValueError("Git hooks point outside this repository")
    if (hook.exists() or hook.is_symlink()) and hook.resolve() != root / ".hooks/hard-eng.py":
        raise ValueError("Existing pre-push hook must be preserved; ask before changing it")
    for name, content in changes.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    (root / ".hooks/hard-eng.py").chmod(0o755)
    if not hook.is_symlink():
        hook.symlink_to(os.path.relpath(root / ".hooks/hard-eng.py", hook.parent))
    print(f"Installed Hard Eng in {root}")
    print("Run: python3 .hooks/hard-eng.py check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())
    try:
        install(parser.parse_args().repository.resolve())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")

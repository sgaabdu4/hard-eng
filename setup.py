"""Copy the Hard Eng scaffold into an existing Git repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gate_config import Gate, GateConfig, Group, JsonObject

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE / ".hooks"))
START, END = "<!-- hard-eng:start -->", "<!-- hard-eng:end -->"
LANGUAGES = {
    "pyproject.toml": "python",
    "package.json": "javascript",
    "pubspec.yaml": "dart",
}


def merge(
    current: JsonObject, additions: JsonObject, path: tuple[str, ...] = ()
) -> JsonObject:
    if not isinstance(current, dict):
        raise TypeError(f"Conflicting setting {'.'.join(path)}; expected an object")
    for key, value in additions.items():
        location = (*path, key)
        existing = current.get(key)
        if key not in current:
            current[key] = value
        elif isinstance(value, dict):
            if not isinstance(existing, dict):
                raise TypeError(
                    f"Conflicting setting {'.'.join(location)}; expected an object"
                )
            merge(existing, value, location)
        elif (
            isinstance(value, list)
            and path == ("hooks",)
            and isinstance(existing, list)
        ):
            for item in value:
                if item not in existing:
                    existing.append(item)
        elif current[key] != value:
            raise ValueError(
                f"Conflicting setting {'.'.join(location)}; preserve it and ask before changing it"
            )
    return current


def gate_config(root: Path) -> GateConfig:
    from project_setup import adapt_packages

    result = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    packages: list[Group] = []
    shared: list[Gate] = []
    for name in sorted(set(result.stdout.split("\0")) - {""}):
        path = Path(name)
        if path.name not in LANGUAGES or ".agents" in path.parts:
            continue
        template = json.loads(
            (
                SOURCE
                / ".agents/skills/he/templates"
                / f"hard-eng.{LANGUAGES[path.name]}.json"
            ).read_text()
        )
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
    config: GateConfig = {"version": 1, "packages": packages, "shared": shared}
    adapt_packages(root, config)
    return config


def agent_instructions(root: Path, previous: Path | None = None) -> str:
    agents = root / "AGENTS.md"
    existing = agents.read_bytes().decode("utf-8") if agents.exists() else ""
    if START in existing or END in existing:
        if (
            existing.count(START) != 1
            or existing.count(END) != 1
            or not existing.startswith(START)
        ):
            raise ValueError("Resolve conflicting Hard Eng markers in AGENTS.md first")
        expected = (
            f"{START}\n{((previous or SOURCE) / 'AGENTS.md').read_text().rstrip()}\n"
        )
        if existing.split(END, 1)[0] != expected:
            raise ValueError(
                "Local Hard Eng instructions differ; preserve them and ask before replacing them"
            )
        existing = existing.split(END, 1)[1]
        if not existing.startswith("\n\n"):
            raise ValueError("Resolve conflicting Hard Eng markers in AGENTS.md first")
        existing = existing[2:]
    return (
        f"{START}\n{(SOURCE / 'AGENTS.md').read_text().rstrip()}\n{END}\n\n{existing}"
    )


def configure_hooks(root: Path, changes: dict[str, str]) -> None:
    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    for agent, name in (
        ("claude", ".claude/settings.json"),
        ("codex", ".codex/hooks.json"),
        ("copilot", ".github/hooks/hard-eng.json"),
    ):
        hooks: JsonObject = {}
        for event, native in (("session", "SessionStart"), ("stop", "Stop")):
            call = f"{command} {event} {agent}"
            hooks[native] = [
                {"hooks": [{"type": "command", "command": call, "timeout": 3600}]}
            ]
            if agent == "copilot":
                del hooks[native]
                hooks["sessionStart" if event == "session" else "agentStop"] = [
                    {"type": "command", "bash": call, "timeoutSec": 3600}
                ]
        target = root / name
        current: JsonObject = json.loads(target.read_text()) if target.exists() else {}
        if current.get("disableAllHooks"):
            raise ValueError(f"{agent} hooks are disabled; ask before changing that")
        additions: JsonObject = {"hooks": hooks}
        if agent == "copilot":
            additions["version"] = 1
        if agent == "claude":
            additions.update(
                {
                    "extraKnownMarketplaces": {
                        "context-mode": {
                            "source": {
                                "source": "github",
                                "repo": "mksglu/context-mode",
                            }
                        }
                    },
                    "enabledPlugins": {"context-mode@context-mode": True},
                }
            )
        changes[name] = json.dumps(merge(current, additions), indent=2) + "\n"


def configure_mcp(root: Path, changes: dict[str, str]) -> None:
    for name in (".mcp.json", ".github/mcp.json"):
        target = root / name
        current = json.loads(target.read_text()) if target.exists() else {}
        plugins = (
            ["codebase-memory-mcp"]
            if name == ".mcp.json"
            else ["context-mode", "codebase-memory-mcp"]
        )
        servers: JsonObject = {
            plugin: {"command": "npx", "args": ["--yes", f"{plugin}@latest"]}
            for plugin in plugins
        }
        changes[name] = (
            json.dumps(merge(current, {"mcpServers": servers}), indent=2) + "\n"
        )
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


def configure_typing_checks(package: Group) -> None:
    template = (
        SOURCE
        / ".agents/skills/he/templates"
        / f"hard-eng.{package.get('language')}.json"
    )
    if template.exists():
        for required in json.loads(template.read_text())["packages"][0]["checks"]:
            if required["role"] not in {"types", "annotations", "typing-style"}:
                continue
            matching = next(
                (
                    gate
                    for gate in package["checks"]
                    if gate["command"] == required["command"]
                ),
                None,
            )
            if matching is not None:
                matching["role"] = required["role"]
                continue
            for gate in package["checks"]:
                if gate.get("role") == required["role"]:
                    gate["role"] = "project-" + required["role"]
            required["name"] = "strict-" + required["name"]
            package["checks"].append(required)


def configure_dart(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    target = directory / "analysis_options.yaml"
    typing = runpy.run_path(str(SOURCE / ".hooks/hard-eng.py"))
    options: JsonObject = typing["dart_options"](target) if target.exists() else {}
    for section, groups in typing["DART_TYPING"].items():
        section_options = options.setdefault(section, {})
        if not isinstance(section_options, dict):
            raise TypeError(f"Dart {section} settings must be an object")
        for group, settings in groups.items():
            current = section_options.setdefault(group, {})
            if group == "rules" and isinstance(current, list):
                if not all(isinstance(rule, str) for rule in current):
                    raise TypeError("Dart lint rule names must be strings")
                rules: JsonObject = {str(rule): True for rule in current}
                current = rules
                section_options[group] = current
            if isinstance(settings, dict):
                if not isinstance(current, dict):
                    raise TypeError(f"Dart {section}.{group} must be an object")
                current.update(settings)
            else:
                section_options[group] = settings
    changes[str(target.relative_to(root))] = json.dumps(options, indent=2) + "\n"


def configure_javascript(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    from project_setup import javascript_manager

    manager = javascript_manager(directory)[0]
    target = directory / "tsconfig.json"
    if not target.exists():
        changes[str(target.relative_to(root))] = (
            json.dumps(
                {
                    "compilerOptions": {
                        "strict": True,
                        "allowJs": True,
                        "checkJs": True,
                        "noEmit": True,
                    },
                    "include": [*package["sources"], "test", "tests"],
                },
                indent=2,
            )
            + "\n"
        )
    scripts = json.loads((directory / "package.json").read_text()).get("scripts", {})
    if "typecheck" in scripts and not any(
        gate["command"] == [manager, "run", "typecheck"] for gate in package["checks"]
    ):
        package["checks"].append(
            {
                "name": "project-typecheck",
                "role": "project-typecheck",
                "command": [manager, "run", "typecheck"],
            }
        )


def configure_python(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    from project_setup import import_configuration

    native = directory / "pyrefly.toml"
    project = directory / "pyproject.toml"
    content = project.read_text()
    options = (
        tomllib.loads(native.read_text())
        if native.exists()
        else tomllib.loads(content).get("tool", {}).get("pyrefly")
    )
    if options is not None:
        if (
            options.get("preset") not in {"strict", "all"}
            or options.get("check-unannotated-defs", True) is not True
        ):
            raise ValueError(
                f"{package['path']}: existing Pyrefly settings need strict checking; preserve them and ask before changing them"
            )
    else:
        changes[str(project.relative_to(root))] = (
            content
            + '\n[tool.pyrefly]\npreset = "strict"\ncheck-unannotated-defs = true\n'
        )
    name = str(project.relative_to(root))
    updated = import_configuration(directory, package, changes.get(name, content))
    if updated != content:
        changes[name] = updated


def prepare_hook(root: Path) -> tuple[Path, str]:
    hook = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=root, text=True
        ).strip()
    )
    hook = hook if hook.is_absolute() else root / hook
    if not hook.parent.resolve().is_relative_to(root):
        raise ValueError("Git hooks point outside this repository")
    launcher = """#!/usr/bin/env python3
import subprocess
import sys

root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
sys.exit(subprocess.call([sys.executable, root + "/.hooks/hard-eng.py", "pre-push"]))
"""
    if (hook.exists() or hook.is_symlink()) and not (
        (hook.is_symlink() and hook.resolve() == root / ".hooks/hard-eng.py")
        or (not hook.is_symlink() and hook.is_file() and hook.read_text() == launcher)
    ):
        raise ValueError(
            "Existing pre-push hook must be preserved; ask before changing it"
        )
    return hook, launcher


def validate_destinations(root: Path, changes: dict[str, str], hook: Path) -> None:
    for name in (*changes, os.path.relpath(hook, root)):
        target = root / name
        for path in (target, *target.parents):
            if path == root:
                break
            if path == hook and path.is_symlink():
                continue
            if path.is_symlink():
                raise ValueError(
                    f"{path.relative_to(root)} is a symlink; preserve it and ask before changing it"
                )
            if path.exists() and (
                not path.is_file() if path == target else not path.is_dir()
            ):
                raise ValueError(f"Conflicting destination {path.relative_to(root)}")


def configure_workflows(root: Path, config: GateConfig) -> None:
    workflows = root / ".github/workflows"
    if not any(
        path.is_file() and path.suffix in {".yml", ".yaml"}
        for path in workflows.glob("*")
    ):
        return
    add_workflow_checks(config)


def add_workflow_checks(config: GateConfig) -> None:
    for role, command in (
        ("workflows", ["actionlint", "-no-color"]),
        (
            "ci-security",
            [
                "zizmor",
                "--strict-collection",
                "--persona=auditor",
                "--format=plain",
                ".",
            ],
        ),
    ):
        if any(
            gate.get("role") == role
            or (gate.get("command") and Path(gate["command"][0]).name == command[0])
            for gate in config["shared"]
        ):
            continue
        config["shared"].append(
            {
                "name": command[0],
                "role": role,
                "parallel": True,
                "command": command,
            }
        )


def configure_shellcheck(root: Path, config: GateConfig) -> None:
    if any(
        gate.get("role") == "shell"
        or (gate.get("command") and Path(gate["command"][0]).name == "shellcheck")
        for gate in config["shared"]
    ):
        return
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    )
    scripts = []
    for name in sorted(set(names.split("\0")) - {""}):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        if path.suffix in {".sh", ".bash"}:
            scripts.append(name)
        elif not path.suffix:
            with path.open("rb") as source:
                first_line = source.readline(4096)
            if re.match(rb"^#![^\n]*\b(?:bash|sh)(?:\s|$)", first_line):
                scripts.append(name)
    if scripts:
        config["shared"].append(
            {
                "name": "shellcheck",
                "role": "shell",
                "parallel": True,
                "command": ["shellcheck", "--", *scripts],
            }
        )


def configure_deployment(root: Path, config: GateConfig) -> None:
    if any(
        gate.get("role") == "deployment"
        or (
            gate.get("command")
            and Path(gate["command"][0]).name == "trivy"
            and "config" in gate["command"][1:]
        )
        for gate in config["shared"]
    ):
        return
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    )
    for name in names.split("\0"):
        path = root / name
        if not path.is_file() or path.is_symlink():
            continue
        if path.name in {
            "Dockerfile",
            "Containerfile",
            "Chart.yaml",
            "tfplan",
        } or name.endswith((".tf", ".tf.json", ".tfvars", ".tfplan")):
            config["shared"].append(
                {
                    "name": "trivy-config",
                    "role": "deployment",
                    "command": [
                        "trivy",
                        "config",
                        "--exit-code",
                        "1",
                        "--format",
                        "json",
                        ".",
                    ],
                    "report": {
                        "type": "trivy",
                        "path": "coverage/trivy.json",
                        "stdout": True,
                    },
                }
            )
            return


def scaffold_changes(root: Path, previous: Path | None = None) -> dict[str, str]:
    changes = {
        str(path.relative_to(SOURCE)): path.read_text()
        for path in (SOURCE / ".hooks").glob("*.py")
    }
    for path in (SOURCE / ".agents/skills").rglob("*"):
        if path.is_file():
            changes[str(path.relative_to(SOURCE))] = path.read_text()
    for name, content in changes.items():
        target = root / name
        if target.exists() and target.read_text() != content:
            old = previous / name if previous is not None else None
            if (
                old is None
                or not old.is_file()
                or target.read_bytes() != old.read_bytes()
            ):
                raise ValueError(f"{name} already differs; ask before replacing it")
    return changes


def prepare_skill_links(root: Path) -> dict[str, str]:
    links = {}
    for skill in (SOURCE / ".agents/skills").iterdir():
        if not skill.is_dir():
            continue
        name = ".claude/skills/" + skill.name
        link = root / name
        target = root / ".agents/skills" / skill.name
        if (link.exists() or link.is_symlink()) and not (
            link.is_symlink() and link.resolve() == target
        ):
            raise ValueError(
                f"{name} already differs; preserve it and ask before replacing it"
            )
        for parent in (link.parent, link.parent.parent):
            if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                raise ValueError(f"Conflicting skills directory: {parent}")
        links[name] = os.path.relpath(target, link.parent)
    return links


def configure_ignores(root: Path, changes: dict[str, str]) -> None:
    ignores = (
        (root / ".gitignore").read_text() if (root / ".gitignore").exists() else ""
    )
    for pattern in (
        ".git/",
        "__pycache__/",
        ".hard-eng/",
        ".codebase-memory/",
        ".context-mode/",
        "coverage/",
    ):
        if pattern not in ignores.splitlines():
            ignores += (
                ("" if not ignores or ignores.endswith("\n") else "\n") + pattern + "\n"
            )
    changes[".gitignore"] = ignores


def plan_install(
    root: Path, previous: Path | None = None
) -> tuple[dict[str, str], dict[str, str], Path, str]:
    if root == SOURCE:
        raise ValueError(
            "Run setup against the target project, not the scaffold source"
        )
    git_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"], cwd=root, text=True
    ).strip()
    if Path(git_root).resolve() != root:
        raise ValueError("Run setup from the target Git repository root")
    changes = scaffold_changes(root, previous)
    changes["AGENTS.md"] = agent_instructions(root, previous)
    configure_hooks(root, changes)
    configure_mcp(root, changes)
    configure_ignores(root, changes)
    revision = None
    if not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=SOURCE, text=True
    ):
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True
        ).strip()
    changes[".hooks/hard-eng-source.json"] = json.dumps({"revision": revision}) + "\n"
    if not (root / "hard-eng.gates.json").exists():
        changes["hard-eng.gates.json"] = json.dumps(gate_config(root), indent=2) + "\n"
    config = json.loads(
        changes.get("hard-eng.gates.json") or (root / "hard-eng.gates.json").read_text()
    )
    for package in config.get("packages", []):
        ignore = Path(package["path"]) / ".semgrepignore"
        if not (root / ignore).exists():
            changes[str(ignore)] = (
                "# Include production and tests; replace Semgrep's default test exclusions.\n"
            )
        configure_typing_checks(package)
        configure = {
            "python": configure_python,
            "dart": configure_dart,
            "javascript": configure_javascript,
        }.get(package.get("language"))
        if configure is not None:
            configure(root, root / package["path"], package, changes)
    from project_setup import configure_ci

    configure_ci(root, SOURCE, config, changes)
    if ".github/workflows/hard-eng.yml" in changes:
        add_workflow_checks(config)
    configure_workflows(root, config)
    configure_shellcheck(root, config)
    configure_deployment(root, config)
    if "hard-eng.gates.json" in changes or config != json.loads(
        (root / "hard-eng.gates.json").read_text()
    ):
        changes["hard-eng.gates.json"] = json.dumps(config, indent=2) + "\n"
    hook, launcher = prepare_hook(root)
    links = prepare_skill_links(root)
    validate_destinations(root, changes, hook)
    return changes, links, hook, launcher


def install(root: Path, previous: Path | None = None) -> None:
    changes, links, hook, launcher = plan_install(root, previous)
    for name, content in changes.items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    for name, destination in links.items():
        link = root / name
        if not link.is_symlink():
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(destination, target_is_directory=True)
    (root / ".hooks/hard-eng.py").chmod(0o755)
    if hook.is_symlink():
        hook.unlink()
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(launcher)
    hook.chmod(0o755)
    print(f"Installed Hard Eng in {root}")
    print("Run: python3 .hooks/hard-eng.py check")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", nargs="?", type=Path, default=Path.cwd())
    parser.add_argument("--previous-source", type=Path)
    parser.add_argument(
        "--plan",
        action="store_true",
        help="Print the installation plan without writing files",
    )
    try:
        args = parser.parse_args()
        if args.plan:
            changes, links, hook, launcher = plan_install(
                args.repository.resolve(), args.previous_source
            )
            print(json.dumps({"files": changes, "links": links}))
        else:
            install(args.repository.resolve(), args.previous_source)
    except (OSError, TypeError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")

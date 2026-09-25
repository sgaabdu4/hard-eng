"""Copy the Hard Eng scaffold into an existing Git repository."""

from __future__ import annotations

import argparse
import json
import os
import runpy
import subprocess
import sys
import tomllib
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gate_config import Gate, GateConfig, Group, JsonObject

SOURCE = Path(__file__).resolve().parent
sys.path.insert(0, str(SOURCE / ".hooks"))


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
    from gate_config import package_manifests, repository_files
    from project_setup import adapt_packages

    packages: list[Group] = []
    shared: list[Gate] = []
    for path, language in sorted(package_manifests(root, repository_files(root))):
        template = json.loads(
            (
                SOURCE / ".agents/skills/he/templates" / f"hard-eng.{language}.json"
            ).read_text()
        )
        package = template["packages"][0]
        package["name"] = package["path"] = path
        packages.append(package)
        for gate in template["shared"]:
            if gate["role"] in {"secrets-files", "secrets-history"}:
                if gate not in shared:
                    shared.append(gate)
            else:
                package["checks"].insert(0, gate)
    if not packages:
        raise ValueError(
            "No supported project manifest found. New project: ask the user which type to create "
            "(Python, Flutter, Next.js or OpenNext on Cloudflare) unless their request says, "
            "create it with that stack's official scaffold command, then rerun setup. "
            "A new Flutter app uses Riverpod per .agents/skills/building-flutter-apps."
        )
    config: GateConfig = {"version": 1, "packages": packages, "shared": shared}
    adapt_packages(root, config)
    return config


def configure_hooks(root: Path, changes: dict[str, str]) -> None:
    import agent_hooks

    codex_config = root / ".codex/config.toml"
    if codex_config.exists():
        features = tomllib.loads(codex_config.read_text()).get("features", {})
        setting = (
            "hooks"
            if isinstance(features, dict) and "hooks" in features
            else "codex_hooks"
        )
        if isinstance(features, dict) and features.get(setting) is False:
            raise ValueError(
                "Codex hooks are disabled by the project-local "
                f".codex/config.toml [features].{setting} setting; preserve it and ask before changing it. "
                "`codex --enable hooks` enables one launch but does not resolve this installer conflict."
            )

    command = 'python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py"'
    for agent, name in (
        ("claude", ".claude/settings.json"),
        ("codex", ".codex/hooks.json"),
        ("copilot", ".github/hooks/hard-eng.json"),
    ):
        hooks: JsonObject = {}
        for event, native in agent_hooks.hook_events(agent).items():
            timeout = 3600 if event in {"session", "stop"} else 10
            status_message = (
                agent_hooks.CODEX_HOOK_STATUS.get(event) if agent == "codex" else None
            )
            hooks[native] = [
                agent_hooks.owned_hook_entry(
                    agent, event, command, timeout, status_message=status_message
                )
            ]
        target = root / name
        text = target.read_text() if target.exists() else "{}"
        current: JsonObject = json.loads(text)
        if current.get("disableAllHooks"):
            raise ValueError(f"{agent} hooks are disabled; ask before changing that")
        agent_hooks.remove_routine_hooks(current, agent, command)
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
        merged = merge(current, additions)
        if merged != json.loads(text):
            changes[name] = json.dumps(merged, indent=2) + "\n"


def configure_mcp(root: Path, changes: dict[str, str]) -> None:
    from mcp_setup import configure_mcp as configure

    configure(root, changes)


def configure_typing_checks(root: Path, package: Group) -> None:
    template = (
        SOURCE
        / ".agents/skills/he/templates"
        / f"hard-eng.{package.get('language')}.json"
    )
    if template.exists():
        root_dart_sources = list(
            dict.fromkeys(
                [
                    *package.get("sources", ["lib"]),
                    *(
                        name
                        for name in ("test", "tests", "integration_test", "test_driver")
                        if (root / name).is_dir()
                    ),
                ]
            )
        )
        for required in json.loads(template.read_text())["packages"][0]["checks"]:
            if required["role"] not in {"types", "annotations", "typing-style"}:
                continue
            root_dart = package.get("language") == "dart" and package.get("path") == "."
            template_command = required["command"]
            required["command"] = [
                value
                for argument in template_command
                for value in (
                    package.get("sources", ["src"])
                    if argument == "src"
                    else root_dart_sources
                    if argument == "." and root_dart
                    else [argument]
                )
            ]
            accepted = [required["command"]]
            if root_dart and "." in template_command:
                accepted += adopt_root_dart_gates(
                    package["checks"], required, template_command
                )
            matching = next(
                (gate for gate in package["checks"] if gate["command"] in accepted),
                None,
            )
            if matching is not None:
                matching["role"] = required["role"]
                # Earlier installs could leave copies or a strict gate beside the owner.
                package["checks"][:] = [
                    gate
                    for gate in package["checks"]
                    if gate is matching
                    or (
                        gate["command"] != matching["command"]
                        and (gate["name"], gate["command"])
                        != ("strict-" + required["name"], required["command"])
                    )
                ]
                continue
            for gate in package["checks"]:
                if gate.get("role") == required["role"]:
                    gate["role"] = "project-" + required["role"]
            required["name"] = "strict-" + required["name"]
            package["checks"].append(required)


def adopt_root_dart_gates(
    checks: list[Gate], required: Gate, template_command: list[str]
) -> list[list[str]]:
    for gate in checks:
        # Hard Eng's own unexpanded root gate follows the expanded template.
        if gate["name"] == required["name"] and gate["command"] == template_command:
            gate["command"] = required["command"]
    # A project's package-root analyzer already covers the explicit directories.
    return [template_command, [value for value in template_command if value != "."]]


def configure_dart(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    import yaml
    from gate_config import dart_rule_settings, validate_dart_exclusions
    from project_setup import migrate_dart_plugins

    target = directory / "analysis_options.yaml"
    typing = runpy.run_path(str(SOURCE / ".hooks/hard-eng.py"))
    options: JsonObject = typing["dart_options"](target) if target.exists() else {}
    original = deepcopy(options)
    existing = target.read_bytes().decode("utf-8") if target.exists() else ""
    migrate_dart_plugins(options, SOURCE)
    for section, groups in typing["DART_TYPING"].items():
        section_options = options.setdefault(section, {})
        if not isinstance(section_options, dict):
            raise TypeError(f"Dart {section} settings must be an object")
        for group, settings in groups.items():
            current = (
                section_options.get(group, [])
                if isinstance(settings, list)
                else section_options.setdefault(group, {})
            )
            if group == "rules" and isinstance(current, list):
                dart_rule_settings(current)
                current.extend(rule for rule in settings if rule not in current)
                continue
            if isinstance(settings, dict):
                if not isinstance(current, dict):
                    raise TypeError(f"Dart {section}.{group} must be an object")
                if group == "language":
                    current.pop("strict-casts", None)
                    current.pop("strict-raw-types", None)
                merge(current, settings, (section, group))
            else:
                validate_dart_exclusions(directory, current)
    content = (
        existing
        if target.exists() and options == original
        else yaml.safe_dump(options, sort_keys=False)
    )
    marker = "# Hard Eng test coverage uses dart run coverage:test_with_coverage.\n"
    if marker not in content and any(
        "coverage:test_with_coverage" in gate["command"] for gate in package["checks"]
    ):
        # Declare coverage tooling without hiding production-import checks.
        content = marker + content
    if content != existing:
        changes[str(target.relative_to(root))] = content
    configure_dart_scanner(root, directory, changes)


def configure_dart_scanner(
    root: Path, directory: Path, changes: dict[str, str]
) -> None:
    scanner_names = (
        ".dart-decimaterc",
        ".dart-decimaterc.json",
        ".dart-decimaterc.jsonc",
        "dart-decimate.toml",
        ".dart-decimate.toml",
    )
    if not any((directory / name).exists() for name in scanner_names):
        scanner: dict[str, list[str]] = {"ignore_patterns": [".agents/**"]}
        path = directory / ".dart-decimaterc.json"
        changes[str(path.relative_to(root))] = json.dumps(scanner, indent=2) + "\n"


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
    from project_setup import import_configuration, parallel_pytest

    parallel_pytest(package)
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
    from agent_hooks import project_pre_push

    hook = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--git-path", "hooks/pre-push"], cwd=root, text=True
        ).strip()
    )
    hook = hook if hook.is_absolute() else root / hook
    target = project_pre_push(root, hook)
    launcher = """#!/usr/bin/env python3
import subprocess
import sys

root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip()
sys.exit(subprocess.call([sys.executable, root + "/.hooks/hard-eng.py", "pre-push"]))
"""
    previous = launcher
    if target != hook:
        launcher = '#!/usr/bin/env sh\nexec python3 "$(git rev-parse --show-toplevel)/.hooks/hard-eng.py" pre-push\n'
    hook = target
    if (hook.exists() or hook.is_symlink()) and not (
        (hook.is_symlink() and hook.resolve() == root / ".hooks/hard-eng.py")
        or (
            not hook.is_symlink()
            and hook.is_file()
            and hook.read_text() in {launcher, previous}
        )
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
    from gate_config import repository_files
    from project_setup import is_shell_script

    if any(
        gate.get("role") == "shell"
        or (gate.get("command") and Path(gate["command"][0]).name == "shellcheck")
        for gate in config["shared"]
    ):
        return
    scripts = [
        str(path.relative_to(root))
        for path in repository_files(root)
        if is_shell_script(path)
    ]
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
    from gate_config import repository_files
    from project_setup import is_deployment_file

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
    for path in repository_files(root):
        if is_deployment_file(path):
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


STACK_SKILLS = {"appwrite-backend": "Appwrite", "building-flutter-apps": "Dart"}


def unused_skills(root: Path) -> set[str]:
    from agent_hooks import integrated_services

    services = integrated_services(root)
    return {skill for skill, service in STACK_SKILLS.items() if service not in services}


def scaffold_changes(
    root: Path, previous: Path | None, unused: set[str]
) -> dict[str, str]:
    from update import scaffold_files, without_skills

    changes = {
        name: (SOURCE / name).read_text()
        for name in sorted(without_skills(scaffold_files(SOURCE), unused))
    }
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


def prepare_skill_links(root: Path, unused: set[str]) -> dict[str, str]:
    links = {}
    for skill in (SOURCE / ".agents/skills").iterdir():
        if not skill.is_dir() or skill.name in unused:
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
        ".coverage",
        ".coverage.*",
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
    unused = unused_skills(root)
    changes = scaffold_changes(root, previous, unused)
    from agent_hooks import configure_instructions

    configure_instructions(root, SOURCE, previous, changes)
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
    from gate_config import parse_config, repository_files, typescript_packages

    config = parse_config(
        changes.get("hard-eng.gates.json") or (root / "hard-eng.gates.json").read_text()
    )
    from project_setup import (
        adapt_boundaries,
        browser_test_coverage,
        strict_scanner_flags,
    )

    typescript = typescript_packages(root, repository_files(root))
    for package in config.get("packages", []):
        adapt_boundaries(package, typescript)
        strict_scanner_flags(package)
        browser_test_coverage(root / package["path"], package)
        ignore = Path(package["path"]) / ".semgrepignore"
        if not (root / ignore).exists():
            changes[str(ignore)] = (
                "# Include production and tests; replace Semgrep's default test exclusions.\n"
            )
        configure_typing_checks(root, package)
        configure = {
            "python": configure_python,
            "dart": configure_dart,
            "javascript": configure_javascript,
        }.get(package.get("language", ""))
        if configure is not None:
            configure(root, root / package["path"], package, changes)
    from ci_setup import configure_ci

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
    links = prepare_skill_links(root, unused)
    validate_destinations(root, changes, hook)
    return changes, links, hook, launcher


def commit_install(root: Path, names: list[str], clean: bool) -> str:
    from update import install_paths

    reason = "these paths already had local changes"
    if clean:
        subprocess.run(["git", "add", "--force", "--", *names], cwd=root, check=True)
        result = subprocess.run(
            ["git", "commit", "--only", "-m", "Install Hard Eng", "--", *names],
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return "Committed the installed files locally without pushing."
        subprocess.run(["git", "reset", "--quiet", "--", *names], cwd=root, check=False)
        reason = " | ".join(result.stdout.strip().splitlines()[-3:])
    return (
        f"Installed files are not committed ({reason}). Commit them so updates and "
        "worktrees include them: " + install_paths(names)
    )


def install(root: Path, previous: Path | None = None) -> None:
    changes, links, hook, launcher = plan_install(root, previous)
    names = sorted({*changes, *links})
    # Commit only paths without prior local state, so no project edit joins the commit.
    clean = not subprocess.check_output(
        [
            "git",
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--ignored",
            "--",
            *names,
        ],
        cwd=root,
        text=True,
    )
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
    from dependency_graph import dependency_review_guidance

    config = json.loads((root / "hard-eng.gates.json").read_text())
    guidance = dependency_review_guidance(config["packages"])
    if guidance is not None:
        print("Before using --base package selection, " + guidance)
    print(f"Installed Hard Eng files in {root}; setup is not yet verified.")
    print(commit_install(root, names, clean))
    print("Follow HE Plan to adapt the gates and configure shipping before delivery.")
    print(
        "Integration setup: .agents/skills/he/references/integrations.md — reuse existing choices; resolve only missing service targets and verify relevant real calls."
    )
    print(
        "Codex: if hooks are disabled for this launch, start with `codex --enable hooks`; trust the project to load .codex configuration, then review new or changed hooks with /hooks. Hook-trust bypass alone does not trust the project.\n"
        "MCP entries still need host loading and authentication. In Codex, inspect `codex mcp list`; use `codex mcp login <name>` for an unauthenticated OAuth server, then verify a real call in the task."
    )
    print("Then run: python3 .hooks/hard-eng.py check")
    print("Start a new agent session so it loads the installed skills.")


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
            hook_plan = {
                "path": os.path.relpath(hook, args.repository.resolve()),
                "content": launcher,
            }
            print(json.dumps({"files": changes, "links": links, "hook": hook_plan}))
        else:
            install(args.repository.resolve(), args.previous_source)
    except (OSError, TypeError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")

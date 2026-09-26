"""Copy the Hard Eng scaffold into an existing Git repository."""

from __future__ import annotations

import argparse
import json
import os
import re
import runpy
import shlex
import shutil
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
    from gate_config import dart_test_support, package_manifests, repository_files
    from project_setup import adapt_packages

    packages: list[Group] = []
    shared: list[Gate] = []
    files = repository_files(root)
    for path, language in sorted(package_manifests(root, files)):
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
    requirements = sorted(
        str(path.parent.relative_to(root))
        for path in files
        if path.name == "requirements.txt"
        and ".agents" not in path.relative_to(root).parts
    )
    if not packages and requirements:
        raise ValueError(
            f"requirements.txt without pyproject.toml in {', '.join(requirements)}: run "
            "`uv init --bare` then `uv add -r requirements.txt` there (writes pyproject.toml "
            "and uv.lock), commit both, then rerun setup."
        )
    if not packages:
        raise ValueError(
            "No supported project manifest found. New project: ask the user which type to create "
            "(Python, Flutter, Next.js or OpenNext on Cloudflare) unless their request says, "
            "create it with that stack's official scaffold command, then rerun setup. "
            "A new Flutter app uses Riverpod per .agents/skills/building-flutter-apps."
        )
    config: GateConfig = {"version": 1, "packages": packages, "shared": shared}
    adapt_packages(root, config)
    for package in packages:
        if dart_test_support(package["path"], package.get("language"), packages):
            # A test-support package's code is gated by its parent's checks.
            del package["language"], package["sources"]
            package["checks"] = [
                gate
                for gate in package["checks"]
                if gate.get("role") in {"lockfiles", "vulnerabilities"}
            ]
    return config


def configure_hooks(root: Path, changes: dict[str, str]) -> None:
    import agent_hooks
    from gate_config import json_file

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
    for agent, name in agent_hooks.HOOK_FILES.items():
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
            changes[name] = json_file(root, merged)


def configure_mcp(root: Path, changes: dict[str, str]) -> None:
    from mcp_setup import configure_mcp as configure

    configure(root, changes)


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
            root_dart = package.get("language") == "dart" and package.get("path") == "."
            required["command"] = [
                value
                for argument in required["command"]
                for value in (
                    package.get("sources", ["src"]) if argument == "src" else [argument]
                )
            ]
            accepted = [required["command"]]
            if root_dart and "." in required["command"]:
                accepted += adopt_root_dart_gates(package["checks"], required)
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


def adopt_root_dart_gates(checks: list[Gate], required: Gate) -> list[list[str]]:
    analyzer = [value for value in required["command"] if value != "."]
    for gate in checks:
        paths = gate["command"][len(analyzer) :]
        # Explicit paths skip analyzer plugins, so earlier directory scopes return to the root.
        if (
            gate["name"] in {required["name"], "strict-" + required["name"]}
            and gate["command"][: len(analyzer)] == analyzer
            and paths
            and not any(path == "." or path.startswith("-") for path in paths)
        ):
            gate["command"] = list(required["command"])
    return [analyzer]


def apply_dart_typing(
    options: JsonObject,
    required: dict[str, JsonObject],
    directory: Path,
) -> None:
    from gate_config import dart_rule_settings, validate_dart_exclusions

    for section, groups in required.items():
        # A key holding only comments, as in `flutter create` output, parses as null.
        if options.get(section) is None:
            options[section] = {}
        section_options = options[section]
        if not isinstance(section_options, dict):
            raise TypeError(f"Dart {section} settings must be an object")
        for group, settings in groups.items():
            if section_options.get(group) is None and not isinstance(settings, list):
                section_options[group] = {}
            current = (
                section_options.get(group) or []
                if isinstance(settings, list)
                else section_options[group]
            )
            if (
                group == "rules"
                and isinstance(current, list)
                and isinstance(settings, dict)
            ):
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


def configure_dart(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    import yaml
    from project_setup import migrate_dart_plugins

    target = directory / "analysis_options.yaml"
    typing = runpy.run_path(str(SOURCE / ".hooks/hard-eng.py"))
    options: JsonObject = typing["dart_options"](target) if target.exists() else {}
    original = deepcopy(options)
    existing = target.read_bytes().decode("utf-8") if target.exists() else ""
    migrate_dart_plugins(options, SOURCE)
    apply_dart_typing(options, typing["DART_TYPING"], directory)
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
    configure_dart_generated(root, directory, changes)


LOCALE = re.compile(r"[a-z]{2,3}([_-][A-Z][a-z]{3})?([_-](?:[A-Z]{2}|\d{3}))?")


def arb_language(arb: Path) -> str | None:
    """Mirror gen-l10n: `@@locale`, else the first locale suffix of the file name."""
    try:
        resources = json.loads(arb.read_text())
    except (OSError, ValueError):
        resources = None
    locale = resources.get("@@locale") if isinstance(resources, dict) else None
    if not isinstance(locale, str):
        stem = arb.stem
        candidates = [stem, *(stem[i + 1 :] for i, c in enumerate(stem) if c == "_")]
        locale = next((name for name in candidates if LOCALE.fullmatch(name)), None)
    return re.split("[_-]", locale)[0] if locale else None


def localization_outputs(root: Path, directory: Path) -> list[str]:
    import yaml

    localization = directory / "l10n.yaml"
    if not localization.is_file():
        return []
    options = yaml.safe_load(localization.read_text()) or {}
    if not isinstance(options, dict) or options.get("synthetic-package", False):
        return []
    arbs = directory / str(options.get("arb-dir", "lib/l10n"))
    output = directory / str(
        options.get("output-dir", options.get("arb-dir", "lib/l10n"))
    )
    name = Path(
        str(options.get("output-localization-file", "app_localizations.dart"))
    ).name
    stem, _, extension = name.partition(".")  # gen-l10n splits at the first dot.
    languages = {arb_language(arb) for arb in arbs.glob("*.arb")} - {None}
    names = [name, *(f"{stem}_{language}.{extension}" for language in languages)]
    relative = [os.path.relpath(output / name, root) for name in sorted(names)]
    return [Path(name).as_posix() for name in relative if not name.startswith("..")]


def configure_dart_generated(
    root: Path, directory: Path, changes: dict[str, str]
) -> None:
    """Mark generator output so coverage and file-size gates skip it."""
    path = root / ".gitattributes"
    existing = path.read_text() if path.exists() else ""
    attributes = changes.get(".gitattributes", existing)
    declared = set()
    for line in attributes.splitlines():
        try:
            fields = shlex.split(line, comments=True)
        except ValueError:
            fields = line.split()
        if fields and any("linguist-generated" in field for field in fields[1:]):
            declared.add(fields[0])
    added = "".join(
        # Git reads C-style double-quoted patterns, which may contain spaces.
        (
            json.dumps(pattern, ensure_ascii=False)
            if any(c.isspace() for c in pattern)
            else pattern
        )
        + " linguist-generated=true\n"
        for pattern in [
            "*.g.dart",
            "*.freezed.dart",
            "*.gr.dart",
            *localization_outputs(root, directory),
        ]
        if pattern not in declared
    )
    # Prepend: later lines win, so existing project overrides keep precedence.
    if added:
        changes[".gitattributes"] = added + attributes


def configure_dart_scanner(
    root: Path, directory: Path, changes: dict[str, str]
) -> None:
    from gate_config import json_file

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
        changes[str(path.relative_to(root))] = json_file(root, scanner)


def configure_javascript(
    root: Path, directory: Path, package: Group, changes: dict[str, str]
) -> None:
    from gate_config import json_file
    from project_setup import javascript_manager

    manager = javascript_manager(directory)[0]
    target = directory / "tsconfig.json"
    if not target.exists():
        changes[str(target.relative_to(root))] = json_file(
            root,
            {
                "compilerOptions": {
                    "strict": True,
                    "allowJs": True,
                    "checkJs": True,
                    "noEmit": True,
                },
                "include": [*package["sources"], "test", "tests"],
            },
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
    from project_setup import dependency_command, import_configuration, parallel_pytest

    dependency_command(directory, "python")  # Existing configurations need a lock too.
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


def configure_shellcheck(
    root: Path, config: GateConfig, retired: tuple[str, ...] = ()
) -> None:
    from gate_config import repository_files
    from project_setup import is_shell_script

    existing = [
        gate
        for gate in config["shared"]
        if gate.get("role") == "shell"
        or (gate.get("command") and Path(gate["command"][0]).name == "shellcheck")
    ]
    for gate in existing:
        command = [part for part in gate["command"] if part not in retired]
        if command != gate["command"] and not any(
            (root / part).is_file() for part in command[1:]
        ):
            config["shared"].remove(gate)
        gate["command"] = command
    if any(gate in config["shared"] for gate in existing):
        return
    scripts = [
        str(path.relative_to(root))
        for path in repository_files(root)
        if is_shell_script(path) and str(path.relative_to(root)) not in retired
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
        ".claude/worktrees/",
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


INTERPRETERS = {"python", "python3", "node", "bash", "sh", "ruby", "perl"}
# Options whose operand is inline code or a module, then options that take a value.
INLINE = {"-c", "-m", "-e", "-p", "--eval", "--print"}
VALUED = {"-W", "-X", "-r", "--require", "--import", "--loader", "-o"}


def script_operand(arguments: list[str]) -> str | None:
    """Return the script an interpreter runs, or None for inline code or modules."""
    options = iter(arguments[1:])
    for argument in options:
        if argument in INLINE:
            return None
        if argument == "--" or not argument.startswith("-"):
            return next(options, None) if argument == "--" else argument
        if argument in VALUED:
            next(options, None)
    return None


def legacy_command_problem(root: Path, arguments: list[str]) -> str | None:
    """Name why a retired family command cannot run, or None when it can."""
    if not (shutil.which(arguments[0]) or (root / arguments[0]).is_file()):
        return "program not found"
    interpreter = Path(arguments[0]).name.rstrip("0123456789.") in INTERPRETERS
    script = script_operand(arguments) if interpreter else None
    if script is not None and not (root / script).is_file():
        return "script not found"
    return None


def retired_config(root: Path) -> GateConfig | None:
    """Regenerate a pre-rebuild families configuration, keeping runnable commands."""
    from gate_config import validate_gate

    legacy = json.loads((root / "hard-eng.gates.json").read_text())
    if not isinstance(legacy, dict) or "families" not in legacy or "packages" in legacy:
        return None
    families: dict[str, object] = (
        legacy["families"] if isinstance(legacy["families"], dict) else {}
    )
    config = gate_config(root)
    # Families ran from the repository root; only root checks duplicate them.
    covered = [gate["command"] for gate in config["shared"]] + [
        gate["command"]
        for group in config["packages"]
        if Path(group["path"]) == Path(".")
        for gate in group["checks"]
    ]
    dropped = []
    for name, command in families.items():
        values: list[object] = command if isinstance(command, list) else []
        arguments = [value for value in values if isinstance(value, str)]
        gate: Gate = {"name": f"legacy-{name}", "command": arguments}
        reason = None
        if not arguments or len(arguments) != len(values):
            reason = "not an argument list"
        else:
            reason = legacy_command_problem(root, arguments)
        if reason is None:
            try:
                validate_gate(gate, root, set())
            except (OSError, ValueError, TypeError) as error:
                reason = str(error)
        if reason is not None:
            dropped.append(f"{name} ({reason}): {command}")
        elif arguments not in covered:
            config["shared"].append(gate)
    # stderr keeps --plan's JSON output parseable.
    print(
        "Regenerated hard-eng.gates.json from the current templates. Retired families "
        "that still run and validate stay as legacy-<name> shared checks; remove any "
        "the templates now cover. Dropped: " + ("; ".join(dropped) or "none"),
        file=sys.stderr,
    )
    return config


def plan_install(
    root: Path, previous: Path | None = None
) -> tuple[dict[str, str], dict[str, str], Path, str, list[str]]:
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
    from update import old_generation

    retired = old_generation(root, changes)
    configure_mcp(root, changes)
    configure_ignores(root, changes)
    revision = None
    if not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=SOURCE, text=True
    ):
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=SOURCE, text=True
        ).strip()
    from gate_config import (
        json_file,
        parse_config,
        repository_files,
        typescript_packages,
    )

    changes[".hooks/hard-eng-source.json"] = json_file(root, {"revision": revision})
    generated = (
        retired_config(root)
        if (root / "hard-eng.gates.json").exists()
        else gate_config(root)
    )
    if generated is not None:
        changes["hard-eng.gates.json"] = json_file(root, generated)
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
        configure_typing_checks(package)
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
    configure_shellcheck(root, config, tuple(retired))
    configure_deployment(root, config)
    if "hard-eng.gates.json" in changes or config != json.loads(
        (root / "hard-eng.gates.json").read_text()
    ):
        changes["hard-eng.gates.json"] = json_file(root, config)
    hook, launcher = prepare_hook(root)
    links = prepare_skill_links(root, unused)
    validate_destinations(root, changes, hook)
    return changes, links, hook, launcher, retired


def install(root: Path, previous: Path | None = None) -> None:
    from update import commit_install, local_state, write_changes

    changes, links, hook, launcher, deleted = plan_install(root, previous)
    names = sorted({*changes, *links, *deleted})
    if hook.is_relative_to(root) and ".git" not in hook.relative_to(root).parts:
        names.append(str(hook.relative_to(root)))  # A Husky launcher lives in the tree.
    # Commit only paths without prior local state, so no project edit joins the commit.
    clean = not local_state(root, names)
    write_changes(root, {**changes, **dict.fromkeys(deleted)})
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
    if deleted:
        print("Removed old Hard Eng files: " + ", ".join(deleted))
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
            changes, links, hook, launcher, retired = plan_install(
                args.repository.resolve(), args.previous_source
            )
            hook_plan = {
                "path": os.path.relpath(hook, args.repository.resolve()),
                "content": launcher,
            }
            print(
                json.dumps(
                    {
                        "files": changes,
                        "links": links,
                        "hook": hook_plan,
                        "retired": retired,
                    }
                )
            )
        else:
            install(args.repository.resolve(), args.previous_source)
    except (OSError, TypeError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"{error}\n")

"""Adapt native template commands to the target project's existing stack."""

import json
import os
import re
import shlex
import subprocess
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

from gate_config import GateConfig, Group, nonproduction_source, repository_files

PACKAGE_MANAGERS = {"npm", "npx", "pnpm", "yarn", "yarnpkg", "bun", "bunx"}


def is_shell_script(path: Path) -> bool:
    if path.suffix in {".sh", ".bash"}:
        return True
    if path.suffix:
        return False
    with path.open("rb") as source:
        return bool(re.match(rb"^#![^\n]*\b(?:bash|sh)(?:\s|$)", source.readline(4096)))


def is_deployment_file(path: Path) -> bool:
    return path.name in {"Dockerfile", "Containerfile", "Chart.yaml", "tfplan"} or str(
        path
    ).endswith((".tf", ".tf.json", ".tfvars", ".tfplan"))


def package_script_arguments(
    command: list[str], directory: Path, pnpm_only: bool = False
) -> list[str]:
    arguments = list(command)
    scripts_seen = set()
    while arguments:
        executable = Path(arguments[0]).name
        if pnpm_only and executable in PACKAGE_MANAGERS - {"pnpm"}:
            raise ValueError(f"JavaScript checks must use pnpm, not: {executable}")
        if (
            executable not in {"npm", "pnpm", "yarn", "bun"}
            or len(arguments) <= 2
            or arguments[1] not in {"run", "run-script"}
        ):
            break
        if arguments[2] in scripts_seen:
            raise ValueError("Recursive package test script")
        scripts_seen.add(arguments[2])
        package = json.loads((directory / "package.json").read_text())
        script = package.get("scripts", {}).get(arguments[2])
        if not isinstance(script, str):
            raise TypeError("Configured package test script is missing")
        arguments = shlex.split(script) + arguments[3:]
        if not arguments:
            raise ValueError("Configured package test script is empty")
    return arguments


def javascript_manager(directory: Path) -> tuple[str, list[str], str]:
    manifest = json.loads((directory / "package.json").read_text())
    if manifest.get("workspaces") and not (directory / "pnpm-workspace.yaml").is_file():
        raise ValueError(
            "pnpm workspaces require pnpm-workspace.yaml; migrate the workspace declaration"
        )
    declared = manifest.get("packageManager")
    if declared is not None and (
        not isinstance(declared, str) or not declared.startswith("pnpm@")
    ):
        raise ValueError(
            f"{directory}: pnpm is required; migrate packageManager to pnpm@VERSION"
        )
    legacy = [
        name
        for name in (
            "package-lock.json",
            "npm-shrinkwrap.json",
            "yarn.lock",
            "bun.lock",
            "bun.lockb",
        )
        if (directory / name).exists()
    ]
    if legacy:
        raise ValueError(
            f"{directory}: pnpm is required; migrate and remove legacy lockfiles: "
            + ", ".join(legacy)
        )
    lockfile = "pnpm-lock.yaml"
    if not (directory / lockfile).exists() and not (directory / ".git").exists():
        for parent in directory.parents:
            if (parent / "package.json").exists() and workspace_matches(
                str(directory.relative_to(parent)),
                workspace_members(parent, "javascript"),
            ):
                return javascript_manager(parent)
            if (parent / ".git").exists():
                break
    if not (directory / lockfile).exists():
        raise ValueError(
            f"{directory}: pnpm-lock.yaml is required; run pnpm install and review the migration"
        )
    return "pnpm", ["pnpm", "install", "--frozen-lockfile"], lockfile


def adapt_sources(root: Path, package: Group, files: list[Path]) -> None:
    directory = root / package["path"]
    extensions = {
        "python": {".py"},
        "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"},
        "dart": {".dart"},
    }
    sources = set()
    for path in files:
        if (
            not path.is_relative_to(directory)
            or path.suffix not in extensions[package["language"]]
        ):
            continue
        relative = path.relative_to(directory)
        if nonproduction_source(relative) or {".hooks", ".agents"} & set(
            relative.parts
        ):
            continue
        sources.add(relative.parts[0])
    if sources:
        previous = package["sources"]
        package["sources"] = sorted(sources)
        for gate in package["checks"]:
            command = []
            for argument in gate["command"]:
                if argument in previous:
                    command.extend(package["sources"])
                elif argument.startswith("--cov="):
                    command.extend(
                        f"--cov={Path(source).stem if source.endswith('.py') else source}"
                        for source in package["sources"]
                    )
                else:
                    command.append(argument)
            gate["command"] = command


def dependency_command(directory: Path, language: str) -> tuple[str, list[str], str]:
    if language == "javascript":
        return javascript_manager(directory)
    if language == "python":
        if (directory / "poetry.lock").exists():
            return "poetry", ["poetry", "sync"], "poetry.lock"
        return "uv", ["uv", "sync", "--locked"], "uv.lock"
    import yaml

    manifest = yaml.safe_load((directory / "pubspec.yaml").read_text())
    dependencies = {
        **manifest.get("dependencies", {}),
        **manifest.get("dev_dependencies", {}),
    }
    manager = (
        "flutter"
        if any(
            isinstance(value, dict) and value.get("sdk") == "flutter"
            for value in dependencies.values()
        )
        else "dart"
    )
    return manager, [manager, "pub", "get", "--enforce-lockfile"], "pubspec.lock"


def adapt_packages(root: Path, config: GateConfig) -> None:
    owned: dict[Path, list[Path]] = {
        root / package["path"]: [] for package in config["packages"]
    }
    for path in repository_files(root):
        owner = next((parent for parent in path.parents if parent in owned), None)
        if owner is not None:
            owned[owner].append(path)
    for package in config["packages"]:
        directory = root / package["path"]
        adapt_sources(root, package, owned[directory])
        adapt_package(directory, package)
        for gate in package["checks"]:
            if gate.get("role") == "security":
                gate["command"] = [
                    os.path.relpath(root / argument, directory)
                    if argument == ".agents/skills/he/security"
                    else argument
                    for argument in gate["command"]
                ]
    adapt_workspaces(root, config)


def workspace_members(directory: Path, language: str) -> list[str]:
    if language == "python":
        project = tomllib.loads((directory / "pyproject.toml").read_text())
        workspace = project.get("tool", {}).get("uv", {}).get("workspace", {})
        return [
            *workspace.get("members", []),
            *("!" + value for value in workspace.get("exclude", [])),
        ]
    if language == "javascript" and not (directory / "pnpm-workspace.yaml").exists():
        return []
    import yaml

    name = "pubspec.yaml" if language == "dart" else "pnpm-workspace.yaml"
    manifest = yaml.safe_load((directory / name).read_text())
    return manifest.get("workspace" if language == "dart" else "packages", [])


def workspace_matches(relative: str, members: list[str]) -> bool:
    return any(
        fnmatchcase(relative, pattern)
        for pattern in members
        if not pattern.startswith("!")
    ) and not any(
        fnmatchcase(relative, pattern[1:])
        for pattern in members
        if pattern.startswith("!")
    )


def adapt_workspaces(root: Path, config: GateConfig) -> None:
    for owner in config["packages"]:
        directory, language = root / owner["path"], owner["language"]
        members = workspace_members(directory, language)
        if not members:
            continue
        for child in config["packages"]:
            path = root / child["path"]
            if (
                child is owner
                or child.get("language") != language
                or not path.is_relative_to(directory)
            ):
                continue
            relative = str(path.relative_to(directory))
            if workspace_matches(relative, members):
                child["checks"] = [
                    gate
                    for gate in child["checks"]
                    if gate.get("role") not in {"lockfiles", "vulnerabilities"}
                ]
        if language == "python":
            for gate in owner["checks"]:
                if gate.get("role") == "lockfiles" and gate["command"][:2] == [
                    "uv",
                    "sync",
                ]:
                    gate["command"].append("--all-packages")
        if not any((directory / source).exists() for source in owner["sources"]):
            owner["checks"] = [
                gate
                for gate in owner["checks"]
                if gate.get("role")
                in {
                    "lockfiles",
                    "vulnerabilities",
                    "build",
                    "integration",
                    "ui",
                    "generated",
                }
            ]
            owner.pop("language")
            owner.pop("sources")


def adapt_package(directory: Path, package: Group) -> None:
    language = package["language"]
    manager, install, lockfile = dependency_command(directory, language)
    for gate in package["checks"]:
        if gate.get("role") == "lockfiles":
            gate["command"] = install
        elif gate.get("role") == "vulnerabilities":
            gate["command"] = [
                f"--lockfile={lockfile}" if arg.startswith("--lockfile=") else arg
                for arg in gate["command"]
            ]
        elif language == "python" and gate["command"][0] in {
            "pytest",
            "deptry",
            "lint-imports",
        }:
            gate["command"] = python_gate_command(gate["command"], manager)
        elif language == "dart" and manager == "dart" and gate.get("role") == "tests":
            gate["command"] = [
                "dart",
                "run",
                "coverage:test_with_coverage",
                "--branch-coverage",
                "--",
                "--file-reporter=json:coverage/tests.jsonl",
            ]
            gate["report"]["stdout"] = False
    if language == "javascript":
        adapt_javascript(directory, package, manager)
    elif language == "python" and not python_roots(directory, package):
        package["checks"] = [
            gate for gate in package["checks"] if gate.get("role") != "imports"
        ]
    adapt_performance(directory, package)


def adapt_performance(directory: Path, package: Group) -> None:
    if any(
        (directory / name).is_file()
        for name in (
            "lighthouserc.js",
            "lighthouserc.cjs",
            "lighthouserc.json",
            "lighthouserc.yml",
            "lighthouserc.yaml",
            ".lighthouserc.js",
            ".lighthouserc.cjs",
            ".lighthouserc.json",
            ".lighthouserc.yml",
            ".lighthouserc.yaml",
        )
    ):
        for gate in package["checks"]:
            if gate.get("role") == "performance":
                gate["command"] = [
                    "lhci",
                    "autorun",
                    "--assert.includePassedAssertions",
                    "--upload.target=filesystem",
                    "--upload.outputDir=coverage/lighthouse",
                ]
                gate["report"] = {
                    "type": "lighthouse-ci",
                    "path": ".lighthouseci/assertion-results.json",
                }
    # Production builds and generators must finish before measurement begins.
    checks = package["checks"]
    package["checks"] = [
        gate for gate in checks if gate.get("role") != "performance"
    ] + [gate for gate in checks if gate.get("role") == "performance"]


def python_gate_command(command: list[str], manager: str) -> list[str]:
    packages = {
        "pytest": ["pytest", "pytest-cov"],
        "deptry": ["deptry"],
        "lint-imports": ["import-linter"],
    }[command[0]]
    prefix = ["uv", "run", "--no-sync"]
    if manager == "poetry":
        prefix = ["poetry", "run", "uv", "run", "--no-project", "--active"]
    for package in packages:
        prefix.extend(["--with", package, "--upgrade-package", package])
    return [*prefix, *command]


def python_interpreter(directory: Path, timeout: float) -> str:
    from tool_setup import managed_command

    manager, _, _ = dependency_command(directory, "python")
    command = (
        ["uv", "run", "--no-sync", "python", "-c", "import sys; print(sys.executable)"]
        if manager == "uv"
        else ["poetry", "env", "info", "--executable"]
    )
    environment = dict(os.environ)
    environment.pop("VIRTUAL_ENV", None)
    return subprocess.check_output(
        managed_command(command),
        cwd=directory,
        text=True,
        timeout=timeout,
        env=environment,
    ).strip()


def javascript_files(directory: Path) -> list[str]:
    extensions = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"}
    files = [
        str(path.relative_to(directory))
        for path in repository_files(directory)
        if path.suffix in extensions
        and not {"node_modules", "vendor", ".hooks", ".agents"}
        & set(path.relative_to(directory).parts)
    ]
    if not files:
        raise ValueError("No JavaScript or TypeScript source files found")
    return files


def adapt_javascript(directory: Path, package: Group, manager: str) -> None:
    manifest = json.loads((directory / "package.json").read_text())
    dependencies = {
        **manifest.get("dependencies", {}),
        **manifest.get("devDependencies", {}),
    }
    if "react" in dependencies:
        package["checks"].append(
            {
                "name": "react-doctor",
                "role": "react",
                "command": [
                    "react-doctor",
                    "--scope",
                    "full",
                    "--blocking",
                    "warning",
                    "--json",
                    "--json-out",
                    "coverage/react-doctor.json",
                ],
                "report": {
                    "type": "react-doctor",
                    "path": "coverage/react-doctor.json",
                },
            }
        )
    for script, role in (
        ("build", "build"),
        ("test:integration", "integration"),
        ("test:ui", "ui"),
        ("check:generated", "generated"),
    ):
        if script in manifest.get("scripts", {}):
            package["checks"].append(
                {"name": script, "role": role, "command": [manager, "run", script]}
            )


def python_roots(directory: Path, package: Group) -> list[str]:
    roots = set()
    for name in package["sources"]:
        path = directory / name
        if not path.is_dir():
            continue
        if (path / "__init__.py").exists() and name.isidentifier():
            roots.add(name)
        elif name == "src":
            roots.update(
                child.name
                for child in path.iterdir()
                if child.is_dir()
                and child.name.isidentifier()
                and (child / "__init__.py").exists()
            )
    return sorted(roots)


def import_configuration(directory: Path, package: Group, content: str) -> str:
    roots = python_roots(directory, package)
    if not roots or "importlinter" in tomllib.loads(content).get("tool", {}):
        return content
    ancestors = [value for root in roots for value in (root, root + ".**")]
    return content + (
        "\n[tool.importlinter]\nroot_packages = " + json.dumps(roots) + "\n"
        '\n[[tool.importlinter.contracts]]\nname = "No sibling dependency cycles"\n'
        'type = "acyclic_siblings"\nancestors = '
        + json.dumps(ancestors)
        + "\ndepth = 0\n"
    )


def configure_ci(
    root: Path, source: Path, config: GateConfig, changes: dict[str, str]
) -> None:
    name = ".github/workflows/hard-eng.yml"
    if (root / name).exists():
        return
    tools = ["uv@latest", "python@3.12", "node@latest"]
    for package in config["packages"]:
        directory = root / package["path"]
        language = package.get("language")
        if language not in {"python", "javascript", "dart"}:
            continue
        manager, _, _ = dependency_command(directory, language)
        if manager in {"dart", "flutter", "pnpm", "yarn", "bun", "poetry"}:
            version = "latest"
            if language == "javascript":
                declared = json.loads((directory / "package.json").read_text()).get(
                    "packageManager", ""
                )
                if declared.startswith(manager + "@"):
                    version = declared.split("@", 1)[1].split("+", 1)[0]
            specification = manager + "@" + version
            if specification not in tools:
                tools.append(specification)
    if "flutter@latest" in tools and "dart@latest" in tools:
        tools.remove("dart@latest")
    if any(package.get("language") == "dart" for package in config["packages"]):
        tools.append("rust@latest")
    changes[name] = (
        (source / name)
        .read_text()
        .replace("uv@latest python@3.12 node@latest", " ".join(tools))
    )

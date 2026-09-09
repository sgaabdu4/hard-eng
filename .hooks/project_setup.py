"""Adapt native template commands to the target project's existing stack."""

import json
import tomllib
from fnmatch import fnmatchcase
from pathlib import Path

from gate_config import GateConfig, Group, nonproduction_source, repository_files


def javascript_manager(directory: Path) -> tuple[str, list[str], str]:
    manifest = json.loads((directory / "package.json").read_text())
    declared = manifest.get("packageManager", "").split("@", 1)[0]
    locks = {
        "npm": "package-lock.json",
        "pnpm": "pnpm-lock.yaml",
        "yarn": "yarn.lock",
        "bun": "bun.lock",
    }
    found = [manager for manager, lock in locks.items() if (directory / lock).exists()]
    if (directory / "bun.lockb").exists():
        locks["bun"] = "bun.lockb"
        if "bun" not in found:
            found.append("bun")
    if declared and declared not in locks:
        raise ValueError(f"Unsupported package manager: {declared}")
    if not declared and len(found) > 1:
        raise ValueError(
            f"Ambiguous package manager in {directory}; preserve lockfiles and resolve the choice"
        )
    if not declared and not found and not (directory / ".git").exists():
        for parent in directory.parents:
            if (parent / "package.json").exists() and workspace_matches(
                str(directory.relative_to(parent)),
                workspace_members(parent, "javascript"),
            ):
                return javascript_manager(parent)
            if (parent / ".git").exists():
                break
    manager = declared or (found[0] if found else "npm")
    install = {
        "npm": ["npm", "ci", "--no-audit", "--no-fund"],
        "pnpm": ["pnpm", "install", "--frozen-lockfile"],
        "yarn": ["yarn", "install", "--immutable"],
        "bun": ["bun", "install", "--frozen-lockfile"],
    }[manager]
    if manager == "yarn" and (
        manifest.get("packageManager", "").startswith("yarn@1.")
        or (
            (directory / "yarn.lock").exists()
            and "yarn lockfile v1" in (directory / "yarn.lock").read_text()[:100]
        )
    ):
        install[-1] = "--frozen-lockfile"
    return manager, install, locks[manager]


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
                    command.extend(f"--cov={source}" for source in package["sources"])
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
    adapt_workspaces(root, config)


def workspace_members(directory: Path, language: str) -> list[str]:
    if language == "python":
        project = tomllib.loads((directory / "pyproject.toml").read_text())
        workspace = project.get("tool", {}).get("uv", {}).get("workspace", {})
        return [
            *workspace.get("members", []),
            *("!" + value for value in workspace.get("exclude", [])),
        ]
    if language == "javascript":
        manifest = json.loads((directory / "package.json").read_text())
        if not (directory / "pnpm-workspace.yaml").exists():
            members = manifest.get("workspaces", [])
            return members.get("packages", []) if isinstance(members, dict) else members
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
        elif language == "javascript" and gate["command"][:2] == ["npm", "run"]:
            gate["command"][0] = manager
        elif language == "python" and gate["command"][0] in {
            "pytest",
            "deptry",
            "lint-imports",
        }:
            gate["command"] = [manager, "run", *gate["command"]]
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
    changes[name] = (
        (source / name)
        .read_text()
        .replace("uv@latest python@3.12 node@latest", " ".join(tools))
    )

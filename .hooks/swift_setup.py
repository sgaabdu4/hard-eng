"""Swift groups for the Xcode projects in a Flutter app's ios/ and macos/ folders."""

import json
import os
from pathlib import Path
from typing import NamedTuple

from gate_config import (
    GateConfig,
    Group,
    generated_sources,
    package_manifests,
    repository_files,
)

PLATFORMS = ("ios", "macos")
NOT_AUTHORED = {"Flutter", "Pods"}
TEST_FLAGS = (
    "-only-testing",
    "-skip-testing",
    "-only-test-configuration",
    "-skip-test-configuration",
    "-testPlan",
)
TEMPLATE = Path(__file__).resolve().parents[1] / (
    ".agents/skills/he/templates/hard-eng.swift.json"
)


class SwiftProject(NamedTuple):
    sources: list[str]
    tests: list[str]
    pods: bool


def flutter_apps(root: Path, files: list[Path]) -> list[str]:
    from project_setup import dependency_command

    return sorted(
        path
        for path, language in package_manifests(root, files)
        if language == "dart"
        and dependency_command(root / path, "dart")[0] == "flutter"
    )


def swift_projects(
    root: Path, files: list[Path] | None = None
) -> dict[str, SwiftProject]:
    """Platform folders of Flutter apps that hold an Xcode project and authored Swift."""
    files = repository_files(root) if files is None else files
    names = [str(path.relative_to(root)) for path in files]
    authored = set(names) - generated_sources(root, names)
    found: dict[str, SwiftProject] = {}
    for app in flutter_apps(root, files):
        for platform in PLATFORMS:
            base = Path(app) / platform
            if str(base / "Runner.xcodeproj/project.pbxproj") not in authored:
                continue
            folders = {
                Path(name).relative_to(base).parts[0]
                for name in authored
                if name.endswith(".swift") and Path(name).is_relative_to(base)
            } - NOT_AUTHORED
            tests = {f for f in folders if f.removesuffix(".swift").endswith("Tests")}
            if sources := sorted(folders - tests):
                found[str(base)] = SwiftProject(
                    sources,
                    sorted(tests),
                    str(base / "Podfile") in authored,
                )
    return found


def swift_group(root: Path, path: str, project: SwiftProject) -> Group:
    package = json.loads(TEMPLATE.read_text())["packages"][0]
    directory = root / path
    expansion = {"Runner": project.sources, "RunnerTests": project.tests}
    package["name"] = package["path"] = path
    package["sources"] = project.sources
    for gate in package["checks"]:
        gate["command"] = [
            value
            for argument in gate["command"]
            for value in (
                [os.path.relpath(root / argument, directory)]
                if argument == ".agents/skills/he/security"
                else expansion.get(argument, [argument])
            )
        ]
    if project.pods:
        package["checks"].insert(
            0,
            {
                "name": "pods-locked",
                "role": "lockfiles",
                "command": [
                    "sh",
                    "-c",
                    'flutter precache --"$(basename "$PWD")" && pod install --deployment',
                ],
            },
        )
    return package


def add_swift_groups(root: Path, config: GateConfig) -> None:
    """Add a group for each Swift platform folder the configuration lacks."""
    declared = {str(Path(group["path"])) for group in config["packages"]}
    for path, project in swift_projects(root).items():
        if path not in declared:
            config["packages"].append(swift_group(root, path, project))


def require_swift_groups(root: Path, config: GateConfig, files: list[Path]) -> None:
    declared = {str(Path(group["path"])): group for group in config["packages"]}
    projects = swift_projects(root, files)
    if missing := sorted(set(projects) - declared.keys()):
        raise ValueError(
            f"Swift code is missing from gate configuration: {', '.join(missing)}; "
            "rerun setup to add its group"
        )
    for path, project in projects.items():
        if declared[path].get("language") != "swift":
            raise ValueError(
                f"{path}: the group holding Swift code must declare language swift"
            )
        roles = {gate.get("role") for gate in declared[path]["checks"]}
        if project.pods and "lockfiles" not in roles:
            raise ValueError(
                f"{path}: a Podfile needs the pods-locked gate (`pod install --deployment`) "
                "before the tests; add it as a lockfiles check"
            )
        if folders := unscanned(declared[path], project):
            raise ValueError(
                f"{path}: Swift folders {', '.join(folders)} are outside the group's "
                "sources or its format, duplicate and security commands; add them to each"
            )


def parent_roles(
    directory: Path, by_directory: dict[tuple[Path, str], Group]
) -> set[str]:
    """Roles a Flutter app supplies to the Swift group in its ios/ or macos/ folder."""
    parent = by_directory.get((directory.parent, "dart"))
    if directory.name not in PLATFORMS or parent is None:
        return set()
    return {gate.get("role", "") for gate in parent["checks"]}


def unscanned(group: Group, project: SwiftProject) -> list[str]:
    scopes = {
        "format-lint": [*project.sources, *project.tests],
        "duplicates": project.sources,
        "security": [*project.sources, *project.tests],
    }
    folders = {name for name in project.sources if name not in group["sources"]}
    for gate in group["checks"]:
        folders |= {
            name
            for name in scopes.get(gate.get("role", ""), [])
            if name not in gate["command"]
        }
    return sorted(folders)


def reject_test_filters(command: list[str]) -> None:
    for flag in TEST_FLAGS:
        if any(flag in argument for argument in command):
            raise ValueError(
                f"Focused test selection is not allowed in the full-suite gate: {flag}"
            )

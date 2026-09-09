"""Validate required documents and gate configuration before execution."""

import json
import re
import subprocess
from collections import deque
from pathlib import Path
from typing import NotRequired, TypedDict, cast

type JsonValue = (
    str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]
)
type JsonObject = dict[str, JsonValue]


Report = TypedDict(
    "Report",
    {"type": str, "path": str, "tests": str, "coverage": str, "stdout": bool},
    total=False,
)
Gate = TypedDict(
    "Gate",
    {
        "name": str,
        "command": list[str],
        "role": NotRequired[str],
        "parallel": NotRequired[bool],
        "report": NotRequired[Report],
    },
)
Group = TypedDict(
    "Group",
    {
        "path": str,
        "checks": list[Gate],
        "name": NotRequired[str],
        "language": NotRequired[str],
        "sources": NotRequired[list[str]],
        "depends_on": NotRequired[list[str]],
    },
)
GateConfig = TypedDict(
    "GateConfig",
    {
        "packages": list[Group],
        "shared": list[Gate],
        "version": NotRequired[int],
        "scan_git_history": NotRequired[bool],
        "file_size_exceptions": NotRequired[dict[str, dict[str, str]]],
    },
)

LANGUAGES = {
    "pyproject.toml": "python",
    "package.json": "javascript",
    "pubspec.yaml": "dart",
}


def package_manifests(root: Path, files: list[Path]) -> set[tuple[str, str]]:
    return {
        (str(path.parent.relative_to(root)), LANGUAGES[path.name])
        for path in files
        if path.name in LANGUAGES and ".agents" not in path.relative_to(root).parts
    }


def repository_files(root: Path) -> list[Path]:
    names = subprocess.check_output(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        text=True,
    )
    return [
        root / name
        for name in sorted(set(names.split("\0")) - {""})
        if (root / name).is_file() and not (root / name).is_symlink()
    ]


def nonproduction_source(relative: Path) -> bool:
    return bool(
        {"test", "tests", "__tests__", "node_modules", "vendor"} & set(relative.parts)
        or relative.name.startswith("test_")
        or relative.stem.endswith(("_test", ".test", ".spec"))
        or relative.name.endswith((".d.ts", ".d.mts", ".d.cts"))
    )


def generated_sources(root: Path, names: list[str]) -> set[str]:
    if not names:
        return set()
    repository = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if repository.returncode:
        return set()  # Standalone source directories have no Git attributes.
    attributes = subprocess.check_output(
        [
            "git",
            "check-attr",
            "-z",
            "--stdin",
            "linguist-generated",
            "linguist-vendored",
        ],
        cwd=root,
        text=True,
        input="\0".join(names) + "\0",
    ).split("\0")
    return {
        name
        for name, _, value in zip(attributes[::3], attributes[1::3], attributes[2::3])
        if value in {"set", "true"}
    }


def validate_file_sizes(root: Path, exceptions: dict[str, dict[str, str]]) -> None:
    if not isinstance(exceptions, dict):
        raise TypeError("File-size exceptions must be an object")
    extensions = {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".mjs",
        ".cjs",
        ".mts",
        ".cts",
        ".dart",
        ".sh",
        ".bash",
    }
    files = [path for path in repository_files(root) if path.suffix in extensions]
    names = [str(path.relative_to(root)) for path in files]
    for name, justification in exceptions.items():
        if (
            name not in names
            or not isinstance(justification, dict)
            or not all(
                isinstance(justification.get(key), str) and justification[key].strip()
                for key in ("reason", "evidence")
            )
        ):
            raise ValueError(
                "File-size exceptions require an exact existing file, reason and evidence"
            )
    generated = generated_sources(root, names)
    failures = []
    for path, name in zip(files, names):
        if name in generated or name in exceptions:
            continue
        lines = len(path.read_bytes().splitlines())
        if lines > 700:
            failures.append(f"{name}: {lines} lines")
    if failures:
        raise ValueError(
            "Handwritten files exceed 700 physical lines: " + "; ".join(failures)
        )


def validate_documents(root: Path) -> None:
    for name, required in (
        ("PRODUCT.md", ("Users", "Problem", "Product Purpose", "Boundaries")),
        ("DESIGN.md", ("Overview", "Components", "Do's and Don'ts")),
    ):
        path = root / name
        if not path.is_file():
            raise ValueError(f"{name} is required; fill it from the actual project")
        content = path.read_text().strip()
        if not content:
            raise ValueError(f"{name} is empty; fill it from the actual project")
        if "[todo:" in content.lower():
            raise ValueError(f"{name} contains unfilled template prompts")
        if not re.search(r"(?m)^# \S[^\n]*$", content):
            raise ValueError(f"{name} needs a document title using '# Title'")
        parts = re.split(r"(?m)^##[ \t]+([^\n]+)\n", content + "\n")
        sections = dict(zip((heading.strip() for heading in parts[1::2]), parts[2::2]))
        for heading in required:
            if not sections.get(heading, "").strip():
                raise ValueError(f"{name} needs a filled '## {heading}' section")
        order = [
            heading.strip() for heading in parts[1::2] if heading.strip() in required
        ]
        if order != list(required):
            raise ValueError(
                f"{name} sections must follow the template order without duplicates"
            )


def validate_gate(gate: Gate, directory: Path, report_paths: set[Path]) -> None:
    if (
        not isinstance(gate, dict)
        or not isinstance(gate.get("name"), str)
        or not gate["name"].strip()
    ):
        raise ValueError("Each check must have a nonempty name")
    if type(gate.get("parallel", False)) is not bool:
        raise ValueError("parallel must be true or false")
    report = gate.get("report", {})
    if not isinstance(report, dict):
        raise TypeError("report must be an object")
    for key in ("path", "tests", "coverage"):
        if key in report:
            value = report[key]
            if not isinstance(value, str) or not value:
                raise ValueError("Report paths must be nonempty strings")
            path = (directory / value).resolve()
            if path in report_paths:
                raise ValueError(f"Checks must use distinct report files: {path}")
            report_paths.add(path)
    command = gate.get("command")
    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(arg, str) for arg in command)
        or not command[0].strip()
    ):
        raise ValueError(
            f"{gate['name']}: command must be a nonempty list starting with an executable"
        )
    if "tool" in gate:
        raise ValueError(
            f"{gate['name']}: put the executable in command; separate tool fields are unsupported"
        )


def changed_packages(
    root: Path, by_path: dict[str, Group], base: str
) -> set[str] | None:
    try:
        changed = subprocess.check_output(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, "--"],
            cwd=root,
            text=True,
        )
        changed += subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard", "-z"],
            cwd=root,
            text=True,
        )
    except subprocess.CalledProcessError:
        print("Impact base unavailable; checking all packages.")
        return None
    names = set(changed.split("\0")) - {""}
    if not names:
        return None
    selected: set[str] = set()
    for name in names:
        matches = [path for path in by_path if Path(name).is_relative_to(path)]
        if (
            not matches
            or name.startswith((".hooks/", ".agents/", ".github/"))
            or name in {"hard-eng.gates.json", "AGENTS.md"}
        ):
            return None
        selected.add(max(matches, key=len))
    return selected


def affected_groups(root: Path, groups: list[Group], base: str | None) -> list[Group]:
    packages = groups[:-1]
    if (
        base is None
        or not packages
        or any("depends_on" not in group for group in packages)
    ):
        return groups
    by_path = {group["path"]: group for group in packages}
    if len(by_path) != len(packages):
        return groups
    dependents: dict[str, list[str]] = {name: [] for name in by_path}
    for group in packages:
        for dependency in group["depends_on"]:
            if dependency not in by_path:
                raise ValueError(f"Unknown package dependency: {dependency}")
            dependents[dependency].append(group["path"])
    selected = changed_packages(root, by_path, base)
    if selected is None:
        return groups
    pending = deque(selected)
    while pending:
        for dependent in dependents[pending.popleft()]:
            if dependent not in selected:
                selected.add(dependent)
                pending.append(dependent)
    print("Affected packages and dependents: " + ", ".join(sorted(selected)))
    return [group for group in packages if group["path"] in selected] + [groups[-1]]


def validate_performance_gate(gate: Gate) -> None:
    if gate.get("role") != "performance":
        return
    if gate.get("parallel", False):
        raise ValueError("Performance suites must run serially")
    if gate.get("report", {}).get("type") not in {
        "performance-junit",
        "performance-dart",
        "lighthouse-ci",
    }:
        raise ValueError("Performance suite requires a supported native report")


def validate_group(root: Path, group: Group, report_paths: set[Path]) -> int:
    if (
        not isinstance(group, dict)
        or not isinstance(group.get("path"), str)
        or not isinstance(group.get("checks"), list)
    ):
        raise TypeError("Each gate group must contain a path and checks list")
    directory = (root / group["path"]).resolve()
    if not directory.is_relative_to(root) or not directory.is_dir():
        raise ValueError(
            f"Gate directory must exist inside the project: {group['path']}"
        )
    if group.get("language") not in {None, *LANGUAGES.values()}:
        raise ValueError(f"Unsupported package language: {group.get('language')}")
    required = {
        "python": {
            "format",
            "lint",
            "complexity",
            "types",
            "annotations",
            "tests",
            "dead-code",
            "duplicates",
            "dependencies",
        },
        "javascript": {
            "format-lint",
            "focused-tests",
            "types",
            "typing-style",
            "tests",
            "dead-code-duplicates",
        },
        "dart": {"format", "types", "tests", "dead-code-duplicates"},
    }.get(group.get("language", ""), set())
    roles = {gate.get("role") for gate in group["checks"] if isinstance(gate, dict)}
    if required - roles:
        raise ValueError(
            f"{group['path']}: missing mandatory checks: {', '.join(sorted(required - roles))}"
        )
    if group.get("language") and "performance" not in roles:
        raise ValueError(
            "Missing mandatory performance suite; configure a workload and budget"
        )
    for gate in group["checks"]:
        validate_gate(gate, directory, report_paths)
        validate_performance_gate(gate)
    if group.get("language") == "javascript":
        from project_setup import javascript_manager, package_script_arguments

        javascript_manager(directory)
        for gate in group["checks"]:
            package_script_arguments(gate["command"], directory, pnpm_only=True)
    return len(group["checks"])


def require_roles(directory: str, required: set[str], roles: set[str]) -> None:
    if missing := required - roles:
        raise ValueError(
            f"{directory}: missing mandatory checks: {', '.join(sorted(missing))}"
        )


def validate_manifest_groups(
    root: Path, config: GateConfig, manifests: set[tuple[str, str]]
) -> None:
    from project_setup import workspace_members

    declared = {
        (str(Path(group["path"])), group.get("language")): group
        for group in config["packages"]
    }
    if len(declared) != len(config["packages"]):
        raise ValueError("Package path/language pairs must be unique")
    for path, language in manifests:
        if (path, language) in declared:
            continue
        group = declared.get((path, None))
        if group is None:
            raise ValueError(
                f"Supported {language} package is missing from gate configuration: {path}"
            )
        if group.get("sources") or not workspace_members(root / path, language):
            raise ValueError(f"{path}: package language must be {language}")


def validate_required_checks(root: Path, config: GateConfig) -> None:
    from project_setup import is_deployment_file, is_shell_script

    files = repository_files(root)
    manifests = package_manifests(root, files)
    validate_manifest_groups(root, config, manifests)
    if not config["packages"] and not manifests:
        return  # Ad-hoc command groups without a supported application manifest.
    shared_roles = {gate.get("role", "") for gate in config["shared"]}
    required = {"secrets-files"}
    if config.get("scan_git_history", True):
        required.add("secrets-history")
    if any(
        path.parent == root / ".github/workflows" and path.suffix in {".yml", ".yaml"}
        for path in files
    ):
        required.update({"workflows", "ci-security"})
    if any(is_shell_script(path) for path in files):
        required.add("shell")
    if any(is_deployment_file(path) for path in files):
        required.add("deployment")
    for gate in config["shared"]:
        command = gate["command"]
        shared_roles.update(
            {
                "actionlint": {"workflows"},
                "zizmor": {"ci-security"},
                "shellcheck": {"shell"},
            }.get(Path(command[0]).name, set())
        )
        if Path(command[0]).name == "trivy" and "config" in command[1:]:
            shared_roles.add("deployment")
    require_roles("shared", required, shared_roles)
    workspace_languages = dict(manifests)
    for group in config["packages"]:
        validate_package_services(
            root, group, config, workspace_languages, shared_roles
        )


def validate_package_services(
    root: Path,
    group: Group,
    config: GateConfig,
    manifests: dict[str, str],
    shared_roles: set[str],
) -> None:
    from project_setup import python_roots, workspace_matches, workspace_members

    directory = (root / group["path"]).resolve()
    language = group.get("language") or manifests.get(str(Path(group["path"])), "")
    roles = {gate.get("role", "") for gate in group["checks"]}
    inherited = set(shared_roles)
    for parent in config["packages"]:
        owner = (root / parent["path"]).resolve()
        owner_language = parent.get("language") or manifests.get(
            str(Path(parent["path"])), ""
        )
        if (
            owner != directory
            and owner_language == language
            and directory.is_relative_to(owner)
            and workspace_matches(
                str(directory.relative_to(owner)), workspace_members(owner, language)
            )
        ):
            inherited.update(gate.get("role", "") for gate in parent["checks"])
    require_roles(group["path"], {"lockfiles", "vulnerabilities"}, roles | inherited)
    if not group.get("language"):
        return
    require_roles(group["path"], {"security"}, roles | shared_roles)
    if language == "python" and python_roots(directory, group):
        require_roles(group["path"], {"imports"}, roles)
    if language == "javascript":
        manifest = json.loads((directory / "package.json").read_text())
        dependencies = {
            **manifest.get("dependencies", {}),
            **manifest.get("devDependencies", {}),
        }
        required = {"react"} if "react" in dependencies else set()
        required.update(
            role
            for script, role in {
                "build": "build",
                "test:integration": "integration",
                "test:ui": "ui",
                "check:generated": "generated",
            }.items()
            if script in manifest.get("scripts", {})
        )
        require_roles(group["path"], required, roles)


def load_groups(root: Path, base: str | None = None) -> list[Group]:
    validate_documents(root)
    config = cast(GateConfig, json.loads((root / "hard-eng.gates.json").read_text()))
    if (
        not isinstance(config, dict)
        or not isinstance(config.get("packages"), list)
        or not isinstance(config.get("shared"), list)
    ):
        raise TypeError("Gate configuration must contain packages and shared lists")
    if type(config.get("scan_git_history", True)) is not bool:
        raise TypeError("scan_git_history must be true or false")
    validate_file_sizes(root, config.get("file_size_exceptions", {}))
    if config.get("scan_git_history", True) is False:
        config["shared"] = [
            gate for gate in config["shared"] if gate.get("role") != "secrets-history"
        ]
    groups: list[Group] = [
        *config["packages"],
        {"path": ".", "checks": config["shared"]},
    ]
    report_paths: set[Path] = set()
    count = sum(validate_group(root, group, report_paths) for group in groups)
    if not count:
        raise ValueError("No checks configured; verification cannot pass")
    validate_required_checks(root, config)
    return affected_groups(root, groups, base)

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
    attributes = subprocess.check_output(
        ["git", "check-attr", "-z", "--stdin", "linguist-generated"],
        cwd=root,
        text=True,
        input="\0".join(names) + ("\0" if names else ""),
    ).split("\0")
    generated = {
        name
        for name, _, value in zip(attributes[::3], attributes[1::3], attributes[2::3])
        if value in {"set", "true"}
    }
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
    required = {
        "python": {"types", "annotations"},
        "javascript": {"types", "typing-style"},
        "dart": {"types"},
    }.get(group.get("language", ""), set())
    roles = {gate.get("role") for gate in group["checks"] if isinstance(gate, dict)}
    if required - roles:
        raise ValueError(
            f"Missing mandatory typing checks: {', '.join(sorted(required - roles))}"
        )
    for gate in group["checks"]:
        validate_gate(gate, directory, report_paths)
    return len(group["checks"])


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
    return affected_groups(root, groups, base)

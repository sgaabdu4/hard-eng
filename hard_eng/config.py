"""Validate repository-owned commands and their mandatory gate coverage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from hard_eng.common import (
    GateError,
    Json,
    array,
    object_value,
    read_json,
    relative_path,
    source_files,
    strings,
)

LANGUAGE_ROLES = {
    "python": {"format", "lint", "types", "tests", "dead-code", "duplicates", "dependencies", "imports"},
    "javascript": {"format-lint", "types", "tests", "dead-code-duplicates"},
    "dart": {"format", "lint", "tests", "dead-code-duplicates"},
}


@dataclass(frozen=True)
class Check:
    name: str
    role: str
    package: str
    cwd: Path
    command: tuple[str, ...]
    tool: str | None
    timeout: int
    report: Json


@dataclass(frozen=True)
class Package:
    name: str
    path: Path
    language: str
    sources: tuple[str, ...]
    depends_on: tuple[str, ...]
    checks: tuple[Check, ...]


@dataclass(frozen=True)
class Config:
    root: Path
    packages: tuple[Package, ...]
    shared: tuple[Check, ...]
    raw: Json


def nonempty(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise GateError(f"{label} must be a nonempty string")
    return value


def check(value: object, package: str, cwd: Path) -> Check:
    data = object_value(value, "check")
    name = nonempty(data.get("name"), "check name")
    role = nonempty(data.get("role"), f"{name} role")
    command = strings(data.get("command"), f"{name} command")
    if any("[TODO:" in argument for argument in command):
        raise GateError(f"{name}: replace the template command with the repository's real check")
    tool = data.get("tool")
    if not command and not tool:
        raise GateError(f"{name}: empty command")
    if tool is not None and not isinstance(tool, str):
        raise GateError(f"{name}: tool must be a name")
    timeout = data.get("timeout", 600)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout <= 0:
        raise GateError(f"{name}: timeout must be positive seconds")
    report = object_value(data.get("report", {}), f"{name} report")
    required_reports = {
        "fallow": "fallow",
        "dart-decimate": "dart-decimate",
        "react-doctor": "react-doctor",
        "trivy": "trivy",
    }
    if tool in required_reports and report.get("type") != required_reports[tool]:
        raise GateError(
            f"{name}: {tool} requires its complete JSON report; exit status alone is insufficient"
        )
    return Check(name, role, package, cwd, tuple(command), tool, timeout, report)


def package(value: object, root: Path) -> Package:
    data = object_value(value, "package")
    name = nonempty(data.get("name"), "package name")
    path = relative_path(root, nonempty(data.get("path"), f"{name} path"))
    language = nonempty(data.get("language"), f"{name} language")
    if language not in LANGUAGE_ROLES:
        raise GateError(f"Unsupported language: {language}")
    sources = strings(data.get("sources"), f"{name} production sources")
    if not sources or not all(relative_path(path, source).exists() for source in sources):
        raise GateError(f"{name}: production sources must exist")
    checks = tuple(check(item, name, path) for item in array(data.get("checks"), f"{name} checks"))
    required = LANGUAGE_ROLES[language].copy()
    node: Json = (
        read_json(path / "package.json")
        if language == "javascript" and (path / "package.json").is_file()
        else {}
    )
    dependencies = object_value(node.get("dependencies", {}), "Node dependencies")
    scripts = object_value(node.get("scripts", {}), "Node scripts")
    if data.get("react") or "react" in dependencies:
        required.add("react")
    if data.get("build") or "build" in scripts:
        required.add("build")
    if data.get("ui"):
        required.add("ui")
    if language == "python" and not any(relative_path(path, source).is_dir() for source in sources):
        required.discard("imports")
    missing = required - {item.role for item in checks}
    if missing:
        raise GateError(f"{name}: missing checks: {', '.join(sorted(missing))}")
    test_checks = [item for item in checks if item.role == "tests"]
    if any(
        item.report.get("type") not in {"python-tests", "lcov-tests", "dart-tests"} for item in test_checks
    ):
        raise GateError(f"{name}: tests require test-count and production coverage reports")
    return Package(
        name, path, language, tuple(sources), tuple(strings(data.get("depends_on", []), "dependents")), checks
    )


def shared_roles(root: Path) -> set[str]:
    roles = {"secrets-files", "secrets-history", "vulnerabilities", "security"}
    if (root / ".github/workflows").is_dir():
        roles |= {"workflows", "workflow-security"}
    files = source_files(root) if (root / ".git").exists() else list(root.rglob("*"))
    if any(path.suffix in {".sh", ".bash"} for path in files):
        roles.add("shell")
    if any(
        path.name in {"Dockerfile", "compose.yaml", "compose.yml", "docker-compose.yml"}
        or path.suffix == ".tf"
        for path in files
    ):
        roles.add("deployment")
    return roles


def load(root: Path) -> Config:
    data = read_json(root / "hard-eng.gates.json")
    if data.get("version") != 1:
        raise GateError("hard-eng.gates.json requires version 1")
    packages = tuple(package(item, root) for item in array(data.get("packages"), "packages"))
    if not packages or len({item.name for item in packages}) != len(packages):
        raise GateError("At least one package with unique names is required")
    names = {item.name for item in packages}
    for item in packages:
        if set(item.depends_on) - names or item.name in item.depends_on:
            raise GateError(f"{item.name}: invalid dependency names")
    shared = tuple(check(item, "shared", root) for item in array(data.get("shared"), "shared checks"))
    missing = shared_roles(root) - {item.role for item in shared}
    if data.get("scan_git_history") is False:
        missing.discard("secrets-history")
    if data.get("container_images") and not any(item.role == "container-vulnerabilities" for item in shared):
        missing.add("container-vulnerabilities")
    if missing:
        raise GateError(f"Missing shared checks: {', '.join(sorted(missing))}")
    checks = [item for pkg in packages for item in pkg.checks] + list(shared)
    if len({item.name for item in checks}) != len(checks):
        raise GateError("Check names must be unique across the repository")
    return Config(root, packages, shared, data)


def affected(config: Config, changed: list[Path] | None) -> tuple[Package, ...]:
    if changed is None or not changed:
        return config.packages
    names: set[str] = set()
    for path in changed:
        owners = {pkg.name for pkg in config.packages if path.is_relative_to(pkg.path)}
        if not owners:
            return config.packages
        names |= owners
    while True:
        expanded = names | {pkg.name for pkg in config.packages if set(pkg.depends_on) & names}
        if expanded == names:
            return tuple(pkg for pkg in config.packages if pkg.name in names)
        names = expanded

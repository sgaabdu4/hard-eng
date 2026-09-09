"""Detect actual service dependencies and retain explicit project identities."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from hard_eng.common import GateError, Json, array, object_value, read_json, source_files


def dependency_names(path: Path) -> list[str]:
    if path.name == "package.json":
        data = read_json(path)
        return [
            name
            for field in ("dependencies", "devDependencies", "optionalDependencies")
            for name in object_value(data.get(field, {}), field)
        ]
    if path.name == "pyproject.toml":
        data = tomllib.loads(path.read_text())
        project = object_value(data.get("project", {}), "Python project")
        return [str(value) for value in array(project.get("dependencies", []), "Python dependencies")]
    if path.name == "pubspec.yaml" or (path.name.startswith("requirements") and path.suffix == ".txt"):
        return re.findall(
            r"(?m)^\s*(sentry[-_\w]*|(?:dart[-_]|node[-_])?appwrite)(?=\s*[:[<>=!~;]|\s*$)", path.read_text()
        )
    return []


def detected(root: Path) -> set[str]:
    names = [name.lower() for path in source_files(root) for name in dependency_names(path)]
    services: set[str] = set()
    if any(re.match(r"(?:@sentry/|sentry(?:[-_\[<>=;!~]|$))", name) for name in names):
        services.add("sentry")
    if any(re.match(r"(?:(?:node|dart)[-_])?appwrite(?:[\[<>=;!~]|$)", name) for name in names):
        services.add("appwrite")
    return services


def settings(root: Path) -> Json:
    data = read_json(root / "hard-eng.gates.json")
    declared = object_value(data.get("services", {}), "service MCP settings")
    required = detected(root)
    missing = required - declared.keys()
    if missing:
        raise GateError(
            f"Configure service MCP project identity and read-only readiness call for: {', '.join(sorted(missing))}"
        )
    result: Json = {}
    for name in sorted(required):
        value = object_value(declared[name], f"{name} settings")
        fields = ("organization", "project") if name == "sentry" else ("endpoint", "project")
        if any(not isinstance(value.get(field), str) or not value[field] for field in fields):
            raise GateError(f"{name}: expected explicit {' and '.join(fields)}")
        probe = object_value(value.get("readiness"), f"{name} read-only readiness call")
        if not isinstance(probe.get("tool"), str) or not probe["tool"]:
            raise GateError(f"{name}: name the native read-only project lookup tool")
        object_value(probe.get("arguments"), f"{name} readiness arguments")
        result[name] = value
    return result


def servers(root: Path) -> Json:
    result: Json = {}
    for name, raw in settings(root).items():
        value = object_value(raw, f"{name} settings")
        if name == "sentry":
            result[name] = {"url": "https://mcp.sentry.dev/mcp"}
        elif "server" in value:
            result[name] = object_value(value["server"], "Appwrite server configuration")
        elif (urlparse(str(value["endpoint"])).hostname or "").endswith(".appwrite.io"):
            result[name] = {"url": "https://mcp.appwrite.io/mcp"}
        else:
            raise GateError(
                "Self-hosted Appwrite needs its actual MCP server configuration; cloud MCP cannot verify it"
            )
    return result

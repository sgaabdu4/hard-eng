#!/usr/bin/env python3
"""Read-only validation of the pinned Copilot Context Mode plugin state."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import NoReturn

from jsonc import JsoncError, loads


MATCH = 0
MISSING = 3
CONFLICT = 4
DRIFT = 5


def fail(message: str, code: int = 2) -> NoReturn:
    print(f"setup:copilot: {message}", file=sys.stderr)
    raise SystemExit(code)


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        fail(f"missing required environment value: {name}")
    return value


def required_path(name: str) -> Path:
    value = required_env(name)
    path = Path(value)
    if not path.is_absolute():
        fail(f"{name} must be an absolute path: {value}")
    return path


def regular_directory(path: Path, description: str) -> None:
    if path.is_symlink() or not path.is_dir():
        fail(f"{description} is not a regular directory: {path}")


def regular_file(path: Path, description: str) -> None:
    if path.is_symlink() or not path.is_file():
        fail(f"{description} is not a regular file: {path}")


def source_path() -> Path:
    source = required_path("COPILOT_PLUGIN_SOURCE")
    regular_directory(source, "Context Mode plugin source")
    manifest = source / ".github/plugin/plugin.json"
    regular_file(manifest, "Context Mode plugin manifest")
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"Context Mode plugin manifest is invalid: {error}")
    if not isinstance(value, dict):
        fail("Context Mode plugin manifest must be an object")
    expected_name = required_env("COPILOT_PLUGIN_NAME")
    expected_version = required_env("COPILOT_CONTEXT_VERSION")
    if value.get("name") != expected_name or value.get("version") != expected_version:
        fail("Context Mode plugin source does not match the pinned manifest")
    return source


def config_path() -> Path:
    directory = required_path("COPILOT_CONFIG_DIR")
    regular_directory(directory, "Copilot home")
    return directory / "config.json"


def load_config(path: Path) -> dict:
    if not os.path.lexists(path):
        return {}
    regular_file(path, "Copilot config")
    try:
        value = loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, JsoncError) as error:
        fail(f"Copilot config is not valid JSONC: {error}")
    if not isinstance(value, dict):
        fail("Copilot config must be an object")
    return value


def validate_cache(
    cache: Path, installed_root: Path, source: Path
) -> None:
    if not cache.is_absolute():
        fail("managed Copilot plugin cache path is not absolute", CONFLICT)
    try:
        cache.relative_to(installed_root)
    except ValueError:
        fail("managed Copilot plugin cache escapes installed-plugins", CONFLICT)
    if cache.is_symlink() or not cache.is_dir():
        fail(f"managed Copilot plugin cache is missing or not a directory: {cache}", DRIFT)
    relative_files = (
        ".github/plugin/plugin.json",
        ".mcp.json",
        "hooks.json",
        "skills/context-mode/SKILL.md",
    )
    for relative in relative_files:
        source_file = source / relative
        cache_file = cache / relative
        regular_file(source_file, f"Context Mode source file {relative}")
        regular_file(cache_file, f"installed Context Mode file {relative}")
        try:
            if source_file.read_bytes() != cache_file.read_bytes():
                fail(f"installed Context Mode file drifted: {relative}", DRIFT)
        except OSError as error:
            fail(f"could not compare Context Mode file {relative}: {error}", DRIFT)


def plugin_status() -> int:
    source = source_path()
    path = config_path()
    if not path.exists():
        return MISSING
    config = load_config(path)
    installed = config.get("installedPlugins")
    if installed is None:
        return MISSING
    if not isinstance(installed, list):
        fail("Copilot installedPlugins state is missing or invalid", DRIFT)
    name = required_env("COPILOT_PLUGIN_NAME")
    matches = [
        item
        for item in installed
        if isinstance(item, dict) and item.get("name") == name
    ]
    if not matches:
        return MISSING
    if len(matches) != 1:
        fail("duplicate managed Copilot Context Mode plugins", CONFLICT)
    entry = matches[0]
    source_entry = entry.get("source")
    if (
        not isinstance(source_entry, dict)
        or source_entry.get("source") != "local"
    ):
        fail("managed Copilot plugin name belongs to another source", CONFLICT)
    if source_entry.get("path") != str(source):
        legacy_source = os.environ.get("COPILOT_LEGACY_PLUGIN_SOURCE")
        if source_entry.get("path") != legacy_source:
            fail("managed Copilot plugin name belongs to another source", CONFLICT)
        return DRIFT
    if (
        entry.get("version") != required_env("COPILOT_CONTEXT_VERSION")
        or entry.get("enabled") is not True
    ):
        return DRIFT
    cache_value = entry.get("cache_path")
    if not isinstance(cache_value, str):
        fail("managed Copilot plugin cache path is missing", DRIFT)
    installed_root = path.parent / "installed-plugins"
    if not installed_root.is_dir() or installed_root.is_symlink():
        fail("Copilot installed-plugins directory is missing", DRIFT)
    validate_cache(Path(cache_value), installed_root, source)
    return MATCH


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] != "status":
        fail("usage: copilot-plugin-state.py status")
    return plugin_status()


if __name__ == "__main__":
    raise SystemExit(main())

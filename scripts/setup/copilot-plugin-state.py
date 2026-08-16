#!/usr/bin/env python3
"""Read-only validation of the pinned Copilot Context Mode plugin state."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import NoReturn

from jsonc import JsoncError, loads

SETUP_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = SETUP_DIR.parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.setup import safe_file


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
    try:
        with safe_file.parent_fd(path.parent, Path(path.name)) as (directory, name):
            metadata = os.stat(name, dir_fd=directory, follow_symlinks=False)
    except OSError as error:
        fail(f"{description} is not a safe directory: {path}: {error}")
    if not stat.S_ISDIR(metadata.st_mode) or metadata.st_uid != os.getuid():
        fail(f"{description} is not a current-user directory: {path}")


def regular_file(path: Path, description: str) -> None:
    try:
        safe_file.read_snapshot(path.parent, Path(path.name))
    except OSError as error:
        fail(f"{description} is not a safe regular file: {path}: {error}")


def tree_manifest(root: Path) -> tuple[tuple[str, str, int, str], ...]:
    regular_directory(root, "plugin tree root")
    records: list[tuple[str, str, int, str]] = []
    for path in sorted(root.rglob("*"), key=lambda item: os.fsencode(str(item.relative_to(root)))):
        relative = path.relative_to(root).as_posix()
        metadata = path.lstat()
        if metadata.st_uid != os.getuid():
            fail(f"plugin tree entry has another owner: {path}", DRIFT)
        mode = stat.S_IMODE(metadata.st_mode)
        if stat.S_ISDIR(metadata.st_mode):
            records.append((relative, "directory", mode, ""))
        elif stat.S_ISREG(metadata.st_mode):
            try:
                content, observed_mode = safe_file.read_snapshot(
                    path.parent, Path(path.name)
                )
            except OSError as error:
                fail(f"plugin tree file is unsafe: {path}: {error}", DRIFT)
            if observed_mode != mode:
                fail(f"plugin tree file mode changed while reading: {path}", DRIFT)
            records.append((relative, "file", mode, hashlib.sha256(content).hexdigest()))
        else:
            fail(f"plugin tree contains a link or special entry: {path}", DRIFT)
    return tuple(records)


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
    regular_directory(cache, "managed Copilot plugin cache")
    if tree_manifest(cache) != tree_manifest(source):
        fail("installed Context Mode plugin tree drifted", DRIFT)


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

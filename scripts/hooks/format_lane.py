#!/usr/bin/env python3
"""Format the files a turn actually edited, once the turn is over."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

EDIT_TTL_SECONDS = 6 * 60 * 60
EDIT_LIMIT = 400
TOOL_TIMEOUT_SECONDS = 20
REPORT_FILE_LIMIT = 4
SKIP_PARTS = {".dart_tool", ".git", "build", "dist", "node_modules", "vendor"}

BIOME_SUFFIXES = {
    ".cjs",
    ".css",
    ".cts",
    ".js",
    ".json",
    ".jsonc",
    ".jsx",
    ".mjs",
    ".mts",
    ".ts",
    ".tsx",
}
PRETTIER_SUFFIXES = BIOME_SUFFIXES | {
    ".html",
    ".less",
    ".md",
    ".scss",
    ".svelte",
    ".vue",
    ".yaml",
    ".yml",
}

Builder = Callable[[Path, list[str]], list[list[str]]]


def repository_binary(root: Path, name: str) -> str | None:
    candidate = root / "node_modules" / ".bin" / name
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return str(candidate)
    return None


def biome(root: Path, files: list[str]) -> list[list[str]]:
    binary = repository_binary(root, "biome")
    if binary is None:
        return []
    return [[binary, "check", "--write", "--no-errors-on-unmatched", *files]]


def prettier(root: Path, files: list[str]) -> list[list[str]]:
    binary = repository_binary(root, "prettier")
    if binary is None:
        return []
    return [[binary, "--write", "--log-level", "warn", *files]]


def ruff(root: Path, files: list[str]) -> list[list[str]]:
    binary = repository_binary(root, "ruff") or shutil.which("ruff")
    if binary is None:
        return []
    return [[binary, "format", "--quiet", *files]]


def dart_package(path: Path, root: Path) -> Path | None:
    for candidate in [path, *path.parents]:
        if (candidate / "pubspec.yaml").is_file():
            return candidate
        if candidate == root:
            break
    return None


def dart(root: Path, files: list[str]) -> list[list[str]]:
    binary = shutil.which("dart")
    if binary is None:
        return []
    planned = [[binary, "format", *files]]
    # `dart fix` has no file argument: it fixes whatever package it is run in, so
    # it is scoped by running it once per package that this turn actually touched.
    packages = sorted(
        {
            str(package)
            for name in files
            if (package := dart_package(Path(name).parent, root)) is not None
        }
    )
    planned += [[binary, "fix", "--apply", package] for package in packages]
    return planned


TOOLS: tuple[tuple[set[str], Builder], ...] = (
    (BIOME_SUFFIXES, biome),
    (PRETTIER_SUFFIXES, prettier),
    ({".dart"}, dart),
    ({".py"}, ruff),
)

KNOWN_SUFFIXES = {suffix for suffixes, _ in TOOLS for suffix in suffixes}


def record(state: dict, targets: list[Path]) -> None:
    """Remember what this turn wrote; no runtime hands the list over at the end."""
    edits = state.get("edits")
    if not isinstance(edits, dict):
        edits = {}
        state["edits"] = edits
    now = time.time()
    for target in targets:
        if target.suffix.lower() not in KNOWN_SUFFIXES:
            continue
        if SKIP_PARTS.intersection(target.parts):
            continue
        try:
            edits[str(target.resolve())] = now
        except OSError:
            continue
    for name in sorted(edits, key=lambda key: edits[key])[: len(edits) - EDIT_LIMIT]:
        edits.pop(name, None)


def pending(state: dict) -> list[Path]:
    edits = state.get("edits")
    if not isinstance(edits, dict):
        return []
    oldest = time.time() - EDIT_TTL_SECONDS
    paths = [
        Path(name)
        for name, stamp in edits.items()
        if isinstance(stamp, (int, float)) and stamp >= oldest
    ]
    return sorted(path for path in paths if path.is_file())


def signature(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def commands(root: Path, paths: list[Path]) -> list[list[str]]:
    remaining = set(paths)
    planned: list[list[str]] = []
    for suffixes, build in TOOLS:
        claimed = sorted(path for path in remaining if path.suffix.lower() in suffixes)
        if not claimed:
            continue
        built = build(root, [str(path) for path in claimed])
        if not built:
            continue
        planned += built
        remaining.difference_update(claimed)
    return planned


def group(paths: list[Path], root_of: Callable[[Path], Path | None]) -> dict[Path, list[Path]]:
    grouped: dict[Path, list[Path]] = {}
    for path in paths:
        root = root_of(path.parent)
        if root is not None:
            grouped.setdefault(root, []).append(path)
    return grouped


def run(state: dict, root_of: Callable[[Path], Path | None]) -> str | None:
    paths = pending(state)
    state.pop("edits", None)
    rewritten: list[str] = []
    for root, owned in sorted(group(paths, root_of).items()):
        before = {path: signature(path) for path in owned}
        for command in commands(root, owned):
            try:
                subprocess.run(
                    command,
                    cwd=str(root),
                    capture_output=True,
                    timeout=TOOL_TIMEOUT_SECONDS,
                )
            except (OSError, subprocess.SubprocessError):
                continue
        rewritten += [
            str(path.relative_to(root)) for path in owned if signature(path) != before[path]
        ]
    if not rewritten:
        return None
    named = ", ".join(sorted(rewritten)[:REPORT_FILE_LIMIT])
    if len(rewritten) > REPORT_FILE_LIMIT:
        named += f" and {len(rewritten) - REPORT_FILE_LIMIT} more"
    return f"format lane: rewrote {named}. Re-read those files before editing them again."

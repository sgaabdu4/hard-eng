#!/usr/bin/env python3
"""Converge the pinned Context Mode runtime's native bootstrap policy."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


PATCH_MARKER = "// hard-eng managed runtime: use built-in SQLite when it provides FTS5"
FUNCTION_ANCHOR = """function hasModernSqlite() {
  if (typeof globalThis.Bun !== "undefined") return true;
  const [major, minor] = process.versions.node.split(".").map(Number);
  return major > 22 || (major === 22 && minor >= 5);
}

"""
ENSURE_ANCHOR = "export async function ensureDeps() {\n"
PATCH_BODY = """// hard-eng managed runtime: use built-in SQLite when it provides FTS5
const BUILTIN_SQLITE_FTS5_PROBE = "__hard_eng_context_mode_fts5_probe";

function hasUsableBuiltinSqlite() {
  if (!hasModernSqlite()) return false;
  let database;
  try {
    const { DatabaseSync } = createRequire(import.meta.url)(["node", "sqlite"].join(":"));
    database = new DatabaseSync(":memory:");
    database.exec(`CREATE VIRTUAL TABLE ${BUILTIN_SQLITE_FTS5_PROBE} USING fts5(body)`);
    return true;
  } catch {
    return false;
  } finally {
    try { database?.close(); } catch { /* probe cleanup */ }
  }
}

"""


def fail(message: str) -> None:
    raise SystemExit(f"setup:context-mode-runtime: {message}")


def load_hook(package_root: Path, expected_version: str) -> Path:
    package_file = package_root / "package.json"
    hook_file = package_root / "hooks/ensure-deps.mjs"
    if not package_root.is_dir() or package_root.is_symlink():
        fail(f"Context Mode package root is not a regular directory: {package_root}")
    try:
        package = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"could not read Context Mode package metadata: {error}")
    if package.get("name") != "context-mode" or package.get("version") != expected_version:
        fail(f"unexpected Context Mode package identity: {package.get('name')}@{package.get('version')}")
    if not hook_file.is_file() or hook_file.is_symlink():
        fail(f"Context Mode dependency hook is not a regular file: {hook_file}")
    return hook_file


def patched_source(source: str) -> str:
    if PATCH_MARKER in source:
        return source
    if source.count(FUNCTION_ANCHOR) != 1:
        fail("pinned Context Mode dependency hook changed its SQLite capability anchor")
    if source.count(ENSURE_ANCHOR) != 1:
        fail("pinned Context Mode dependency hook changed its bootstrap anchor")
    source = source.replace(FUNCTION_ANCHOR, FUNCTION_ANCHOR + PATCH_BODY, 1)
    source = source.replace(
        ENSURE_ANCHOR,
        ENSURE_ANCHOR + "  if (hasUsableBuiltinSqlite()) return;\n",
        1,
    )
    return source


def check_source(source: str) -> None:
    if source.count(PATCH_MARKER) != 1:
        fail("Context Mode dependency hook is missing the managed runtime overlay")
    if PATCH_BODY not in source:
        fail("Context Mode dependency hook overlay is incomplete")
    if source.count("  if (hasUsableBuiltinSqlite()) return;\n") != 1:
        fail("Context Mode dependency hook has an invalid bootstrap guard")


def write_atomic(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".hard-eng-context-mode-", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str]) -> int:
    if len(argv) != 4 or argv[1] not in {"apply", "check"}:
        raise SystemExit(
            f"usage: {argv[0]} <apply|check> <context-mode-package-root> <version>"
        )
    operation, package_root, expected_version = argv[1:]
    hook_file = load_hook(Path(package_root), expected_version)
    source = hook_file.read_text(encoding="utf-8")
    if operation == "apply":
        updated = patched_source(source)
        if updated != source:
            write_atomic(hook_file, updated)
        check_source(updated)
    else:
        check_source(source)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

#!/usr/bin/env python3
"""Resolve local JavaScript-family default imports to their owning module."""

from __future__ import annotations

import re
from pathlib import Path


JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")
DEFAULT_IMPORT = re.compile(
    r"import\s+(?:type\s+)?([A-Za-z_$][\w$]*)\s+from\s+[\"']([^\"']+)[\"']"
)
DEFAULT_DECL = re.compile(
    r"\bexport\s+default\s+(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)\b"
)
DEFAULT_REF = re.compile(r"\bexport\s+default\s+([A-Za-z_$][\w$]*)\s*;?\s*$", re.MULTILINE)
DEFINITION = re.compile(
    r"\b(?:class|function)\s+([A-Za-z_$][\w$]*)|"
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
)


class JsImportError(RuntimeError):
    pass


def module_path(root: Path, importer: str, specifier: str) -> Path:
    base = (root / importer).parent / specifier
    candidates = [
        *(base.with_suffix(suffix) if not base.suffix else base for suffix in JS_SUFFIXES),
        *(base / f"index{suffix}" for suffix in JS_SUFFIXES),
    ]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            continue
        if not candidate.is_symlink() and resolved.is_file() and resolved.suffix in JS_SUFFIXES:
            return resolved
    raise JsImportError(f"unresolved local default import: {specifier} from {importer}")


def default_owner(lines: list[str], relative: str) -> tuple[str, int]:
    text = "\n".join(lines)
    match = DEFAULT_DECL.search(text) or DEFAULT_REF.search(text)
    if match:
        name = match.group(1)
        for number, line in enumerate(lines, 1):
            if name in (group for found in DEFINITION.finditer(line) for group in found.groups() if group):
                return name, number
        return name, text[: match.start()].count("\n") + 1
    for number, line in enumerate(lines, 1):
        if re.search(r"\bexport\s+default\b", line):
            return f"default@{relative}", number
    raise JsImportError(f"local default import target has no default export: {relative}")


def default_import_owners(
    root: Path, importer: str, lines: list[str]
) -> tuple[dict[str, str], tuple[tuple[str, str, int, list[str]], ...]]:
    mapping: dict[str, str] = {}
    owners = []
    for local, specifier in DEFAULT_IMPORT.findall("\n".join(lines)):
        if not specifier.startswith("."):
            continue
        path = module_path(root, importer, specifier)
        relative = path.relative_to(root.resolve()).as_posix()
        try:
            target_lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise JsImportError(f"unsafe local default import target: {relative}") from exc
        owner, line = default_owner(target_lines, relative)
        mapping[local] = owner
        owners.append((relative, owner, line, target_lines))
    return mapping, tuple(owners)

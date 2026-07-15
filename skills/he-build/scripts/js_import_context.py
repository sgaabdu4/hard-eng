#!/usr/bin/env python3
"""Resolve local JavaScript-family default imports to their owning module."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


JS_SUFFIXES = (".js", ".jsx", ".ts", ".tsx")
DEFAULT_IMPORT = re.compile(
    r"import\s+(?:type\s+)?([A-Za-z_$][\w$]*)\s+from\s+[\"']([^\"']+)[\"']"
)
DEFAULT_DECL = re.compile(
    r"\bexport\s+default\s+(?:async\s+)?(?:function|class)\s+([A-Za-z_$][\w$]*)\b"
)
DEFAULT_REF = re.compile(r"\bexport\s+default\s+([A-Za-z_$][\w$]*)\s*;?\s*$", re.MULTILINE)
NAMED_IMPORT = re.compile(
    r"import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+[\"']([^\"']+)[\"']",
    re.DOTALL,
)
NAMED_DECL = re.compile(
    r"\bexport\s+(?:declare\s+)?(?:(?:async\s+)?function|class|const|let|var|interface|type|enum)\s+"
    r"([A-Za-z_$][\w$]*)"
)
EXPORT_FROM = re.compile(
    r"\bexport\s+(?:type\s+)?\{([^}]+)\}\s+from\s+[\"']([^\"']+)[\"']",
    re.DOTALL,
)
EXPORT_LOCAL = re.compile(r"\bexport\s+(?:type\s+)?\{([^}]+)\}(?!\s+from)", re.DOTALL)
EXPORT_STAR = re.compile(r"\bexport\s+\*\s+from\s+[\"']([^\"']+)[\"']")
DEFINITION = re.compile(
    r"\b(?:class|function)\s+([A-Za-z_$][\w$]*)|"
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*="
)


class JsImportError(RuntimeError):
    pass


def dedupe_owners(owners):
    unique = {}
    for value in owners:
        relative, owner, line, _ = value
        unique[(relative, owner, line)] = value
    return tuple(unique.values())


def _base_file(root: Path, path: Path, base: str | None) -> bool:
    if base is None:
        return False
    try:
        relative = path.resolve(strict=False).relative_to(root.resolve()).as_posix()
    except (OSError, ValueError):
        return False
    result = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-z", base, "--", relative],
        capture_output=True, check=False,
    )
    record = result.stdout.split(b"\0", 1)[0]
    return result.returncode == 0 and record.startswith((b"100644 blob ", b"100755 blob "))


def module_path(root: Path, importer: str, specifier: str, base: str | None = None) -> Path:
    anchor = (root / importer).parent / specifier
    candidates = (
        [anchor]
        if anchor.suffix.lower() in JS_SUFFIXES
        else [Path(f"{anchor}{suffix}") for suffix in JS_SUFFIXES]
    ) + [anchor / f"index{suffix}" for suffix in JS_SUFFIXES]
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
            resolved.relative_to(root.resolve())
        except (OSError, ValueError):
            resolved = None
        if (resolved is not None and not candidate.is_symlink()
                and resolved.is_file() and resolved.suffix in JS_SUFFIXES):
            return resolved
        if candidate.suffix.lower() in JS_SUFFIXES and _base_file(root, candidate, base):
            return candidate.resolve(strict=False)
    raise JsImportError(f"unresolved local module import: {specifier} from {importer}")


def module_lines(root: Path, path: Path, base: str | None) -> list[str]:
    relative = path.resolve(strict=False).relative_to(root.resolve()).as_posix()
    try:
        if not path.is_symlink() and path.is_file():
            return path.read_text(encoding="utf-8").splitlines()
        if _base_file(root, path, base):
            result = subprocess.run(
                ["git", "-C", str(root), "show", f"{base}:{relative}"],
                capture_output=True, check=False,
            )
            if result.returncode == 0:
                return result.stdout.decode("utf-8").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise JsImportError(f"unsafe local import target: {relative}") from exc
    raise JsImportError(f"unsafe local import target: {relative}")


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
    root: Path, importer: str, lines: list[str], base: str | None = None,
) -> tuple[dict[str, str], tuple[tuple[str, str, int, list[str]], ...]]:
    mapping: dict[str, str] = {}
    owners = []
    for local, specifier in DEFAULT_IMPORT.findall("\n".join(lines)):
        if not specifier.startswith("."):
            continue
        path = module_path(root, importer, specifier, base)
        relative = path.relative_to(root.resolve()).as_posix()
        target_lines = module_lines(root, path, base)
        owner, line = default_owner(target_lines, relative)
        mapping[local] = owner
        owners.append((relative, owner, line, target_lines))
    return mapping, tuple(owners)


def import_parts(group: str) -> tuple[tuple[str, str], ...]:
    values = []
    for raw in group.split(","):
        value = re.sub(r"^type\s+", "", raw.strip())
        if not value:
            continue
        original, separator, alias = value.partition(" as ")
        if not re.fullmatch(r"[A-Za-z_$][\w$]*", original.strip()):
            continue
        local = alias.strip() if separator else original.strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", local):
            values.append((original.strip(), local))
    return tuple(values)


def named_owner(
    root: Path, path: Path, exported: str, seen: frozenset[tuple[Path, str]] = frozenset(),
    base: str | None = None,
) -> tuple[Path, str, int, list[str]]:
    key = (path, exported)
    if key in seen:
        raise JsImportError(f"cyclic local named export: {exported} from {path.name}")
    relative = path.relative_to(root.resolve()).as_posix()
    lines = module_lines(root, path, base)
    for number, line in enumerate(lines, 1):
        if exported in NAMED_DECL.findall(line):
            return path, exported, number, lines
    text = "\n".join(lines)
    for group in EXPORT_LOCAL.findall(text):
        for local, public in import_parts(group):
            if public != exported:
                continue
            for number, line in enumerate(lines, 1):
                if local in (name for match in DEFINITION.finditer(line) for name in match.groups() if name):
                    return path, local, number, lines
    for group, specifier in EXPORT_FROM.findall(text):
        for source, public in import_parts(group):
            if public == exported:
                target = module_path(root, relative, specifier, base)
                return named_owner(root, target, source, seen | {key}, base)
    for specifier in EXPORT_STAR.findall(text):
        target = module_path(root, relative, specifier, base)
        try:
            return named_owner(root, target, exported, seen | {key}, base)
        except JsImportError:
            continue
    raise JsImportError(f"local named import target has no export: {exported} from {relative}")


def named_import_owners(
    root: Path, importer: str, lines: list[str], required: set[str] | None = None,
    base: str | None = None,
) -> tuple[dict[str, str], tuple[tuple[str, str, int, list[str]], ...]]:
    mapping: dict[str, str] = {}
    owners = []
    for group, specifier in NAMED_IMPORT.findall("\n".join(lines)):
        if not specifier.startswith("."):
            continue
        parts = tuple(
            (exported, local) for exported, local in import_parts(group)
            if required is None or local in required
        )
        if not parts:
            continue
        path = module_path(root, importer, specifier, base)
        for exported, local in parts:
            owner_path, owner, line, target_lines = named_owner(root, path, exported, base=base)
            mapping[local] = owner
            relative = owner_path.relative_to(root.resolve()).as_posix()
            owners.append((relative, owner, line, target_lines))
    return mapping, dedupe_owners(owners)

#!/usr/bin/env python3
"""Build one immutable tracked-source index for related-context queries."""

from __future__ import annotations

import re
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

from related_context_budget import RelatedContextError


SOURCE_SUFFIXES = frozenset({
    ".c", ".cc", ".cpp", ".dart", ".go", ".java", ".js", ".jsx", ".kt",
    ".py", ".rs", ".swift", ".ts", ".tsx",
})
LANGUAGE_FAMILY = {
    ".c": "cpp", ".cc": "cpp", ".cpp": "cpp",
    ".java": "jvm", ".kt": "jvm",
    ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
}
IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
LITERAL = re.compile(
    r"[\"']((?:/[^\"'\r\n]*)|(?:[A-Za-z_$][A-Za-z0-9_.$:-]{1,63}))[\"']"
)


@dataclass(frozen=True)
class SourceEntry:
    relative: str
    family: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryIndex:
    entries: tuple[SourceEntry, ...]
    symbols: dict[tuple[str, str], tuple[tuple[int, int], ...]]
    literals: dict[tuple[str, str], tuple[tuple[int, int], ...]]


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise RelatedContextError(f"git {' '.join(args[:2])} failed during related-context indexing")
    return result.stdout


def language_family(relative: str) -> str:
    suffix = Path(relative).suffix.lower()
    return LANGUAGE_FAMILY.get(suffix, suffix)


def repository_source_index(root: Path) -> RepositoryIndex:
    entries: list[SourceEntry] = []
    symbols: dict[tuple[str, str], list[tuple[int, int]]] = {}
    literals: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for entry in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not entry:
            continue
        try:
            metadata, raw_relative = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            relative = raw_relative.decode("utf-8", "surrogateescape")
        except (UnicodeError, ValueError) as exc:
            raise RelatedContextError("cannot parse tracked source index") from exc
        if Path(relative).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if stage != "0":
            raise RelatedContextError(f"unmerged tracked source blocks related context: {relative}")
        if mode == "120000":
            raise RelatedContextError(f"tracked source symlink blocks related context: {relative}")
        if mode not in {"100644", "100755"}:
            raise RelatedContextError(f"unsupported tracked source mode blocks related context: {relative}")
        path = root / relative
        try:
            worktree_mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RelatedContextError(f"cannot inspect tracked source: {relative}") from exc
        if stat.S_ISLNK(worktree_mode):
            raise RelatedContextError(f"worktree source symlink blocks related context: {relative}")
        if not stat.S_ISREG(worktree_mode):
            raise RelatedContextError(f"non-file tracked source blocks related context: {relative}")
        try:
            lines = tuple(git(root, "cat-file", "blob", object_id).decode("utf-8").splitlines())
        except UnicodeError as exc:
            raise RelatedContextError(f"tracked source is not UTF-8: {relative}") from exc
        family = language_family(relative)
        entry_index = len(entries)
        entries.append(SourceEntry(relative, family, lines))
        for line_number, source_line in enumerate(lines, 1):
            for identifier in set(IDENTIFIER.findall(source_line)):
                symbols.setdefault((family, identifier), []).append((entry_index, line_number))
            for literal in set(LITERAL.findall(source_line)):
                literals.setdefault((family, literal), []).append((entry_index, line_number))
    return RepositoryIndex(
        tuple(entries), {token: tuple(hits) for token, hits in symbols.items()},
        {token: tuple(hits) for token, hits in literals.items()},
    )

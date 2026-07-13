#!/usr/bin/env python3
"""Bounded current and related context for final audit."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path


MAX_SECTIONS = 24
MAX_BYTES = 48 * 1024
MAX_OWNER_SECTIONS = 6
CONTEXT_RADIUS = 5
MAX_OWNER_SCAN_LINES = 200
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".dart", ".go", ".java", ".js", ".jsx", ".kt", ".py", ".rs", ".swift", ".ts", ".tsx"}
DEFINITION = re.compile(
    r"\b(?:class|def|fn|function)\s+([A-Za-z_$][A-Za-z0-9_$]*)|"
    r"\b(?:const|final|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=.*(?:=>|function\b)"
)
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class RelatedContextError(RuntimeError):
    pass


def command(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode in {0, 1} else ""


def numbered(lines: list[str], start: int, end: int) -> str:
    return "\n".join(f"{index + 1}: {lines[index]}" for index in range(start, end))


def changed_ranges(root: Path, relative: str, base: str) -> tuple[tuple[int, int], ...]:
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
        capture_output=True,
        check=False,
    ).returncode == 0
    if not tracked:
        try:
            line_count = len((root / relative).read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            return ()
        return ((1, max(1, line_count)),)
    ranges = set()
    for revisions in ((base,), ("--cached",), ()):
        for line in command(root, "diff", "--unified=0", *revisions, "--", relative).splitlines():
            match = HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                ranges.add((start, max(start, start + count - 1)))
    return tuple(sorted(ranges))


def context_slice(root: Path, relative: str, line: int) -> str:
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        if path.is_symlink() or not resolved.is_file():
            raise OSError
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise RelatedContextError(f"unsafe related-context path: {relative}") from exc
    start = max(0, line - 1 - CONTEXT_RADIUS)
    end = min(len(lines), line + CONTEXT_RADIUS)
    return numbered(lines, start, end)


def definition_names(line: str) -> tuple[str, ...]:
    return tuple(next(group for group in match.groups() if group) for match in DEFINITION.finditer(line))


def current_plan_intent(text: str) -> str:
    projected: list[str] = []
    excluded = False
    stage_review = False
    for line in text.splitlines():
        if line.strip() in {
            "## State", "## Active items", "## Repository", "## Research", "## UX", "## Technical",
            "## Consistency", "## Approval", "## Build Progress",
        }:
            excluded = True
            continue
        if excluded and line.startswith("## "):
            excluded = False
        if excluded:
            continue
        if line.startswith("### Stage Review:"):
            stage_review = True
            continue
        if stage_review and line.startswith("## "):
            stage_review = False
        if stage_review:
            continue
        projected.append(line)
    return "\n".join(projected) + ("\n" if text.endswith("\n") else "")


def enclosing_owner(lines: list[str], first: int) -> tuple[str, int] | None:
    start = min(len(lines) - 1, max(0, first - 1))
    stop = max(-1, start - MAX_OWNER_SCAN_LINES)
    for index in range(start, stop, -1):
        names = definition_names(lines[index])
        if names:
            return names[0], index + 1
    return None


def owner_slice(lines: list[str], owner_line: int, first: int, last: int) -> str:
    windows = [
        (owner_line - 1, min(len(lines), owner_line + CONTEXT_RADIUS)),
        (max(owner_line, first - 1 - CONTEXT_RADIUS), min(len(lines), last + CONTEXT_RADIUS)),
    ]
    if windows[1][0] <= windows[0][1]:
        return numbered(lines, windows[0][0], max(windows[0][1], windows[1][1]))
    return numbered(lines, *windows[0]) + "\n...\n" + numbered(lines, *windows[1])


def related_context(root: Path, changed: tuple[str, ...], base: str = "HEAD") -> tuple[tuple[str, str, str], ...]:
    owner_sections: list[tuple[str, str, str]] = []
    identifiers: set[str] = set()
    owners: set[tuple[str, int]] = set()
    for relative in changed:
        path = root / relative
        if path.suffix.lower() not in SOURCE_SUFFIXES or path.is_symlink():
            continue
        if path.is_file():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            ranges = changed_ranges(root, relative, base)
            for revisions in ((f"{base}...HEAD",), ("--cached",), ()):
                diff = command(root, "diff", "--unified=0", *revisions, "--", relative)
                identifiers.update(
                    name for line in diff.splitlines() if line[:1] in {"+", "-"} and not line.startswith(("+++", "---"))
                    for name in definition_names(line[1:])
                )
        else:
            lines = command(root, "show", f"{base}:{relative}").splitlines()
            ranges = ((1, max(1, len(lines))),) if lines else ()
        for first, last in ranges:
            found = False
            for line in lines[max(0, first - 1) : min(len(lines), last)]:
                names = definition_names(line)
                identifiers.update(names)
                found = found or bool(names)
            if not found and (owner := enclosing_owner(lines, first)):
                owner_name, owner_line = owner
                identifiers.add(owner_name)
                key = (relative, owner_line)
                owner_changed = any(start <= owner_line <= end for start, end in ranges)
                if key not in owners and not owner_changed:
                    owners.add(key)
                    owner_sections.append((
                        relative,
                        f"## Nearby owner: {relative}:{owner_line} ({owner_name})",
                        owner_slice(lines, owner_line, first, last),
                    ))

    sections: list[tuple[str, str, str]] = []
    owner_paths: set[str] = set()
    for entry in owner_sections:
        if entry[0] not in owner_paths:
            sections.append(entry)
            owner_paths.add(entry[0])
    sections.extend(entry for entry in owner_sections if entry not in sections)
    sections = sections[:MAX_OWNER_SECTIONS]
    seen: set[tuple[str, int]] = set()
    for identifier in sorted(identifiers)[:8]:
        matches = command(root, "grep", "-n", "-w", "-e", identifier, "--").splitlines()
        candidates: list[tuple[str, int]] = []
        for match in matches:
            relative, separator, tail = match.partition(":")
            line_text, separator, _ = tail.partition(":")
            if not separator or not line_text.isdigit() or relative in changed:
                continue
            candidates.append((relative, int(line_text)))
        for relative, line in candidates[:12]:
            key = (relative, line)
            if key in seen:
                continue
            seen.add(key)
            content = context_slice(root, relative, line)
            if not content:
                continue
            kind = "test" if re.search(r"(?:^|/)(?:test|tests|spec)(?:/|_)|[._](?:test|spec)\.", relative) else "caller"
            sections.append((relative, f"## Related {kind}: {relative}:{line} ({identifier})", content))
            if len(sections) >= MAX_SECTIONS:
                break
        if len(sections) >= MAX_SECTIONS:
            break

    prioritized: list[tuple[str, str, str]] = []
    remaining = list(sections)
    for marker in ("## Nearby owner:", "## Related caller:", "## Related test:"):
        if index := next((i + 1 for i, entry in enumerate(remaining) if entry[1].startswith(marker)), 0):
            prioritized.append(remaining.pop(index - 1))
    prioritized.extend(remaining)
    bounded: list[tuple[str, str, str]] = []
    size = 0
    for entry in prioritized[:MAX_SECTIONS]:
        entry_size = sum(len(value.encode("utf-8")) for value in entry)
        if size + entry_size > MAX_BYTES:
            break
        bounded.append(entry)
        size += entry_size
    return tuple(bounded)

#!/usr/bin/env python3
"""Deterministic section and byte budgets for related audit context."""

from __future__ import annotations


PRIORITY_MARKERS = (
    "## Related coverage",
    "## Nearby owner:",
    "## Related owner:",
    "## Related caller:",
    "## Related test:",
)


class RelatedContextError(RuntimeError):
    pass


def rendered_bytes(sections: list[tuple[str, str, str]]) -> int:
    return sum(len(value.encode("utf-8")) for entry in sections for value in entry)


def collapse_required(
    sections: list[tuple[str, str, str]], full_files: set[str], max_sections: int, max_bytes: int
) -> bool:
    return bool(full_files) or len(sections) > max_sections or rendered_bytes(sections) > max_bytes


def bounded_sections(
    sections: list[tuple[str, str, str]], max_sections: int, max_bytes: int
) -> tuple[tuple[str, str, str], ...]:
    prioritized: list[tuple[str, str, str]] = []
    remaining = list(sections)
    for marker in PRIORITY_MARKERS:
        index = next((i + 1 for i, entry in enumerate(remaining) if entry[1].startswith(marker)), 0)
        if index:
            prioritized.append(remaining.pop(index - 1))
    prioritized.extend(remaining)
    if len(prioritized) > max_sections:
        raise RelatedContextError(
            f"required related context exceeds {max_sections} sections: {prioritized[max_sections][1]}"
        )
    size = 0
    for entry in prioritized:
        entry_size = rendered_bytes([entry])
        if size + entry_size > max_bytes:
            raise RelatedContextError(
                f"required related context exceeds {max_bytes} bytes: {entry[1]}"
            )
        size += entry_size
    return tuple(prioritized)

#!/usr/bin/env python3
"""Validate mandatory root PRODUCT.md and DESIGN.md repository context."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bounded_run import run_captured
from git_env import git_env

# product.md canonical headings + Hard Eng proof additions.
# Alias-matched and order-free; product.md defines no ordering.
PRODUCT_REQUIRED: dict[str, tuple[str, ...]] = {
    "Users": ("users", "audience"),
    "Purpose": ("product purpose", "purpose", "value"),
    "Boundaries": ("boundaries", "non-goals"),
    "Success": ("success", "success metrics"),
    "Evidence": ("evidence",),
    "Unknowns": ("unknowns", "open questions"),
}
DESIGN_SECTIONS = (
    "Overview",
    "Colors",
    "Typography",
    "Layout",
    "Elevation & Depth",
    "Shapes",
    "Components",
    "Do's and Don'ts",
)
HEADING = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
H1 = re.compile(r"^# \S.*$", re.MULTILINE)
ISLAND = re.compile(r"^```json[ \t]+product\.md#[\w-]+[ \t]*$\n(.*?)^```", re.MULTILINE | re.DOTALL)
FENCE = re.compile(r"^```.*?^```", re.MULTILINE | re.DOTALL)


class ContextDocsError(ValueError):
    pass


def emit(key: str, value: str) -> None:
    print(f"{key}={value.replace(chr(10), ' ').replace(chr(13), ' ')}")


def git_root(repo: str) -> Path:
    result = run_captured(
        ["git", "-C", str(Path(repo).expanduser()), "rev-parse", "--show-toplevel"], 20, env=git_env()
    )
    if result.returncode:
        raise OSError("cannot resolve repository root")
    return Path(result.stdout.decode("utf-8", "strict").strip()).resolve()


def nested_context_docs(root: Path) -> tuple[str, ...]:
    result = run_captured(
        ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"], 20, env=git_env()
    )
    if result.returncode:
        raise OSError("cannot list repository context documents")
    return tuple(
        path
        for raw in result.stdout.split(b"\0")
        if raw
        for path in (os.fsdecode(raw),)
        if "/" in path and Path(path).name in {"PRODUCT.md", "DESIGN.md"}
    )


def prose(text: str) -> str:
    """Drop fenced blocks so example headings and shell comments are not read as structure."""
    return FENCE.sub("", text)


def headings(text: str) -> tuple[str, ...]:
    values = tuple(HEADING.findall(text))
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ContextDocsError("duplicate sections: " + ",".join(duplicates))
    return values


def validate_islands(text: str) -> None:
    for index, body in enumerate(ISLAND.findall(text), start=1):
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            raise ContextDocsError(f"machine island {index} is not valid JSON: {exc.msg}") from exc


def validate_product(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    body = prose(text)
    if len(H1.findall(body)) != 1:
        raise ContextDocsError("PRODUCT.md requires exactly one H1 product name")
    lowered = {value.lower() for value in headings(body)}
    missing = [
        canonical for canonical, aliases in PRODUCT_REQUIRED.items() if not any(alias in lowered for alias in aliases)
    ]
    if missing:
        raise ContextDocsError("PRODUCT.md missing sections: " + ",".join(missing))
    validate_islands(text)


def frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        raise ContextDocsError("DESIGN.md missing YAML frontmatter")
    try:
        end = lines.index("---", 1)
    except ValueError as exc:
        raise ContextDocsError("DESIGN.md frontmatter is not closed") from exc
    values: dict[str, str] = {}
    for line in lines[1:end]:
        match = re.fullmatch(r"([a-z][a-zA-Z0-9_-]*):\s*(.+)", line)
        if match:
            values[match.group(1)] = match.group(2).strip().strip("\"'")
    return values


def validate_design(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    metadata = frontmatter(text)
    if metadata.get("version") != "alpha" or not metadata.get("name"):
        raise ContextDocsError("DESIGN.md requires version=alpha + name")
    actual = headings(prose(text))
    if "Overview" not in actual:
        raise ContextDocsError("DESIGN.md missing Overview")
    known = tuple(section for section in actual if section in DESIGN_SECTIONS)
    if tuple(DESIGN_SECTIONS.index(section) for section in known) != tuple(
        sorted(DESIGN_SECTIONS.index(section) for section in known)
    ):
        raise ContextDocsError("DESIGN.md sections out of order")
    has_tokens = re.search(r"^(colors|typography|spacing|rounded|components):\s*$", text, re.MULTILINE)
    if not has_tokens and not re.search(r"^- Visual surface = none$", text, re.MULTILINE):
        raise ContextDocsError("DESIGN.md requires tokens or Visual surface = none")


def inspect(repo: str) -> int:
    try:
        root = git_root(repo)
        nested = nested_context_docs(root)
    except (OSError, UnicodeError):
        emit("result", "invalid")
        emit("error", "repository is not a readable Git worktree")
        return 4

    errors: list[str] = []
    if nested:
        errors.append("nested context owners forbidden: " + ",".join(nested))
    for name, validator in (("PRODUCT.md", validate_product), ("DESIGN.md", validate_design)):
        path = root / name
        if not path.is_file():
            errors.append(f"missing {name}")
            continue
        try:
            validator(path)
        except (ContextDocsError, OSError, UnicodeError) as exc:
            errors.append(str(exc))

    if errors:
        emit("result", "invalid")
        emit("repository_root", str(root))
        for index, error in enumerate(errors, start=1):
            emit(f"error_{index}", error)
        return 4
    emit("result", "valid")
    emit("repository_root", str(root))
    emit("product", str(root / "PRODUCT.md"))
    emit("design", str(root / "DESIGN.md"))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    return inspect(parser.parse_args().repo)


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate mandatory root PRODUCT.md and DESIGN.md repository context."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

PRODUCT_SECTIONS = (
    "Identity",
    "Problem",
    "Users",
    "Value",
    "Principles",
    "Core capabilities",
    "Boundaries",
    "Success",
    "Constraints",
    "Evidence",
    "Unknowns",
)
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


class ContextDocsError(ValueError):
    pass


def emit(key: str, value: str) -> None:
    print(f"{key}={value.replace(chr(10), ' ').replace(chr(13), ' ')}")


def git_root(repo: str) -> Path:
    result = subprocess.run(
        ["git", "-C", str(Path(repo).expanduser()), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def nested_context_docs(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(
        path
        for path in result.stdout.splitlines()
        if "/" in path and Path(path).name in {"PRODUCT.md", "DESIGN.md"}
    )


def headings(text: str) -> tuple[str, ...]:
    values = tuple(HEADING.findall(text))
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ContextDocsError("duplicate sections: " + ",".join(duplicates))
    return values


def require_order(actual: tuple[str, ...], required: tuple[str, ...], label: str) -> None:
    missing = [section for section in required if section not in actual]
    if missing:
        raise ContextDocsError(f"{label} missing sections: " + ",".join(missing))
    positions = tuple(actual.index(section) for section in required)
    if positions != tuple(sorted(positions)):
        raise ContextDocsError(f"{label} sections out of order")


def validate_product(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if not re.search(r"^# Product(?:\s|$)", text, re.MULTILINE):
        raise ContextDocsError("PRODUCT.md missing # Product title")
    require_order(headings(text), PRODUCT_SECTIONS, "PRODUCT.md")


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
    actual = headings(text)
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
    except (FileNotFoundError, subprocess.CalledProcessError):
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

"""Deterministic UX-reference provenance and renderability checks."""

from __future__ import annotations

import os
import re
from pathlib import Path
from urllib.parse import urlsplit

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


class UXReferenceError(ValueError):
    """Invalid UX reference or provenance."""


def reference_value(section: str) -> str:
    matches = re.findall(r"(?m)^- ux_reference = (.+)$", section)
    if len(matches) != 1:
        raise UXReferenceError(
            "Material decisions requires exactly one `ux_reference` row: accepted "
            "visual reference for new/changed user-visible surface, or n/a"
        )
    return matches[0].strip()


def source_value(section: str) -> str:
    matches = re.findall(r"(?m)^- ux_reference_sources = (.+)$", section)
    if len(matches) != 1:
        raise UXReferenceError(
            "Material decisions requires exactly one `ux_reference_sources` row"
        )
    return matches[0].strip()


def repo_artifact_path(repo: Path, value: str, field: str) -> Path:
    repo = repo.resolve()
    raw = Path(value)
    candidate = raw if raw.is_absolute() else repo / raw
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(repo)
    except ValueError as error:
        raise UXReferenceError(
            f"{field} must stay inside the repository: {value}"
        ) from error
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(repo)
    except ValueError as error:
        raise UXReferenceError(
            f"{field} must not escape through a symlink: {value}"
        ) from error
    if not resolved.is_file():
        raise UXReferenceError(f"{field} file does not exist: {value}")
    return resolved


def image_file_is_viewable(path: Path) -> bool:
    suffix = path.suffix.lower()
    size = path.stat().st_size
    if size == 0 or suffix not in IMAGE_SUFFIXES:
        return False
    with path.open("rb") as handle:
        head = handle.read(512)
        if suffix in {".jpg", ".jpeg"}:
            if size < 4:
                return False
            handle.seek(-2, os.SEEK_END)
            return head.startswith(b"\xff\xd8") and handle.read(2) == b"\xff\xd9"
    if suffix == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
    if suffix == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if suffix == ".webp":
        return (
            len(head) >= 12
            and head.startswith(b"RIFF")
            and head[8:12] == b"WEBP"
        )
    if suffix == ".svg":
        return re.search(rb"<svg(?:\s|>)", head, re.IGNORECASE) is not None
    return False


def validate(repo: Path, value: str, sources: str) -> Path | str | None:
    if value == "n/a":
        if sources != "n/a":
            raise UXReferenceError(
                "ux_reference = n/a requires ux_reference_sources = n/a"
            )
        return None

    source_values = sources.split(" + ")
    if (
        sources == "n/a"
        or len(source_values) < 2
        or source_values[0] != "DESIGN.md"
    ):
        raise UXReferenceError(
            "visual ux_reference requires ux_reference_sources = DESIGN.md + "
            "<existing production owner path>"
        )
    if any(Path(source).is_absolute() for source in source_values):
        raise UXReferenceError("ux_reference_sources paths must be repository-relative")
    source_paths = [
        repo_artifact_path(repo, source, "ux_reference_sources")
        for source in source_values
    ]
    if any(path.suffix.lower() in IMAGE_SUFFIXES for path in source_paths[1:]):
        raise UXReferenceError(
            "ux_reference_sources production owners must be code, token, theme, "
            "component, or layout files"
        )

    if re.match(r"(?i)https?://", value):
        suffix = Path(urlsplit(value).path).suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            raise UXReferenceError(
                "remote ux_reference must be a direct image URL ending in "
                f"{sorted(IMAGE_SUFFIXES)}: {value}"
            )
        return value

    target = repo_artifact_path(repo, value, "ux_reference")
    if not image_file_is_viewable(target):
        raise UXReferenceError(
            "ux_reference must contain a real viewable PNG, JPEG, WebP, GIF, "
            f"or SVG image: {value}"
        )
    if target in source_paths:
        raise UXReferenceError("ux_reference image cannot be its own production source")
    return target


def markdown(repo: Path, value: str, sources: str) -> str | None:
    target = validate(repo, value, sources)
    if target is None:
        return None
    if isinstance(target, str):
        return f"![UX reference]({target})"
    return f"![UX reference](<{target}>)"

"""Deterministic UX-reference provenance and renderability checks."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
MAX_SVG_BYTES = 5 * 1024 * 1024
ACTIVE_SVG_ELEMENTS = {
    "animate",
    "animatemotion",
    "animatetransform",
    "audio",
    "embed",
    "foreignobject",
    "iframe",
    "object",
    "script",
    "set",
    "style",
    "video",
}
EXTERNAL_SVG_VALUE = re.compile(r"(?:javascript:|vbscript:|file:|https?:|//|@import|expression\s*\()", re.IGNORECASE)
SVG_URL = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.IGNORECASE)


def svg_attribute_is_safe(value: str) -> bool:
    if EXTERNAL_SVG_VALUE.search(value):
        return False
    return all(match.group(2).strip().startswith("#") for match in SVG_URL.finditer(value))


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
        raise UXReferenceError("Material decisions requires exactly one `ux_reference_sources` row")
    return matches[0].strip()


def repo_artifact_path(repo: Path, value: str, field: str) -> Path:
    repo = repo.resolve()
    raw = Path(value)
    candidate = raw if raw.is_absolute() else repo / raw
    lexical = Path(os.path.abspath(candidate))
    try:
        lexical.relative_to(repo)
    except ValueError as error:
        raise UXReferenceError(f"{field} must stay inside the repository: {value}") from error
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(repo)
    except ValueError as error:
        raise UXReferenceError(f"{field} must not escape through a symlink: {value}") from error
    if not resolved.is_file():
        raise UXReferenceError(f"{field} file does not exist: {value}")
    return resolved


def local_reference_path(repo: Path, value: str) -> Path:
    repo = repo.resolve()
    raw = Path(value)
    if not raw.is_absolute():
        raise UXReferenceError(
            f"local ux_reference must be an absolute lifecycle-media path outside the repository: {value}"
        )
    lexical = Path(os.path.abspath(raw))
    try:
        lexical.relative_to(repo)
    except ValueError:
        pass
    else:
        raise UXReferenceError(f"ux_reference media must stay outside the repository: {value}")
    resolved = lexical.resolve(strict=False)
    try:
        resolved.relative_to(repo)
    except ValueError:
        pass
    else:
        raise UXReferenceError(f"ux_reference media must not resolve into the repository: {value}")
    if not resolved.is_file():
        raise UXReferenceError(f"ux_reference file does not exist: {value}")
    return resolved


def svg_file_is_safe(path: Path) -> bool:
    data = path.read_bytes()
    if not data or len(data) > MAX_SVG_BYTES:
        return False
    lowered = data.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered or b"<?xml-stylesheet" in lowered:
        return False
    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        return False
    if root.tag.rsplit("}", 1)[-1].lower() != "svg":
        return False
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1].lower() in ACTIVE_SVG_ELEMENTS:
            return False
        for raw_name, raw_value in element.attrib.items():
            name = raw_name.rsplit("}", 1)[-1].lower()
            value = raw_value.strip().lower()
            if name.startswith("on") or name == "base":
                return False
            if name == "href" and value and not value.startswith("#"):
                return False
            if not svg_attribute_is_safe(value):
                return False
    return True


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
        return len(head) >= 12 and head.startswith(b"RIFF") and head[8:12] == b"WEBP"
    if suffix == ".svg":
        return svg_file_is_safe(path)
    return False


def validate(repo: Path, value: str, sources: str) -> Path | None:
    if value == "n/a":
        if sources != "n/a":
            raise UXReferenceError("ux_reference = n/a requires ux_reference_sources = n/a")
        return None

    source_values = sources.split(" + ")
    if sources == "n/a" or len(source_values) < 2 or source_values[0] != "DESIGN.md":
        raise UXReferenceError(
            "visual ux_reference requires ux_reference_sources = DESIGN.md + <existing production owner path>"
        )
    if any(Path(source).is_absolute() for source in source_values):
        raise UXReferenceError("ux_reference_sources paths must be repository-relative")
    source_paths = [repo_artifact_path(repo, source, "ux_reference_sources") for source in source_values]
    if any(path.suffix.lower() in IMAGE_SUFFIXES for path in source_paths[1:]):
        raise UXReferenceError(
            "ux_reference_sources production owners must be code, token, theme, component, or layout files"
        )

    if re.match(r"(?i)https?://", value):
        raise UXReferenceError(
            "remote ux_reference URLs are mutable; save the approved image bytes "
            "as a local lifecycle-media file and use that absolute path"
        )

    target = local_reference_path(repo, value)
    if not image_file_is_viewable(target):
        raise UXReferenceError(f"ux_reference must contain a real viewable PNG, JPEG, WebP, GIF, or SVG image: {value}")
    if target in source_paths:
        raise UXReferenceError("ux_reference image cannot be its own production source")
    return target


def markdown(repo: Path, value: str, sources: str) -> str | None:
    target = validate(repo, value, sources)
    if target is None:
        return None
    return f"![UX reference](<{target}>)"

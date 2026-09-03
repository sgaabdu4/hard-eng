"""Deterministic UX-reference provenance and renderability checks."""

from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

E2E_SCRIPTS = Path(__file__).resolve().parents[2] / "e2e/scripts"
if str(E2E_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(E2E_SCRIPTS))

from plan_sections import empty_value
from visual_evidence import evaluate_receipt, sha256

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
REFERENCE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MAX_SVG_BYTES = 5 * 1024 * 1024
MIN_REFERENCE_WIDTH = 320
MIN_REFERENCE_HEIGHT = 200
UX_REFERENCE_PURPOSES = {"existing-ui-prototype", "existing-ui-static-preview", "new-ui-concept"}
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


def visual_receipt_path(target: Path) -> Path:
    return Path(f"{target}.visual-review.json")


def validated_delivery_paths(repo: Path, target: Path, source_values: list[str]) -> list[Path]:
    receipt_path = visual_receipt_path(target)
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise UXReferenceError(
            "ux_reference requires a reviewed sidecar at "
            f"{receipt_path}; create it with the canonical e2e visual-review receipt"
        )
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise UXReferenceError(f"ux_reference visual-review receipt is unreadable: {receipt_path}") from error
    if not isinstance(receipt, dict):
        raise UXReferenceError("ux_reference visual-review receipt must be a JSON object")
    evaluated = evaluate_receipt(receipt, repo)
    if evaluated["status"] != "PASS":
        detail = "; ".join(evaluated["failures"][:3]) or "receipt did not reach PASS"
        raise UXReferenceError(f"ux_reference visual-review receipt failed: {detail}")

    evidence = receipt.get("evidence")
    visual = evidence.get("visual") if isinstance(evidence, dict) else None
    if not isinstance(visual, dict) or visual.get("purpose") not in UX_REFERENCE_PURPOSES:
        raise UXReferenceError(
            "ux_reference receipt purpose must be existing-ui-prototype, existing-ui-static-preview, or new-ui-concept"
        )
    prototype = receipt.get("prototype")
    bindings = prototype.get("production_sources") if isinstance(prototype, dict) else None
    if not isinstance(bindings, list) or len(bindings) != len(source_values):
        raise UXReferenceError("ux_reference receipt production_sources must exactly match ux_reference_sources")
    bound_names: list[str] = []
    for index, (binding, expected_name) in enumerate(zip(bindings, source_values, strict=True)):
        if not isinstance(binding, dict) or binding.get("path") != expected_name:
            raise UXReferenceError("ux_reference receipt production_sources must exactly match ux_reference_sources")
        expected_path = repo_artifact_path(repo, expected_name, "ux_reference_sources")
        if binding.get("sha256") != sha256(expected_path):
            raise UXReferenceError(f"ux_reference receipt production source sha256 mismatch: {expected_name}")
        bound_names.append(expected_name)
    if bound_names != source_values:
        raise UXReferenceError("ux_reference receipt production_sources order must match ux_reference_sources")

    delivery = visual.get("delivery_artifact_sha256s")
    artifacts = visual.get("artifacts")
    if not isinstance(delivery, list) or not delivery or not isinstance(artifacts, list):
        raise UXReferenceError("ux_reference receipt requires reviewed delivery screenshots")
    target_digest = sha256(target)
    if target_digest not in delivery:
        raise UXReferenceError("ux_reference image digest is not in the receipt delivery list")
    paths: list[Path] = []
    for digest in delivery:
        matches = [item for item in artifacts if isinstance(item, dict) and item.get("sha256") == digest]
        if len(matches) != 1:
            raise UXReferenceError("each ux_reference delivery digest must bind exactly one artifact")
        artifact = matches[0]
        if artifact.get("kind") != "screenshot":
            raise UXReferenceError("ux_reference delivery artifacts must be screenshots")
        path = local_reference_path(repo, str(artifact.get("path", "")))
        if sha256(path) != digest:
            raise UXReferenceError(f"ux_reference delivery sha256 mismatch: {path}")
        dimensions = artifact.get("dimensions")
        width = dimensions.get("width") if isinstance(dimensions, dict) else None
        height = dimensions.get("height") if isinstance(dimensions, dict) else None
        if (
            not isinstance(width, (int, float))
            or isinstance(width, bool)
            or not isinstance(height, (int, float))
            or isinstance(height, bool)
            or width < MIN_REFERENCE_WIDTH
            or height < MIN_REFERENCE_HEIGHT
        ):
            raise UXReferenceError(
                f"ux_reference screenshots must be at least {MIN_REFERENCE_WIDTH}x{MIN_REFERENCE_HEIGHT}"
            )
        paths.append(path)
    if target not in paths:
        raise UXReferenceError("ux_reference path must be one of the receipt delivery screenshots")
    return [target, *(path for path in paths if path != target)]


def validate(repo: Path, value: str, sources: str) -> list[Path] | None:
    if empty_value(value) is not None:
        if empty_value(sources) is None:
            raise UXReferenceError("ux_reference = n/a requires ux_reference_sources = n/a")
        return None

    source_values = sources.split(" + ")
    if empty_value(sources) is not None or len(source_values) < 2 or source_values[0] != "DESIGN.md":
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
    if target.suffix.lower() not in REFERENCE_SUFFIXES:
        raise UXReferenceError("ux_reference must be a static PNG, JPEG, or WebP screenshot")
    if not image_file_is_viewable(target):
        raise UXReferenceError(f"ux_reference must contain a real viewable PNG, JPEG, or WebP screenshot: {value}")
    if target in source_paths:
        raise UXReferenceError("ux_reference image cannot be its own production source")
    return validated_delivery_paths(repo.resolve(), target, source_values)


def markdown(repo: Path, value: str, sources: str) -> str | None:
    targets = validate(repo, value, sources)
    if targets is None:
        return None
    if len(targets) == 1:
        return f"![UX reference](<{targets[0]}>)"
    return "\n\n".join(f"![UX reference {index}](<{target}>)" for index, target in enumerate(targets, 1))

"""Read-only packet-budget admission for the Hard Eng final-audit owner."""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any, Callable

ADMISSION_MAX_RELATED_SECTIONS = 96
ADMISSION_MAX_RELATED_BYTES = 112 * 1024
ADMISSION_MAX_PACKET_BYTES = 700 * 1024
DIAGNOSTIC_MAX_RELATED_SECTIONS = 4096
DIAGNOSTIC_MAX_RELATED_BYTES = 8 * 1024 * 1024
DIAGNOSTIC_MAX_PACKET_BYTES = 8 * 1024 * 1024
_SLICE = re.compile(r"(?m)^### (S-[1-9][0-9]*)\b[^\n]*$")
_PLANNED_PATHS = re.compile(r"(?m)^- planned_paths = (.+)$")
_GLOB_MARKERS = frozenset("*?[]{}")


def safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._/@:() \-]", "?", value.replace("\n", " "))
    return normalized[:200] or "unknown"


def bounded_units(units) -> list[dict[str, int | str]]:
    measured = ((safe_label(label), size) for label, size in units)
    return [
        {"label": label, "bytes": size}
        for label, size in sorted(measured, key=lambda item: (-item[1], item[0]))[:10]
    ]


def section_overflow_owner(units) -> str:
    if len(units) <= ADMISSION_MAX_RELATED_SECTIONS:
        return "unknown"
    return safe_label(units[ADMISSION_MAX_RELATED_SECTIONS][0])


def byte_overflow_owner(units) -> str:
    total = 0
    for label, size in units:
        total += size
        if total > ADMISSION_MAX_RELATED_BYTES:
            return safe_label(label)
    return "unknown"


def first_crossing_owner(units, limit: int) -> str:
    total = 0
    for label, size in units:
        total += size
        if total > limit:
            return safe_label(label)
    return "unknown"


def _validate_manifest_path(raw: str, *, root: Path, plan_relative: str,
                            sensitive: Callable[[str], bool]) -> str:
    value = raw.strip()
    path = PurePosixPath(value)
    if (not value or "\\" in value or path.is_absolute() or value != path.as_posix()
            or any(part in {"", ".", ".."} for part in path.parts)
            or any(marker in value for marker in _GLOB_MARKERS)
            or value == plan_relative or sensitive(value)):
        raise ValueError(f"unsafe planned path: {safe_label(value)}")
    target = root / value
    if target.is_symlink() or target.is_dir():
        raise ValueError(f"planned path must be a regular file target: {safe_label(value)}")
    return value


def parse_planned_manifests(plan: Path, root: Path, sensitive: Callable[[str], bool]) -> tuple[
    tuple[str, tuple[str, ...]], ...
]:
    text = plan.read_text(encoding="utf-8")
    matches = list(_SLICE.finditer(text))
    manifests = []
    seen = set()
    try:
        plan_relative = plan.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise ValueError("PLAN is outside repository") from exc
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        slice_id = match.group(1)
        if slice_id in seen:
            raise ValueError(f"duplicate slice manifest: {slice_id}")
        seen.add(slice_id)
        rows = _PLANNED_PATHS.findall(text[match.end():end])
        if len(rows) != 1:
            raise ValueError(f"{slice_id} requires exactly one planned_paths row")
        values = tuple(_validate_manifest_path(
            raw, root=root, plan_relative=plan_relative, sensitive=sensitive,
        ) for raw in rows[0].split(","))
        if not values or len(set(values)) != len(values):
            raise ValueError(f"{slice_id} planned_paths must be nonempty and unique")
        manifests.append((slice_id, values))
    if not manifests:
        raise ValueError("PLAN requires at least one planned slice")
    return tuple(manifests)


def parse_planned_paths(plan: Path, unit_id: str, root: Path,
                        sensitive: Callable[[str], bool]) -> tuple[str, ...]:
    manifests = dict(parse_planned_manifests(plan, root, sensitive))
    if unit_id not in manifests:
        raise ValueError(f"unknown planned slice: {safe_label(unit_id)}")
    return manifests[unit_id]


def evaluate_estimate(*, base_snapshot_id: str, base_sha: str, unit_id: str,
                      planned_paths: tuple[str, ...], unresolved_paths: tuple[str, ...],
                      related_units, packet_units,
                      related_bytes_override: int | None = None) -> dict[str, Any]:
    related_sections = len(related_units)
    related_bytes = (sum(size for _, size in related_units)
                     if related_bytes_override is None else related_bytes_override)
    packet_bytes = sum(size for _, size in packet_units)
    error = None
    if related_sections > ADMISSION_MAX_RELATED_SECTIONS:
        error = {"code": "RELATED_CONTEXT_SECTIONS", "actual": related_sections,
                 "limit": ADMISSION_MAX_RELATED_SECTIONS,
                 "owner": section_overflow_owner(related_units)}
    elif related_bytes > ADMISSION_MAX_RELATED_BYTES:
        error = {"code": "RELATED_CONTEXT_BYTES", "actual": related_bytes,
                 "limit": ADMISSION_MAX_RELATED_BYTES,
                 "owner": first_crossing_owner(related_units, ADMISSION_MAX_RELATED_BYTES)}
    elif packet_bytes > ADMISSION_MAX_PACKET_BYTES:
        error = {"code": "PACKET_BYTES", "actual": packet_bytes,
                 "limit": ADMISSION_MAX_PACKET_BYTES,
                 "owner": first_crossing_owner(packet_units, ADMISSION_MAX_PACKET_BYTES)}
    return {
        "mode": "estimate", "result": "fail" if error else "pass",
        "baseSnapshotId": base_snapshot_id, "baseSha": base_sha, "unitId": unit_id,
        "plannedPathCount": len(planned_paths),
        "unresolvedPlannedPaths": list(unresolved_paths),
        "relatedContext": {"sections": related_sections, "bytes": related_bytes,
                           "limitSections": ADMISSION_MAX_RELATED_SECTIONS,
                           "limitBytes": ADMISSION_MAX_RELATED_BYTES},
        "packet": {"bytes": packet_bytes, "limitBytes": ADMISSION_MAX_PACKET_BYTES},
        "largestUnits": bounded_units((*related_units, *packet_units)), "error": error,
    }


def require_diagnostic_packet_limit(packet_bytes: int, error_type) -> None:
    if packet_bytes > DIAGNOSTIC_MAX_PACKET_BYTES:
        raise error_type("diagnostic packet exceeds fixed safety ceiling")


def evaluate_admission(
    *,
    snapshot_id: str,
    base_sha: str,
    changed_path_count: int,
    related_sections: int,
    related_bytes: int,
    packet_bytes: int,
    largest_units,
    related_units=(),
    packet_units=(),
) -> dict[str, Any]:
    error = None
    if related_sections > ADMISSION_MAX_RELATED_SECTIONS:
        error = {
            "code": "RELATED_CONTEXT_SECTIONS",
            "actual": related_sections,
            "limit": ADMISSION_MAX_RELATED_SECTIONS,
            "owner": section_overflow_owner(related_units),
        }
    elif related_bytes > ADMISSION_MAX_RELATED_BYTES:
        error = {
            "code": "RELATED_CONTEXT_BYTES",
            "actual": related_bytes,
            "limit": ADMISSION_MAX_RELATED_BYTES,
            "owner": byte_overflow_owner(related_units),
        }
    elif packet_bytes > ADMISSION_MAX_PACKET_BYTES:
        error = {
            "code": "PACKET_BYTES",
            "actual": packet_bytes,
            "limit": ADMISSION_MAX_PACKET_BYTES,
            "owner": first_crossing_owner(packet_units, ADMISSION_MAX_PACKET_BYTES),
        }
    return {
        "result": "fail" if error else "pass",
        "snapshotId": snapshot_id,
        "baseSha": base_sha,
        "changedPathCount": changed_path_count,
        "relatedContext": {
            "sections": related_sections,
            "bytes": related_bytes,
            "limitSections": ADMISSION_MAX_RELATED_SECTIONS,
            "limitBytes": ADMISSION_MAX_RELATED_BYTES,
        },
        "packet": {"bytes": packet_bytes, "limitBytes": ADMISSION_MAX_PACKET_BYTES},
        "largestUnits": bounded_units(largest_units),
        "error": error,
    }


def error_code(error: Exception) -> str:
    message = str(error).lower()
    if ("accumulated" in message or "completed-slice" in message
            or "completed slices" in message or "preserved wip" in message):
        return "INVALID_ACCUMULATED_STATE"
    if "manifest" in message or "planned path" in message or "planned slice" in message:
        return "INVALID_MANIFEST"
    if "snapshot changed" in message or "stale" in message:
        return "STALE_SNAPSHOT"
    if any(
        marker in message
        for marker in ("secret", "credential", "sensitive", "symlink", "encoded text", "malformed")
    ):
        return "UNSAFE_CONTENT"
    if "candidate patch" in message or "git apply" in message or "delivery checkout" in message:
        return "INVALID_PATCH"
    if "plan" in message or "base_sha" in message or "ancestor" in message:
        return "INVALID_PLAN"
    return "PACKET_BUILD"


def error_detail(error: Exception | str) -> dict[str, str]:
    message = str(error)
    code = message if re.fullmatch(r"[A-Z][A-Z0-9_]*", message) else error_code(error)
    detail = {"code": code}
    if code == "INVALID_ACCUMULATED_STATE":
        patterns = (
            (r"unapproved preserved WIP path: (.+)$", "UNAPPROVED_PRESERVED_PATH"),
            (r"incomplete preserved WIP; missing path: (.+)$", "INCOMPLETE_PRESERVED_WIP"),
            (r"preserved WIP completed path drift: (.+)$", "COMPLETED_PATH_DRIFT"),
        )
        for pattern, reason in patterns:
            if match := re.search(pattern, message):
                detail.update(reason=reason, path=safe_label(match.group(1).strip()))
                break
        if "candidate patch does not match preserved WIP bytes" in message:
            detail["reason"] = "PRESERVED_BYTES_MISMATCH"
        return detail
    if code == "PACKET_BUILD":
        unresolved = re.search(
            r"unresolved required local import: ([A-Za-z_$][A-Za-z0-9_$]*) from (.+)$",
            message,
        )
        if unresolved:
            detail.update(
                reason="UNRESOLVED_LOCAL_IMPORT",
                symbol=safe_label(unresolved.group(1)),
                path=safe_label(unresolved.group(2).strip()),
            )
            return detail
        module = re.search(
            r"unresolved local (?:default|module) import: (.+?) from (.+)$", message,
        )
        if module:
            detail.update(
                reason="UNRESOLVED_LOCAL_MODULE",
                specifier=safe_label(module.group(1).strip()),
                path=safe_label(module.group(2).strip()),
            )
        return detail
    if code == "INVALID_PLAN":
        if missing := re.search(r"missing keys: ([a-z0-9_,]+)", message, re.IGNORECASE):
            fields = safe_label(missing.group(1).lower())
            detail.update(reason="MISSING_KEYS", fields=fields)
            if fields == "approved_plan_digest":
                detail["action"] = "migrate-state"
        elif version := re.search(
            r"unsupported state_version: ([^; ]+); expected: ([^; ]+)", message,
            re.IGNORECASE,
        ):
            detail.update(
                reason="UNSUPPORTED_STATE_VERSION",
                actual=safe_label(version.group(1)),
                expected=safe_label(version.group(2)),
            )
            if version.group(1) == "3" and version.group(2) == "4":
                detail["action"] = "migrate-state"
        return detail
    if code != "UNSAFE_CONTENT":
        return detail
    match = re.match(
        r"(?P<marker>[a-z0-9-]+)(?: (?:content|raw bytes|path|untracked path|historical path))? "
        r"blocks audit: (?P<path>.+)$",
        message,
        re.IGNORECASE,
    )
    if match is None:
        return detail
    marker = safe_label(match.group("marker").lower())
    path = match.group("path").strip()
    path = re.sub(r"^## [^:]+:\s*", "", path)
    path = re.sub(r"^diff:[^:]+:", "", path)
    detail.update(marker=marker, path=safe_label(path))
    return detail

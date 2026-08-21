#!/usr/bin/env python3
"""Validation and hashing for the reusable product-walkthrough media manifest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
from pathlib import Path
from typing import Any

CHAPTER_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
SECRET_NAME = re.compile(r"(?:api[_-]?key|token|secret|password|credential)", re.IGNORECASE)
ALLOWED_SETTINGS = frozenset({"stability", "similarity_boost", "style", "use_speaker_boost"})


class MediaContractError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step


def require(condition: bool, step: str, message: str) -> None:
    if not condition:
        raise MediaContractError(step, message)


def as_dict(raw: Any, step: str, message: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise MediaContractError(step, message)
    return raw


def as_text(raw: Any, step: str, message: str) -> str:
    if not isinstance(raw, str) or not raw:
        raise MediaContractError(step, message)
    return raw


def as_list(raw: Any, step: str, message: str) -> list[Any]:
    if not isinstance(raw, list) or not raw:
        raise MediaContractError(step, message)
    return raw


def read_json(path: Path, step: str) -> dict[str, Any]:
    reject_symlink_components(path, step)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MediaContractError(step, f"invalid JSON file: {path}") from exc
    return as_dict(value, step, f"JSON root must be an object: {path}")


def digest(path: Path) -> str:
    step = "media.digest"
    reject_symlink_components(path, step)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise MediaContractError(step, f"cannot open regular file: {path}") from exc
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), step, f"not a regular file: {path}")
        hasher = hashlib.sha256()
        while chunk := os.read(descriptor, 1024 * 1024):
            hasher.update(chunk)
        after = os.fstat(descriptor)
        require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            step,
            f"file changed while hashing: {path}",
        )
        return hasher.hexdigest()
    finally:
        os.close(descriptor)


def reject_symlink_components(path: Path, step: str, *, include_final: bool = True) -> None:
    absolute = Path(os.path.abspath(path))
    parts = absolute.parts
    current = Path(parts[0])
    limit = len(parts) if include_final else len(parts) - 1
    for index in range(1, limit):
        current /= parts[index]
        try:
            require(not stat.S_ISLNK(current.lstat().st_mode), step, f"path contains symlink: {current}")
        except FileNotFoundError:
            break


def read_bytes_no_follow(path: Path, step: str) -> bytes:
    return read_bytes_identity(path, step)[0]


def read_bytes_identity(path: Path, step: str) -> tuple[bytes, dict[str, Any]]:
    reject_symlink_components(path, step)
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as exc:
        raise MediaContractError(step, f"cannot open regular file: {path}") from exc
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode), step, f"not a regular file: {path}")
        require(before.st_size <= 25 * 1024 * 1024, step, f"audio file is too large: {path}")
        chunks: list[bytes] = []
        while chunk := os.read(descriptor, 1024 * 1024):
            chunks.append(chunk)
        after = os.fstat(descriptor)
        require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
            step,
            f"file changed while reading: {path}",
        )
        payload = b"".join(chunks)
        identity = {"path": str(path), "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)}
        return payload, identity
    finally:
        os.close(descriptor)


def bytes_identity(path: Path, step: str) -> dict[str, Any]:
    return read_bytes_identity(path, step)[1]


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def object_digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return text_digest(encoded)


def inside(root: Path, path: Path, step: str, field: str) -> Path:
    resolved = Path(os.path.abspath(path))
    owner = Path(os.path.abspath(root))
    try:
        resolved.relative_to(owner)
    except ValueError as exc:
        raise MediaContractError(step, f"{field} escapes project root") from exc
    reject_symlink_components(resolved, step, include_final=resolved.exists())
    return resolved


def project_path(root: Path, raw: Any, step: str, field: str, *, exists: bool = True) -> Path:
    candidate = Path(as_text(raw, step, f"{field} must be a project-relative path"))
    require(not candidate.is_absolute(), step, f"{field} must be project-relative")
    resolved = inside(root, root / candidate, step, field)
    if exists:
        require(resolved.is_file() and not resolved.is_symlink(), step, f"{field} must be a regular file")
    return resolved


def executable(raw: Any, step: str, field: str) -> Path:
    name = as_text(raw, step, f"{field} is required")
    candidate = Path(name)
    if candidate.is_absolute():
        path = candidate.resolve(strict=True)
    else:
        require(candidate.name == name, step, f"{field} must be an executable name or absolute path")
        path = Path(as_text(shutil.which(name), step, f"{field} is unavailable")).resolve(strict=True)
    reject_symlink_components(path, step)
    require(path.is_file() and os.access(path, os.X_OK), step, f"{field} is not executable")
    return path


def number(raw: Any, step: str, field: str, minimum: float, maximum: float) -> float:
    require(isinstance(raw, (int, float)) and not isinstance(raw, bool), step, f"{field} must be numeric")
    value = float(raw)
    require(minimum <= value <= maximum, step, f"{field} is outside {minimum}..{maximum}")
    return value


def validate_credential(root: Path, raw: Any, step: str) -> dict[str, Any]:
    credential = as_dict(raw, step, "narration.credential must be an object")
    source = credential.get("source")
    require(source in {"project-env", "keychain"}, step, "credential source must be project-env or keychain")
    if source == "project-env":
        require(set(credential) == {"source", "path", "variable"}, step, "project-env credential fields mismatch")
        path = project_path(root, credential.get("path"), step, "narration.credential.path")
        variable = as_text(credential.get("variable"), step, "credential variable is invalid")
        require(re.fullmatch(r"[A-Z][A-Z0-9_]*", variable) is not None, step, "credential variable is invalid")
        return {"source": source, "path": path, "variable": variable}
    require(set(credential) == {"source", "account", "service"}, step, "keychain credential fields mismatch")
    account = as_text(credential.get("account"), step, "keychain account is required")
    service = as_text(credential.get("service"), step, "keychain service is required")
    return {"source": source, "account": account, "service": service}


def validate_manifest(job_path: Path) -> dict[str, Any]:
    step = "media.validate"
    job = read_json(job_path, step)
    project = as_dict(job.get("project"), step, "job project/artifacts are required")
    artifacts = as_dict(job.get("artifacts"), step, "job project/artifacts are required")
    root_raw = as_text(project.get("root"), step, "project.root must be absolute")
    artifact_raw = as_text(artifacts.get("root"), step, "artifacts.root must be absolute")
    manifest_raw = as_text(job.get("media_manifest"), step, "media_manifest must be absolute")
    require(Path(root_raw).is_absolute(), step, "project.root must be absolute")
    require(Path(artifact_raw).is_absolute(), step, "artifacts.root must be absolute")
    require(Path(manifest_raw).is_absolute(), step, "media_manifest must be absolute")
    root = Path(os.path.abspath(root_raw))
    reject_symlink_components(root, step)
    artifact_root = inside(root, Path(artifact_raw), step, "artifacts.root")
    manifest_path = inside(root, Path(manifest_raw), step, "media_manifest")
    require(root.is_dir(), step, "project.root does not exist")
    manifest = read_json(manifest_path, step)
    require(manifest.get("schema_version") == 1, step, "media manifest schema_version must equal 1")
    require(
        set(manifest) == {"schema_version", "cache_dir", "narration", "render", "qa", "chapters"},
        step,
        "media manifest fields mismatch",
    )

    narration = as_dict(manifest.get("narration"), step, "narration must be an object")
    require(
        set(narration) == {"voice_id", "voice_name", "model_id", "settings", "credential"},
        step,
        "narration fields mismatch",
    )
    for field in ("voice_id", "voice_name", "model_id"):
        as_text(narration.get(field), step, f"narration.{field} is required")
    settings = as_dict(narration.get("settings"), step, "voice settings fields mismatch")
    require(set(settings) == ALLOWED_SETTINGS, step, "voice settings fields mismatch")
    for field in ("stability", "similarity_boost", "style"):
        number(settings.get(field), step, f"settings.{field}", 0, 1)
    require(isinstance(settings.get("use_speaker_boost"), bool), step, "settings.use_speaker_boost must be boolean")
    credential = validate_credential(root, narration.get("credential"), step)

    render = as_dict(manifest.get("render"), step, "render must be an object")
    render_fields = {
        "ffmpeg",
        "ffprobe",
        "width",
        "height",
        "fps",
        "tail_seconds",
        "silence_db",
        "silence_start_seconds",
        "silence_stop_seconds",
        "video_codec",
        "audio_codec",
        "crf",
        "preset",
    }
    require(set(render) == render_fields, step, "render fields mismatch")
    ffmpeg = executable(render.get("ffmpeg"), step, "render.ffmpeg")
    ffprobe = executable(render.get("ffprobe"), step, "render.ffprobe")
    width = int(number(render.get("width"), step, "render.width", 320, 7680))
    height = int(number(render.get("height"), step, "render.height", 240, 4320))
    fps = int(number(render.get("fps"), step, "render.fps", 1, 120))
    tail_seconds = number(render.get("tail_seconds"), step, "render.tail_seconds", 0, 3)
    silence_db = number(render.get("silence_db"), step, "render.silence_db", -80, -10)
    silence_start = number(render.get("silence_start_seconds"), step, "render.silence_start_seconds", 0.01, 2)
    silence_stop = number(render.get("silence_stop_seconds"), step, "render.silence_stop_seconds", 0.01, 2)
    require(render.get("video_codec") == "libx264", step, "render.video_codec must equal libx264")
    require(render.get("audio_codec") == "aac", step, "render.audio_codec must equal aac")
    crf = int(number(render.get("crf"), step, "render.crf", 0, 51))
    preset = render.get("preset")
    require(preset in {"veryfast", "faster", "fast", "medium", "slow"}, step, "render.preset is invalid")

    qa = as_dict(manifest.get("qa"), step, "qa must be an object")
    require(
        set(qa)
        == {"sample_interval_seconds", "contact_sheet_columns", "contact_sheet_rows", "max_boundary_silence_seconds"},
        step,
        "qa fields mismatch",
    )
    sample_interval = number(qa.get("sample_interval_seconds"), step, "qa.sample_interval_seconds", 1, 60)
    columns = int(number(qa.get("contact_sheet_columns"), step, "qa.contact_sheet_columns", 1, 8))
    rows = int(number(qa.get("contact_sheet_rows"), step, "qa.contact_sheet_rows", 1, 8))
    max_boundary_silence = number(
        qa.get("max_boundary_silence_seconds"), step, "qa.max_boundary_silence_seconds", 0.1, 3
    )

    chapters_raw = as_list(manifest.get("chapters"), step, "chapters must be a non-empty list")
    chapters: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(chapters_raw):
        chapter = as_dict(raw, step, f"chapter {index} fields mismatch")
        require(set(chapter) == {"id", "text", "visual"}, step, f"chapter {index} fields mismatch")
        identifier = as_text(chapter.get("id"), step, f"chapter {index} id is invalid")
        require(CHAPTER_ID.fullmatch(identifier) is not None, step, f"chapter {index} id is invalid")
        require(identifier not in identifiers, step, f"chapter {identifier} is duplicated")
        identifiers.add(identifier)
        text = as_text(chapter.get("text"), step, f"chapter {identifier} text is required")
        require(bool(text.strip()), step, f"chapter {identifier} text is required")
        visual = as_dict(chapter.get("visual"), step, f"chapter {identifier} visual is required")
        require(
            set(visual) == {"kind", "path", "sha256", "minimum_duration_seconds", "trim_start_seconds"},
            step,
            f"chapter {identifier} visual fields mismatch",
        )
        kind = visual.get("kind")
        require(kind in {"image", "video"}, step, f"chapter {identifier} visual kind is invalid")
        path = project_path(root, visual.get("path"), step, f"chapter {identifier} visual.path")
        expected_hash = as_text(visual.get("sha256"), step, f"chapter {identifier} visual hash is invalid")
        require(SHA256.fullmatch(expected_hash) is not None, step, f"chapter {identifier} visual hash is invalid")
        require(digest(path) == expected_hash, step, f"chapter {identifier} visual hash mismatch")
        minimum_duration = number(
            visual.get("minimum_duration_seconds"), step, f"chapter {identifier} minimum duration", 0, 600
        )
        trim_start = number(visual.get("trim_start_seconds"), step, f"chapter {identifier} trim start", 0, 3600)
        require(kind == "video" or trim_start == 0, step, f"chapter {identifier} image trim start must be zero")
        chapters.append(
            {
                "id": identifier,
                "text": text,
                "visual": {
                    "kind": kind,
                    "path": path,
                    "sha256": expected_hash,
                    "minimum_duration_seconds": minimum_duration,
                    "trim_start_seconds": trim_start,
                },
            }
        )

    scene_path_raw = as_text(job.get("scene_manifest"), step, "scene_manifest must be absolute")
    require(Path(scene_path_raw).is_absolute(), step, "scene_manifest must be absolute")
    scene_document = read_json(inside(root, Path(scene_path_raw), step, "scene_manifest"), step)
    scene_ids = [item.get("id") for item in scene_document.get("scenes", []) if isinstance(item, dict)]
    require(scene_ids == [item["id"] for item in chapters], step, "media chapters must match ordered scene IDs")
    scene_narration = [item.get("narration") for item in scene_document.get("scenes", []) if isinstance(item, dict)]
    require(scene_narration == [item["text"] for item in chapters], step, "media narration must match scene narration")

    cache_dir = project_path(root, manifest.get("cache_dir"), step, "cache_dir", exists=False)
    script_owner = [{"id": item["id"], "text": item["text"]} for item in chapters]
    settings_owner = {"voice_id": narration["voice_id"], "model_id": narration["model_id"], "settings": settings}
    return {
        "job": job,
        "job_path": job_path.resolve(),
        "job_sha256": digest(job_path),
        "root": root,
        "artifact_root": artifact_root,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_sha256": digest(manifest_path),
        "cache_dir": cache_dir,
        "chapters": chapters,
        "narration": narration,
        "credential": credential,
        "ffmpeg": ffmpeg,
        "ffprobe": ffprobe,
        "render": {
            **render,
            "width": width,
            "height": height,
            "fps": fps,
            "tail_seconds": tail_seconds,
            "silence_db": silence_db,
            "silence_start_seconds": silence_start,
            "silence_stop_seconds": silence_stop,
            "crf": crf,
            "preset": preset,
        },
        "qa": {
            "sample_interval_seconds": sample_interval,
            "contact_sheet_columns": columns,
            "contact_sheet_rows": rows,
            "max_boundary_silence_seconds": max_boundary_silence,
        },
        "script_sha256": object_digest(script_owner),
        "settings_sha256": object_digest(settings_owner),
        "characters": sum(len(item["text"]) for item in chapters),
    }

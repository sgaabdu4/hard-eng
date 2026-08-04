#!/usr/bin/env python3
"""Validation and hashing for the reusable product-walkthrough media manifest."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

CHAPTER_ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
SHA256 = re.compile(r"[0-9a-f]{64}")
SECRET_NAME = re.compile(
    r"(?:api[_-]?key|token|secret|password|credential)", re.IGNORECASE
)
ALLOWED_SETTINGS = frozenset(
    {"stability", "similarity_boost", "style", "use_speaker_boost"}
)


class MediaContractError(RuntimeError):
    def __init__(self, step: str, message: str) -> None:
        super().__init__(message)
        self.step = step


def require(condition: bool, step: str, message: str) -> None:
    if not condition:
        raise MediaContractError(step, message)


def read_json(path: Path, step: str) -> dict[str, Any]:
    require(
        path.is_file() and not path.is_symlink(),
        step,
        f"missing regular JSON file: {path}",
    )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MediaContractError(step, f"invalid JSON file: {path}") from exc
    require(isinstance(value, dict), step, f"JSON root must be an object: {path}")
    return value


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def object_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return text_digest(encoded)


def inside(root: Path, path: Path, step: str, field: str) -> Path:
    resolved = path.resolve(strict=False)
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise MediaContractError(step, f"{field} escapes project root") from exc
    return resolved


def project_path(
    root: Path, raw: Any, step: str, field: str, *, exists: bool = True
) -> Path:
    require(
        isinstance(raw, str) and bool(raw),
        step,
        f"{field} must be a project-relative path",
    )
    candidate = Path(raw)
    require(not candidate.is_absolute(), step, f"{field} must be project-relative")
    resolved = inside(root, root / candidate, step, field)
    if exists:
        require(
            resolved.is_file() and not resolved.is_symlink(),
            step,
            f"{field} must be a regular file",
        )
    return resolved


def executable(raw: Any, step: str, field: str) -> Path:
    require(isinstance(raw, str) and bool(raw), step, f"{field} is required")
    candidate = Path(raw)
    if candidate.is_absolute():
        path = candidate.resolve()
    else:
        require(
            candidate.name == raw,
            step,
            f"{field} must be an executable name or absolute path",
        )
        resolved = shutil.which(raw)
        require(resolved is not None, step, f"{field} is unavailable")
        path = Path(resolved).resolve()
    require(
        path.is_file() and os.access(path, os.X_OK), step, f"{field} is not executable"
    )
    return path


def number(raw: Any, step: str, field: str, minimum: float, maximum: float) -> float:
    require(
        isinstance(raw, (int, float)) and not isinstance(raw, bool),
        step,
        f"{field} must be numeric",
    )
    value = float(raw)
    require(
        minimum <= value <= maximum, step, f"{field} is outside {minimum}..{maximum}"
    )
    return value


def validate_credential(root: Path, raw: Any, step: str) -> dict[str, Any]:
    require(isinstance(raw, dict), step, "narration.credential must be an object")
    source = raw.get("source")
    require(
        source in {"project-env", "keychain"},
        step,
        "credential source must be project-env or keychain",
    )
    if source == "project-env":
        require(
            set(raw) == {"source", "path", "variable"},
            step,
            "project-env credential fields mismatch",
        )
        path = project_path(root, raw.get("path"), step, "narration.credential.path")
        variable = raw.get("variable")
        require(
            isinstance(variable, str)
            and re.fullmatch(r"[A-Z][A-Z0-9_]*", variable) is not None,
            step,
            "credential variable is invalid",
        )
        return {"source": source, "path": path, "variable": variable}
    require(
        set(raw) == {"source", "account", "service"},
        step,
        "keychain credential fields mismatch",
    )
    account = raw.get("account")
    service = raw.get("service")
    require(
        isinstance(account, str) and bool(account), step, "keychain account is required"
    )
    require(
        isinstance(service, str) and bool(service), step, "keychain service is required"
    )
    return {"source": source, "account": account, "service": service}


def validate_manifest(job_path: Path) -> dict[str, Any]:
    step = "media.validate"
    job = read_json(job_path, step)
    project = job.get("project")
    artifacts = job.get("artifacts")
    require(
        isinstance(project, dict) and isinstance(artifacts, dict),
        step,
        "job project/artifacts are required",
    )
    root_raw = project.get("root")
    artifact_raw = artifacts.get("root")
    manifest_raw = job.get("media_manifest")
    require(
        isinstance(root_raw, str) and Path(root_raw).is_absolute(),
        step,
        "project.root must be absolute",
    )
    require(
        isinstance(artifact_raw, str) and Path(artifact_raw).is_absolute(),
        step,
        "artifacts.root must be absolute",
    )
    require(
        isinstance(manifest_raw, str) and Path(manifest_raw).is_absolute(),
        step,
        "media_manifest must be absolute",
    )
    root = Path(root_raw).resolve()
    artifact_root = inside(root, Path(artifact_raw), step, "artifacts.root")
    manifest_path = inside(root, Path(manifest_raw), step, "media_manifest")
    require(root.is_dir(), step, "project.root does not exist")
    manifest = read_json(manifest_path, step)
    require(
        manifest.get("schema_version") == 1,
        step,
        "media manifest schema_version must equal 1",
    )
    require(
        set(manifest)
        == {"schema_version", "cache_dir", "narration", "render", "qa", "chapters"},
        step,
        "media manifest fields mismatch",
    )

    narration = manifest.get("narration")
    require(isinstance(narration, dict), step, "narration must be an object")
    require(
        set(narration)
        == {"voice_id", "voice_name", "model_id", "settings", "credential"},
        step,
        "narration fields mismatch",
    )
    for field in ("voice_id", "voice_name", "model_id"):
        require(
            isinstance(narration.get(field), str) and bool(narration[field]),
            step,
            f"narration.{field} is required",
        )
    settings = narration.get("settings")
    require(
        isinstance(settings, dict) and set(settings) == ALLOWED_SETTINGS,
        step,
        "voice settings fields mismatch",
    )
    for field in ("stability", "similarity_boost", "style"):
        number(settings.get(field), step, f"settings.{field}", 0, 1)
    require(
        isinstance(settings.get("use_speaker_boost"), bool),
        step,
        "settings.use_speaker_boost must be boolean",
    )
    credential = validate_credential(root, narration.get("credential"), step)

    render = manifest.get("render")
    require(isinstance(render, dict), step, "render must be an object")
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
    silence_start = number(
        render.get("silence_start_seconds"),
        step,
        "render.silence_start_seconds",
        0.01,
        2,
    )
    silence_stop = number(
        render.get("silence_stop_seconds"), step, "render.silence_stop_seconds", 0.01, 2
    )
    require(
        render.get("video_codec") == "libx264",
        step,
        "render.video_codec must equal libx264",
    )
    require(
        render.get("audio_codec") == "aac", step, "render.audio_codec must equal aac"
    )
    crf = int(number(render.get("crf"), step, "render.crf", 0, 51))
    preset = render.get("preset")
    require(
        preset in {"veryfast", "faster", "fast", "medium", "slow"},
        step,
        "render.preset is invalid",
    )

    qa = manifest.get("qa")
    require(isinstance(qa, dict), step, "qa must be an object")
    require(
        set(qa)
        == {
            "sample_interval_seconds",
            "contact_sheet_columns",
            "contact_sheet_rows",
            "max_boundary_silence_seconds",
        },
        step,
        "qa fields mismatch",
    )
    sample_interval = number(
        qa.get("sample_interval_seconds"), step, "qa.sample_interval_seconds", 1, 60
    )
    columns = int(
        number(qa.get("contact_sheet_columns"), step, "qa.contact_sheet_columns", 1, 8)
    )
    rows = int(
        number(qa.get("contact_sheet_rows"), step, "qa.contact_sheet_rows", 1, 8)
    )
    max_boundary_silence = number(
        qa.get("max_boundary_silence_seconds"),
        step,
        "qa.max_boundary_silence_seconds",
        0.1,
        3,
    )

    chapters_raw = manifest.get("chapters")
    require(
        isinstance(chapters_raw, list) and bool(chapters_raw),
        step,
        "chapters must be a non-empty list",
    )
    chapters: list[dict[str, Any]] = []
    identifiers: set[str] = set()
    for index, raw in enumerate(chapters_raw):
        require(
            isinstance(raw, dict) and set(raw) == {"id", "text", "visual"},
            step,
            f"chapter {index} fields mismatch",
        )
        identifier = raw.get("id")
        require(
            isinstance(identifier, str)
            and CHAPTER_ID.fullmatch(identifier) is not None,
            step,
            f"chapter {index} id is invalid",
        )
        require(
            identifier not in identifiers, step, f"chapter {identifier} is duplicated"
        )
        identifiers.add(identifier)
        text = raw.get("text")
        require(
            isinstance(text, str) and bool(text.strip()),
            step,
            f"chapter {identifier} text is required",
        )
        visual = raw.get("visual")
        require(
            isinstance(visual, dict), step, f"chapter {identifier} visual is required"
        )
        require(
            set(visual)
            == {
                "kind",
                "path",
                "sha256",
                "minimum_duration_seconds",
                "trim_start_seconds",
            },
            step,
            f"chapter {identifier} visual fields mismatch",
        )
        kind = visual.get("kind")
        require(
            kind in {"image", "video"},
            step,
            f"chapter {identifier} visual kind is invalid",
        )
        path = project_path(
            root, visual.get("path"), step, f"chapter {identifier} visual.path"
        )
        expected_hash = visual.get("sha256")
        require(
            isinstance(expected_hash, str)
            and SHA256.fullmatch(expected_hash) is not None,
            step,
            f"chapter {identifier} visual hash is invalid",
        )
        require(
            digest(path) == expected_hash,
            step,
            f"chapter {identifier} visual hash mismatch",
        )
        minimum_duration = number(
            visual.get("minimum_duration_seconds"),
            step,
            f"chapter {identifier} minimum duration",
            0,
            600,
        )
        trim_start = number(
            visual.get("trim_start_seconds"),
            step,
            f"chapter {identifier} trim start",
            0,
            3600,
        )
        require(
            kind == "video" or trim_start == 0,
            step,
            f"chapter {identifier} image trim start must be zero",
        )
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

    scene_path_raw = job.get("scene_manifest")
    require(
        isinstance(scene_path_raw, str) and Path(scene_path_raw).is_absolute(),
        step,
        "scene_manifest must be absolute",
    )
    scene_document = read_json(
        inside(root, Path(scene_path_raw), step, "scene_manifest"), step
    )
    scene_ids = [
        item.get("id")
        for item in scene_document.get("scenes", [])
        if isinstance(item, dict)
    ]
    require(
        scene_ids == [item["id"] for item in chapters],
        step,
        "media chapters must match ordered scene IDs",
    )
    scene_narration = [
        item.get("narration")
        for item in scene_document.get("scenes", [])
        if isinstance(item, dict)
    ]
    require(
        scene_narration == [item["text"] for item in chapters],
        step,
        "media narration must match scene narration",
    )

    cache_dir = project_path(
        root, manifest.get("cache_dir"), step, "cache_dir", exists=False
    )
    script_owner = [{"id": item["id"], "text": item["text"]} for item in chapters]
    settings_owner = {
        "voice_id": narration["voice_id"],
        "model_id": narration["model_id"],
        "settings": settings,
    }
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

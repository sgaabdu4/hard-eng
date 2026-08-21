#!/usr/bin/env python3
"""Shared synthetic media fixture for walkthrough contract regressions."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from media_common import git_environment

SENTINEL = "DO_NOT_COPY_PRIVATE_VALUE_9482"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def object_sha256(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fake_media_tool_source(kind: str, *, long_silence: bool) -> str:
    if kind == "ffprobe":
        return """#!/usr/bin/env python3
import json
import sys
payload = sys.stdin.buffer.read()
if b"undecodable" in payload:
    raise SystemExit(3)
if "pipe:0" in sys.argv:
    print(json.dumps({"format": {"duration": "2.0", "format_name": "mp3"}, "streams": [{"codec_type": "audio", "codec_name": "mp3"}]}))
else:
    print(json.dumps({"format": {"duration": "2.0", "format_name": "mov,mp4"}, "streams": [{"codec_type": "video", "codec_name": "h264"}, {"codec_type": "audio", "codec_name": "aac"}]}))
"""
    silence_output = (
        "[silencedetect] silence_start: 0.0\n[silencedetect] silence_end: 0.9 | silence_duration: 0.9\n"
        if long_silence
        else ""
    )
    return f"""#!/usr/bin/env python3
import pathlib
import sys

arguments = sys.argv[1:]
if any("silencedetect=" in item for item in arguments):
    sys.stderr.write({silence_output!r})
if arguments and arguments[-1] != "-" and not ("-h" in arguments):
    output = pathlib.Path(arguments[-1])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"synthetic media output" * 16)
"""


def make_media_project(base: Path, name: str, *, long_silence: bool = False) -> tuple[Path, Path, Path]:
    root = base / name
    root.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=git_environment(),
        timeout=10,
        check=True,
    )
    (root / ".gitignore").write_text(".env.local\n.walkthrough-cache/\nartifacts/\n", encoding="utf-8")
    (root / ".env.local").write_text(f"ELEVEN_LABS_API_KEY={SENTINEL}\n", encoding="utf-8")
    visual = root / "visual.png"
    visual.write_bytes(b"synthetic visual" * 16)
    ffmpeg = root / "ffmpeg-fixture"
    ffprobe = root / "ffprobe-fixture"
    ffmpeg.write_text(fake_media_tool_source("ffmpeg", long_silence=long_silence), encoding="utf-8")
    ffprobe.write_text(fake_media_tool_source("ffprobe", long_silence=False), encoding="utf-8")
    ffmpeg.chmod(0o700)
    ffprobe.chmod(0o700)
    text = "A friendly synthetic walkthrough."
    scene_manifest = root / "scenes.json"
    write_json(scene_manifest, {"schema_version": 1, "scenes": [{"id": "welcome", "narration": text}]})
    settings = {"stability": 0.35, "similarity_boost": 0.85, "style": 0.3, "use_speaker_boost": True}
    media_manifest = root / "media.json"
    write_json(
        media_manifest,
        {
            "schema_version": 1,
            "cache_dir": ".walkthrough-cache/narration-v1",
            "narration": {
                "voice_id": "fixture-voice",
                "voice_name": "Fixture Voice",
                "model_id": "fixture-model",
                "settings": settings,
                "credential": {"source": "project-env", "path": ".env.local", "variable": "ELEVEN_LABS_API_KEY"},
            },
            "render": {
                "ffmpeg": str(ffmpeg),
                "ffprobe": str(ffprobe),
                "width": 1440,
                "height": 900,
                "fps": 30,
                "tail_seconds": 0.25,
                "silence_db": -40,
                "silence_start_seconds": 0.1,
                "silence_stop_seconds": 0.15,
                "video_codec": "libx264",
                "audio_codec": "aac",
                "crf": 20,
                "preset": "fast",
            },
            "qa": {
                "sample_interval_seconds": 4,
                "contact_sheet_columns": 4,
                "contact_sheet_rows": 4,
                "max_boundary_silence_seconds": 0.45,
            },
            "chapters": [
                {
                    "id": "welcome",
                    "text": text,
                    "visual": {
                        "kind": "image",
                        "path": "visual.png",
                        "sha256": sha256(visual),
                        "minimum_duration_seconds": 1,
                        "trim_start_seconds": 0,
                    },
                }
            ],
        },
    )
    artifact_root = root / "artifacts" / f"attempt-{name}"
    job = root / "job.json"
    write_json(
        job,
        {
            "schema_version": 1,
            "mode": "production",
            "project": {"name": "Synthetic media project", "root": str(root)},
            "artifacts": {"root": str(artifact_root), "receipts": str(artifact_root / "receipts")},
            "scene_manifest": str(scene_manifest),
            "media_manifest": str(media_manifest),
            "narration": {"mode": "elevenlabs"},
        },
    )
    settings_owner = {"voice_id": "fixture-voice", "model_id": "fixture-model", "settings": settings}
    script_sha256 = object_sha256([{"id": "welcome", "text": text}])
    settings_sha256 = object_sha256(settings_owner)
    approval = root / "approval.json"
    write_json(
        approval,
        {
            "status": "approved",
            "job_sha256": sha256(job),
            "script_sha256": script_sha256,
            "settings_sha256": settings_sha256,
            "characters": len(text),
            "impact": "zero requests because the fixture cache is warm",
            "user_reply": "approved fixture",
        },
    )
    cache_key = object_sha256(
        {"text": text, "voice_id": "fixture-voice", "model_id": "fixture-model", "settings": settings}
    )
    cached = root / ".walkthrough-cache" / "narration-v1" / f"{cache_key}.mp3"
    cached.parent.mkdir(parents=True)
    audio = b"synthetic cached narration" * 16
    cached.write_bytes(audio)
    request_body = {"text": text, "model_id": "fixture-model", "voice_settings": settings}
    request_digest = object_sha256(
        {
            "endpoint": "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            "voice_id": "fixture-voice",
            "body_sha256": object_sha256(request_body),
            "accept": "audio/mpeg",
        }
    )
    write_json(
        cached.with_suffix(".json"),
        {
            "schema_version": 1,
            "cache_key": cache_key,
            "provider_request_sha256": request_digest,
            "audio_sha256": hashlib.sha256(audio).hexdigest(),
            "bytes": len(audio),
            "format": "audio/mpeg",
            "created": {"script_sha256": script_sha256, "settings_sha256": settings_sha256, "chapter_id": "welcome"},
        },
    )
    return job, approval, scene_manifest

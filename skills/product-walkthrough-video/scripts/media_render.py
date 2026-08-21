#!/usr/bin/env python3
"""FFmpeg render and mechanical QA for the walkthrough media pipeline."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from media_common import probe_mp3, run_checked, write_bytes_once, write_json_once
from media_manifest import MediaContractError, digest, read_bytes_identity, read_json, require
from media_narration import cache_key, provider_request_digest


def ffprobe_json(context: dict[str, Any], path: Path, step: str) -> dict[str, Any]:
    result = run_checked(
        [str(context["ffprobe"]), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        step,
        capture_stdout=True,
    )
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaContractError(step, "FFprobe returned invalid JSON") from exc
    require(isinstance(value, dict), step, "FFprobe result must be an object")
    return value


def media_duration(context: dict[str, Any], path: Path, step: str) -> float:
    value = ffprobe_json(context, path, step)
    try:
        duration = float(value["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise MediaContractError(step, "media duration is unavailable") from exc
    require(duration > 0, step, "media duration must be positive")
    return duration


def temporary_output(destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    require(not destination.exists(), "render.output", f"refusing to overwrite output: {destination}")
    descriptor, raw = tempfile.mkstemp(
        prefix=f".{destination.stem}.", suffix=f".tmp{destination.suffix}", dir=destination.parent
    )
    os.close(descriptor)
    return Path(raw)


def promote_output(temporary: Path, destination: Path, step: str) -> None:
    require(temporary.is_file() and temporary.stat().st_size > 0, step, "local media command produced no output")
    require(not destination.exists(), step, f"refusing to overwrite output: {destination}")
    descriptor = os.open(temporary, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.link(temporary, destination)
    temporary.unlink(missing_ok=True)
    parent = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def trim_audio(context: dict[str, Any], source: bytes, destination: Path, chapter_id: str) -> float:
    step = f"render.audio.{chapter_id}"
    temporary = temporary_output(destination)
    audio_filter = (
        f"silenceremove=start_periods=1:"
        f"start_duration={context['render']['silence_start_seconds']}:"
        f"start_threshold={context['render']['silence_db']}dB,areverse,"
        f"silenceremove=start_periods=1:"
        f"start_duration={context['render']['silence_stop_seconds']}:"
        f"start_threshold={context['render']['silence_db']}dB,areverse"
    )
    try:
        run_checked(
            [
                str(context["ffmpeg"]),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                "pipe:0",
                "-af",
                audio_filter,
                "-ar",
                "48000",
                "-ac",
                "2",
                str(temporary),
            ],
            step,
            input_data=source,
        )
        promote_output(temporary, destination, step)
    finally:
        temporary.unlink(missing_ok=True)
    return media_duration(context, destination, f"{step}.probe")


def render_scene(
    context: dict[str, Any], chapter: dict[str, Any], audio: Path, duration: float, destination: Path
) -> None:
    step = f"render.scene.{chapter['id']}"
    temporary = temporary_output(destination)
    visual = chapter["visual"]
    width = context["render"]["width"]
    height = context["render"]["height"]
    fps = context["render"]["fps"]
    fade = min(0.35, duration / 5)
    video_filter = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"tpad=stop_mode=clone:stop_duration={duration:.6f},"
        f"trim=duration={duration:.6f},setpts=PTS-STARTPTS,fps={fps},"
        f"format=yuv420p,fade=t=in:st=0:d={fade:.3f},"
        f"fade=t=out:st={max(0, duration - fade):.3f}:d={fade:.3f}"
    )
    argv = [str(context["ffmpeg"]), "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if visual["kind"] == "image":
        argv.extend(["-loop", "1", "-framerate", str(fps), "-i", str(visual["path"])])
    else:
        argv.extend(["-ss", f"{visual['trim_start_seconds']:.6f}", "-i", str(visual["path"])])
    argv.extend(
        [
            "-i",
            str(audio),
            "-filter_complex",
            f"[0:v]{video_filter}[v];[1:a]apad=pad_dur={context['render']['tail_seconds']:.6f}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            "-t",
            f"{duration:.6f}",
            "-c:v",
            context["render"]["video_codec"],
            "-preset",
            context["render"]["preset"],
            "-crf",
            str(context["render"]["crf"]),
            "-c:a",
            context["render"]["audio_codec"],
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(temporary),
        ]
    )
    try:
        run_checked(argv, step)
        promote_output(temporary, destination, step)
    finally:
        temporary.unlink(missing_ok=True)


def narration_inputs(context: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    step = "render.narration-inputs"
    root = context["artifact_root"]
    receipt_path = root / "narration.json"
    receipt = read_json(receipt_path, step)
    require(
        set(receipt)
        == {
            "schema_version",
            "status",
            "job_path",
            "job_sha256",
            "media_manifest",
            "script_sha256",
            "settings_sha256",
            "approval",
            "voice",
            "requests",
            "cache_hits",
            "characters",
            "credential",
            "chapters",
            "cleanup",
        },
        step,
        "narration receipt fields mismatch",
    )
    require(
        receipt.get("schema_version") == 1 and receipt.get("status") == "pass", step, "narration receipt is not a pass"
    )
    require(receipt.get("job_sha256") == context["job_sha256"], step, "narration receipt is stale")
    require(receipt.get("script_sha256") == context["script_sha256"], step, "narration script hash mismatch")
    require(receipt.get("settings_sha256") == context["settings_sha256"], step, "narration settings hash mismatch")
    rows = receipt.get("chapters")
    require(isinstance(rows, list), step, "narration chapters are missing")
    assert isinstance(rows, list)
    expected_fields = {
        "id",
        "path",
        "canonical_path",
        "path_policy",
        "sha256",
        "bytes",
        "characters",
        "cache_key",
        "provider_request_sha256",
        "format",
        "cache_metadata_sha256",
        "cache_hit",
    }
    require(len(rows) == len(context["chapters"]), step, "narration chapter count mismatch")
    identifiers = [row.get("id") for row in rows if isinstance(row, dict)]
    require(len(identifiers) == len(set(identifiers)), step, "duplicate narration chapter")
    audio_root = root / "audio"
    expected_audio = {audio_root / f"{chapter['id']}.mp3" for chapter in context["chapters"]}
    actual_audio = set(audio_root.iterdir()) if audio_root.is_dir() else set()
    require(actual_audio == expected_audio, step, "narration audio files do not match expected chapters")
    inputs: list[dict[str, Any]] = []
    for chapter, row in zip(context["chapters"], rows, strict=True):
        require(isinstance(row, dict) and set(row) == expected_fields, step, "narration chapter fields mismatch")
        identifier = chapter["id"]
        require(row["id"] == identifier, step, f"narration chapter order mismatch: {identifier}")
        path = root / "audio" / f"{identifier}.mp3"
        require(row["path"] == str(path), step, f"narration chapter path mismatch: {identifier}")
        payload, identity = read_bytes_identity(path, step)
        require(
            row["canonical_path"] == str(path.resolve(strict=True)),
            step,
            f"narration canonical path mismatch: {identifier}",
        )
        require(row["path_policy"] == "no-symlink-components", step, f"narration path policy mismatch: {identifier}")
        require(row["sha256"] == identity["sha256"], step, f"narration audio hash mismatch: {identifier}")
        require(row["bytes"] == identity["bytes"], step, f"narration audio byte count mismatch: {identifier}")
        require(row["characters"] == len(chapter["text"]), step, f"narration character count mismatch: {identifier}")
        require(row["cache_key"] == cache_key(context, chapter), step, f"narration cache key mismatch: {identifier}")
        require(
            row["provider_request_sha256"] == provider_request_digest(context, chapter),
            step,
            f"narration provider request mismatch: {identifier}",
        )
        require(row["format"] == "audio/mpeg", step, f"narration format mismatch: {identifier}")
        metadata_path = context["cache_dir"] / f"{row['cache_key']}.json"
        require(
            row["cache_metadata_sha256"] == digest(metadata_path),
            step,
            f"narration cache metadata mismatch: {identifier}",
        )
        probe_mp3(context, payload, f"render.audio.{identifier}.probe-source")
        inputs.append(
            {
                "chapter": chapter,
                "payload": payload,
                "identity": {
                    **identity,
                    **{key: row[key] for key in ("characters", "cache_key", "provider_request_sha256", "format")},
                },
            }
        )
    return receipt, inputs


def render(context: dict[str, Any]) -> None:
    step = "render.preflight"
    root = context["artifact_root"]
    _, ordered_inputs = narration_inputs(context)
    final = root / "final.mp4"
    receipt_path = root / "render.json"
    failure_path = root / "render-failure.json"
    work = root / "render-work"
    require(
        not final.exists() and not receipt_path.exists() and not failure_path.exists() and not work.exists(),
        step,
        "render outputs are not pristine",
    )
    run_checked(
        [str(context["ffmpeg"]), "-hide_banner", "-h", "filter=silenceremove"], "render.capability.silenceremove"
    )
    scenes: list[dict[str, Any]] = []
    for index, bound in enumerate(ordered_inputs, start=1):
        chapter = bound["chapter"]
        trimmed_audio = work / f"{index:03d}-{chapter['id']}.wav"
        audio_duration = trim_audio(context, bound["payload"], trimmed_audio, chapter["id"])
        duration = max(
            chapter["visual"]["minimum_duration_seconds"], audio_duration + context["render"]["tail_seconds"]
        )
        scene_path = work / f"{index:03d}-{chapter['id']}.mp4"
        render_scene(context, chapter, trimmed_audio, duration, scene_path)
        scenes.append(
            {
                "id": chapter["id"],
                "path": str(scene_path),
                "sha256": digest(scene_path),
                "bytes": scene_path.stat().st_size,
                "duration_seconds": media_duration(context, scene_path, f"render.scene.{chapter['id']}.probe"),
                "trimmed_audio": {
                    "path": str(trimmed_audio),
                    "sha256": digest(trimmed_audio),
                    "bytes": trimmed_audio.stat().st_size,
                },
            }
        )
    concat_path = work / "concat.txt"
    concat_payload = "".join(f"file '{item['path'].replace(chr(39), chr(92) + chr(39))}'\n" for item in scenes)
    write_bytes_once(concat_path, concat_payload.encode("utf-8"), "render.concat-list")
    temporary = temporary_output(final)
    try:
        run_checked(
            [
                str(context["ffmpeg"]),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(temporary),
            ],
            "render.concat",
        )
        promote_output(temporary, final, "render.concat")
    finally:
        temporary.unlink(missing_ok=True)
    identity = ffprobe_json(context, final, "render.probe-final")
    write_json_once(
        receipt_path,
        {
            "schema_version": 1,
            "status": "pass",
            "job_sha256": context["job_sha256"],
            "media_manifest_sha256": context["manifest_sha256"],
            "narration_receipt_sha256": digest(root / "narration.json"),
            "narration_inputs": [bound["identity"] for bound in ordered_inputs],
            "tools": {"ffmpeg": str(context["ffmpeg"]), "ffprobe": str(context["ffprobe"])},
            "artifact": {
                "path": str(final),
                "sha256": digest(final),
                "bytes": final.stat().st_size,
                "duration_seconds": media_duration(context, final, "render.duration"),
            },
            "scenes": scenes,
            "identity": identity,
            "cleanup": [{"actor": "ffmpeg", "status": "closed"}],
        },
        "render.receipt",
    )


def silence_events(stderr: str) -> list[dict[str, float]]:
    starts: list[float] = []
    events: list[dict[str, float]] = []
    for line in stderr.splitlines():
        start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if start:
            starts.append(float(start.group(1)))
        end = re.search(r"silence_end:\s*([0-9.]+)\s*\|\s*silence_duration:\s*([0-9.]+)", line)
        if end and starts:
            events.append({"start": starts.pop(0), "end": float(end.group(1)), "duration": float(end.group(2))})
    return events


def qa(context: dict[str, Any]) -> None:
    step = "qa.preflight"
    root = context["artifact_root"]
    final = root / "final.mp4"
    render_receipt_path = root / "render.json"
    render_receipt = read_json(render_receipt_path, step)
    require(
        final.is_file() and render_receipt.get("artifact", {}).get("sha256") == digest(final),
        step,
        "render artifact binding mismatch",
    )
    receipt_path = root / "qa-mechanical.json"
    contact_sheet = root / "contact-sheet.png"
    failure_path = root / "qa-failure.json"
    require(
        not receipt_path.exists() and not contact_sheet.exists() and not failure_path.exists(),
        step,
        "QA outputs are not pristine",
    )
    identity = ffprobe_json(context, final, "qa.probe")
    run_checked(
        [str(context["ffmpeg"]), "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(final), "-f", "null", "-"],
        "qa.decode",
    )
    silence = run_checked(
        [
            str(context["ffmpeg"]),
            "-hide_banner",
            "-nostdin",
            "-i",
            str(final),
            "-af",
            f"silencedetect=n={context['render']['silence_db']}dB:d=0.15",
            "-f",
            "null",
            "-",
        ],
        "qa.silence",
        capture_stderr=True,
    )
    events = silence_events(silence.stderr)
    boundaries: list[float] = []
    total = 0.0
    for scene in render_receipt.get("scenes", [])[:-1]:
        total += float(scene["duration_seconds"])
        boundaries.append(total)
    maximum = context["qa"]["max_boundary_silence_seconds"]
    final_duration = media_duration(context, final, "qa.duration")
    violations = [
        event
        for event in events
        if event["duration"] > maximum
        and (
            event["start"] <= 0.05
            or event["end"] >= final_duration - 0.1
            or any(event["start"] <= boundary <= event["end"] for boundary in boundaries)
        )
    ]
    require(not violations, "qa.silence-boundaries", "scene boundary silence exceeds the configured maximum")
    columns = context["qa"]["contact_sheet_columns"]
    rows = context["qa"]["contact_sheet_rows"]
    interval = context["qa"]["sample_interval_seconds"]
    temporary = temporary_output(contact_sheet)
    try:
        run_checked(
            [
                str(context["ffmpeg"]),
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(final),
                "-vf",
                f"fps=1/{interval},scale={context['render']['width'] // columns}:-2,tile={columns}x{rows}",
                "-frames:v",
                "1",
                str(temporary),
            ],
            "qa.contact-sheet",
        )
        promote_output(temporary, contact_sheet, "qa.contact-sheet")
    finally:
        temporary.unlink(missing_ok=True)
    write_json_once(
        receipt_path,
        {
            "schema_version": 1,
            "status": "pass",
            "job_sha256": context["job_sha256"],
            "media_manifest_sha256": context["manifest_sha256"],
            "render_receipt_sha256": digest(render_receipt_path),
            "tools": {"ffmpeg": str(context["ffmpeg"]), "ffprobe": str(context["ffprobe"])},
            "artifact": {
                "path": str(final),
                "sha256": digest(final),
                "bytes": final.stat().st_size,
                "duration_seconds": final_duration,
            },
            "identity": identity,
            "full_decode": "pass",
            "silence_events": events,
            "scene_boundaries_seconds": boundaries,
            "boundary_silence_violations": [],
            "contact_sheet": {
                "path": str(contact_sheet),
                "sha256": digest(contact_sheet),
                "bytes": contact_sheet.stat().st_size,
            },
            "cleanup": [{"actor": "ffmpeg", "status": "closed"}],
        },
        "qa.receipt",
    )

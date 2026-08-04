#!/usr/bin/env python3
"""Content-addressed ElevenLabs narration for the walkthrough media pipeline."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from media_common import (
    approval_receipt,
    copy_once,
    credential_preflight,
    read_credential,
    write_bytes_once,
    write_json_once,
)
from media_manifest import MediaContractError, digest, object_digest, require


def cache_key(context: dict[str, Any], chapter: dict[str, Any]) -> str:
    return object_digest(
        {
            "text": chapter["text"],
            "voice_id": context["narration"]["voice_id"],
            "model_id": context["narration"]["model_id"],
            "settings": context["narration"]["settings"],
        }
    )


def provider_audio(context: dict[str, Any], chapter: dict[str, Any]) -> bytes:
    step = f"narration.chapter.{chapter['id']}"
    api_key = read_credential(context)
    try:
        voice_id = urllib.parse.quote(context["narration"]["voice_id"], safe="")
        request = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            data=json.dumps(
                {
                    "text": chapter["text"],
                    "model_id": context["narration"]["model_id"],
                    "voice_settings": context["narration"]["settings"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                status = response.status
                payload = response.read(25 * 1024 * 1024 + 1)
                content_type = response.headers.get_content_type()
        except urllib.error.HTTPError as exc:
            raise MediaContractError(
                step, f"provider response status {exc.code}"
            ) from exc
        except urllib.error.URLError as exc:
            raise MediaContractError(step, "provider request failed") from exc
        require(status == 200, step, f"provider response status {status}")
        require(
            content_type.startswith("audio/"), step, "provider response is not audio"
        )
        require(
            128 <= len(payload) <= 25 * 1024 * 1024,
            step,
            "provider audio size is invalid",
        )
        return payload
    finally:
        api_key = ""


def narration(context: dict[str, Any], approval_path: Path) -> None:
    step = "narration.preflight"
    require(
        context["job"].get("narration", {}).get("mode") == "elevenlabs",
        step,
        "job narration mode must be elevenlabs",
    )
    approval = approval_receipt(approval_path, context)
    credential_summary = credential_preflight(context)
    root = context["artifact_root"]
    output_receipt = root / "narration.json"
    failure_receipt = root / "narration-failure.json"
    require(
        not output_receipt.exists()
        and not failure_receipt.exists()
        and not (root / "audio").exists(),
        step,
        "narration outputs are not pristine",
    )
    results: list[dict[str, Any]] = []
    cache_hits = 0
    for chapter in context["chapters"]:
        key = cache_key(context, chapter)
        cached = context["cache_dir"] / f"{key}.mp3"
        output = root / "audio" / f"{chapter['id']}.mp3"
        was_cached = (
            cached.is_file()
            and not cached.is_symlink()
            and cached.stat().st_size >= 128
        )
        if was_cached:
            cache_hits += 1
        else:
            require(
                not cached.exists(),
                f"narration.chapter.{chapter['id']}",
                "narration cache path is invalid",
            )
            write_bytes_once(
                cached,
                provider_audio(context, chapter),
                f"narration.chapter.{chapter['id']}",
            )
        copy_once(cached, output, f"narration.chapter.{chapter['id']}.output")
        results.append(
            {
                "id": chapter["id"],
                "path": str(output),
                "sha256": digest(output),
                "bytes": output.stat().st_size,
                "characters": len(chapter["text"]),
                "cache_key": key,
                "cache_hit": was_cached,
            }
        )
    receipt = {
        "schema_version": 1,
        "status": "pass",
        "job_path": str(context["job_path"]),
        "job_sha256": context["job_sha256"],
        "media_manifest": {
            "path": str(context["manifest_path"]),
            "sha256": context["manifest_sha256"],
        },
        "script_sha256": context["script_sha256"],
        "settings_sha256": context["settings_sha256"],
        "approval": {
            "path": str(approval_path),
            "sha256": digest(approval_path),
            "characters": approval["characters"],
        },
        "voice": {
            "id": context["narration"]["voice_id"],
            "name": context["narration"]["voice_name"],
            "model": context["narration"]["model_id"],
        },
        "requests": len(results) - cache_hits,
        "cache_hits": cache_hits,
        "characters": context["characters"],
        "credential": credential_summary,
        "chapters": results,
        "cleanup": [{"actor": "elevenlabs", "status": "closed"}],
    }
    write_json_once(output_receipt, receipt, "narration.receipt")

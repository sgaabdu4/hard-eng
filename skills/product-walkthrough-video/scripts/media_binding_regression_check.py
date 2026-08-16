#!/usr/bin/env python3
"""Regression checks for narration cache and render input binding."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

sys.dont_write_bytecode = True

from media_test_fixture import make_media_project
from run_workflow_regression_check import (
    invoke_media,
    require,
    sha256,
    write_json,
)


def artifact_root(job: Path) -> Path:
    return Path(json.loads(job.read_text(encoding="utf-8"))["artifacts"]["root"])


def narrate(base: Path, name: str) -> tuple[Path, Path, Path]:
    job, approval, _ = make_media_project(base, name)
    result = invoke_media(job, "narration", "--approval", str(approval))
    require(result.returncode == 0, f"narration fixture failed: {result.stderr}")
    return job, approval, artifact_root(job)


def render_fails(job: Path, expected: str) -> None:
    result = invoke_media(job, "render")
    require(result.returncode != 0, f"render accepted {expected}")


def narration_receipt(root: Path) -> dict:
    return json.loads((root / "narration.json").read_text(encoding="utf-8"))


def save_narration(root: Path, value: dict) -> None:
    write_json(root / "narration.json", value)


def cache_paths(job: Path) -> tuple[Path, Path]:
    root = job.parent / ".walkthrough-cache" / "narration-v1"
    audio = next(root.glob("*.mp3"))
    return audio, audio.with_suffix(".json")


def case_audio_modified(base: Path) -> None:
    job, _, root = narrate(base, "audio-modified")
    audio = root / "audio" / "welcome.mp3"
    audio.write_bytes(audio.read_bytes() + b"changed")
    render_fails(job, "audio changed after narration receipt")


def case_same_size_replacement(base: Path) -> None:
    job, _, root = narrate(base, "same-size")
    audio = root / "audio" / "welcome.mp3"
    audio.write_bytes(b"X" * audio.stat().st_size)
    render_fails(job, "same-size audio replacement")


def case_audio_symlink(base: Path) -> None:
    job, _, root = narrate(base, "audio-symlink")
    audio = root / "audio" / "welcome.mp3"
    target, _ = cache_paths(job)
    audio.unlink()
    audio.symlink_to(target)
    render_fails(job, "audio symlink")


def case_audio_ancestor_symlink(base: Path) -> None:
    job, _, root = narrate(base, "audio-ancestor-symlink")
    audio_root = root / "audio"
    moved = root / "moved-audio"
    audio_root.rename(moved)
    audio_root.symlink_to(moved, target_is_directory=True)
    render_fails(job, "audio ancestor symlink")


def case_missing_chapter(base: Path) -> None:
    job, _, root = narrate(base, "missing-chapter")
    receipt = narration_receipt(root)
    receipt["chapters"] = []
    save_narration(root, receipt)
    render_fails(job, "missing narration chapter")


def case_duplicate_chapter(base: Path) -> None:
    job, _, root = narrate(base, "duplicate-chapter")
    receipt = narration_receipt(root)
    receipt["chapters"].append(dict(receipt["chapters"][0]))
    save_narration(root, receipt)
    render_fails(job, "duplicate narration chapter")


def case_extra_chapter(base: Path) -> None:
    job, _, root = narrate(base, "extra-chapter")
    (root / "audio" / "extra.mp3").write_bytes(b"extra")
    render_fails(job, "extra chapter audio")


def case_wrong_cache_key(base: Path) -> None:
    job, _, root = narrate(base, "wrong-cache-key")
    receipt = narration_receipt(root)
    receipt["chapters"][0]["cache_key"] = "0" * 64
    save_narration(root, receipt)
    render_fails(job, "wrong cache key")


def case_cache_metadata_mismatch(base: Path) -> None:
    job, approval, _ = make_media_project(base, "cache-metadata-mismatch")
    audio, _ = cache_paths(job)
    audio.write_bytes(audio.read_bytes() + b"tampered")
    result = invoke_media(job, "narration", "--approval", str(approval))
    require(result.returncode != 0, "cache metadata/audio mismatch was reused")


def case_undecodable_mp3(base: Path) -> None:
    job, approval, _ = make_media_project(base, "undecodable")
    audio, metadata_path = cache_paths(job)
    payload = b"undecodable" * 32
    audio.write_bytes(payload)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["audio_sha256"] = hashlib.sha256(payload).hexdigest()
    metadata["bytes"] = len(payload)
    write_json(metadata_path, metadata)
    result = invoke_media(job, "narration", "--approval", str(approval))
    require(result.returncode != 0, "undecodable MP3 cache entry was reused")


def case_valid_cache_zero_calls(base: Path) -> None:
    job, _, root = narrate(base, "valid-cache")
    receipt = narration_receipt(root)
    require(receipt["requests"] == 0 and receipt["cache_hits"] == 1, "valid cache caused a provider call")


def case_valid_render_binding(base: Path) -> None:
    job, _, root = narrate(base, "valid-render")
    result = invoke_media(job, "render")
    require(result.returncode == 0, f"valid render failed: {result.stderr}")
    receipt_path = root / "render.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    source = narration_receipt(root)["chapters"][0]
    inputs = receipt.get("narration_inputs", [])
    require(
        receipt.get("narration_receipt_sha256") == sha256(root / "narration.json")
        and len(inputs) == 1
        and inputs[0]["path"] == source["path"]
        and inputs[0]["sha256"] == source["sha256"]
        and inputs[0]["bytes"] == source["bytes"]
        and inputs[0]["cache_key"] == source["cache_key"],
        "render receipt omitted ordered narration byte binding",
    )


CASES: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("audio-modified", case_audio_modified),
    ("same-size-replacement", case_same_size_replacement),
    ("audio-symlink", case_audio_symlink),
    ("audio-ancestor-symlink", case_audio_ancestor_symlink),
    ("missing-chapter", case_missing_chapter),
    ("duplicate-chapter", case_duplicate_chapter),
    ("extra-chapter", case_extra_chapter),
    ("wrong-cache-key", case_wrong_cache_key),
    ("cache-metadata-mismatch", case_cache_metadata_mismatch),
    ("undecodable-mp3", case_undecodable_mp3),
    ("valid-cache-zero-calls", case_valid_cache_zero_calls),
    ("valid-render-binding", case_valid_render_binding),
)


def main() -> int:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="media-binding-") as raw:
        base = Path(raw).resolve()
        for name, check in CASES:
            try:
                check(base)
            except (AssertionError, OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append(f"{name}: {exc}")
    if failures:
        for failure in failures:
            print(f"media-binding-regression: FAIL | {failure}", file=sys.stderr)
        return 1
    print(f"media-binding-regression: PASS | checks={len(CASES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

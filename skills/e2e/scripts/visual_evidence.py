#!/usr/bin/env python3
"""Validate E2E evidence composition, media provenance, and review receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Callable

STATUSES = {"PASS", "FAIL", "NOT_REVIEWED", "N/A"}
CLASSES = ("automated", "persisted_state", "deployment", "visual")
BINDINGS = ("revision", "environment", "scenario_id", "run_id", "attempt_id")
LAYOUT_FIELDS = ("overflow", "clipping", "spacing", "responsive")
MAX_SAMPLE_GAP_SECONDS = 10.0


class EvidenceError(RuntimeError):
    """Raised when media cannot be mechanically verified."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_media(path: Path, kind: str) -> dict:
    ffprobe = shutil.which("ffprobe")
    ffmpeg = shutil.which("ffmpeg")
    if not ffprobe or not ffmpeg:
        raise EvidenceError("ffprobe and ffmpeg are required to decode visual evidence")
    decoded = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if decoded.returncode:
        raise EvidenceError(f"media decode failed: {path}")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode:
        raise EvidenceError(f"media probe failed: {path}")
    try:
        payload = json.loads(result.stdout)
        video_stream = next(
            stream
            for stream in payload.get("streams", [])
            if stream.get("codec_type") == "video"
        )
        duration = (
            float(payload.get("format", {}).get("duration", 0))
            if kind == "video"
            else None
        )
        return {
            "duration_seconds": duration,
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
        }
    except (
        KeyError,
        StopIteration,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as exc:
        raise EvidenceError(f"media metadata invalid: {path}") from exc


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def number(value: object) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def resolve_media(repo: Path, value: object) -> Path:
    if not nonempty(value):
        raise EvidenceError("artifact path is required")
    path = Path(str(value)).expanduser()
    resolved = (repo / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_file():
        raise EvidenceError(f"artifact missing or unreadable: {value}")
    return resolved


def validate_timeline(
    review: dict, duration: float, failures: list[str], prefix: str
) -> None:
    timeline = review.get("timeline")
    if not isinstance(timeline, dict):
        failures.append(f"{prefix}.timeline is required")
        return
    if (
        timeline.get("coverage") != "complete"
        or timeline.get("continuous_playback") is not True
    ):
        failures.append(
            f"{prefix}.timeline must declare complete continuous inspection"
        )
    start = timeline.get("start")
    final = timeline.get("final")
    samples = timeline.get("samples")
    if (
        not isinstance(start, dict)
        or not number(start.get("timestamp_seconds"))
        or not nonempty(start.get("observed"))
    ):
        failures.append(f"{prefix}.timeline.start requires timestamp + observation")
    elif abs(float(start["timestamp_seconds"])) > 0.25:
        failures.append(f"{prefix}.timeline.start must bind media start")
    if (
        not isinstance(final, dict)
        or not number(final.get("timestamp_seconds"))
        or not nonempty(final.get("observed"))
    ):
        failures.append(f"{prefix}.timeline.final requires timestamp + observation")
    elif abs(float(final["timestamp_seconds"]) - duration) > 0.25:
        failures.append(f"{prefix}.timeline.final must bind media end")
    if not isinstance(samples, list) or not samples:
        failures.append(f"{prefix}.timeline.samples are required")
        return
    timestamps: list[float] = []
    for index, sample in enumerate(samples):
        if (
            not isinstance(sample, dict)
            or not number(sample.get("timestamp_seconds"))
            or not nonempty(sample.get("observed"))
        ):
            failures.append(
                f"{prefix}.timeline.samples[{index}] requires timestamp + observation"
            )
            continue
        timestamps.append(float(sample["timestamp_seconds"]))
    if not timestamps:
        return
    timestamps.sort()
    if timestamps[0] < 0 or timestamps[-1] > duration:
        failures.append(f"{prefix}.timeline samples must remain inside media")
    if timestamps[0] > 0.25 or abs(timestamps[-1] - duration) > 0.25:
        failures.append(f"{prefix}.timeline samples must cover media start + end")
    if any(
        right - left > MAX_SAMPLE_GAP_SECONDS
        for left, right in zip(timestamps, timestamps[1:])
    ):
        failures.append(
            f"{prefix}.timeline sample gap exceeds {MAX_SAMPLE_GAP_SECONDS:g}s"
        )


def validate_artifact_review(
    artifact: dict,
    review: object,
    duration: float | None,
    failures: list[str],
    prefix: str,
) -> None:
    if not isinstance(review, dict):
        failures.append(f"{prefix}.review is required")
        return
    if review.get("artifact_sha256") != artifact.get("sha256"):
        failures.append(f"{prefix}.review digest binding mismatch")
    if review.get("conclusion") not in {"PASS", "FAIL"}:
        failures.append(f"{prefix}.review conclusion must be PASS or FAIL")
    required_ids = artifact.get("required_step_ids")
    steps = review.get("required_steps")
    if (
        not isinstance(required_ids, list)
        or not required_ids
        or not all(nonempty(item) for item in required_ids)
    ):
        failures.append(f"{prefix}.required_step_ids are required")
        required_ids = []
    elif len(required_ids) != len(set(required_ids)):
        failures.append(f"{prefix}.required_step_ids must be unique")
    if not isinstance(steps, list):
        failures.append(f"{prefix}.review required_steps are required")
        steps = []
    observed_ids: list[str] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not nonempty(step.get("id")):
            failures.append(f"{prefix}.review.required_steps[{index}] requires id")
            continue
        observed_ids.append(step["id"])
        if not nonempty(step.get("description")):
            failures.append(
                f"{prefix}.review.required_steps[{index}] requires visible description"
            )
        if step.get("artifact_sha256") != artifact.get("sha256"):
            failures.append(f"{prefix}.review.required_steps[{index}] digest mismatch")
        if not number(step.get("timestamp_seconds")) and not nonempty(
            step.get("frame")
        ):
            failures.append(
                f"{prefix}.review.required_steps[{index}] requires timestamp or frame"
            )
        if (
            number(step.get("timestamp_seconds"))
            and duration is not None
            and not 0 <= float(step["timestamp_seconds"]) <= duration
        ):
            failures.append(
                f"{prefix}.review.required_steps[{index}] timestamp is outside media"
            )
    if sorted(observed_ids) != sorted(required_ids):
        failures.append(f"{prefix}.review required-step accounting is incomplete")
    for field in ("authentication_or_error_screens", "irrelevant_or_stalled_sections"):
        if not isinstance(review.get(field), list):
            failures.append(f"{prefix}.review.{field} must be recorded")
    layout = review.get("layout_findings")
    if not isinstance(layout, dict) or any(
        not isinstance(layout.get(field), list) for field in LAYOUT_FIELDS
    ):
        failures.append(
            f"{prefix}.review.layout_findings requires overflow/clipping/spacing/responsive lists"
        )
    if artifact.get("kind") == "video" and duration is not None:
        validate_timeline(review, duration, failures, f"{prefix}.review")
    elif not nonempty(review.get("observed_start_state")) or not nonempty(
        review.get("observed_final_state")
    ):
        failures.append(f"{prefix}.review requires observed start + final states")


def validate_visual(
    visual: dict,
    binding: dict,
    repo: Path,
    media_checker: Callable[[Path, str], dict],
    failures: list[str],
) -> None:
    required = visual.get("required") is True
    requested = visual.get("requested") is True
    produced = visual.get("produced") is True
    artifacts = visual.get("artifacts")
    if (requested or produced or artifacts) and not required:
        failures.append("visual evidence requested/produced but not required")
    if required and (not produced or not isinstance(artifacts, list) or not artifacts):
        failures.append("required visual artifact is missing")
        return
    if not isinstance(artifacts, list):
        artifacts = []
    review = visual.get("review")
    status = visual.get("status")
    if status in {"PASS", "FAIL"}:
        if (
            not isinstance(review, dict)
            or review.get("method") != "actual-media-inspection"
        ):
            failures.append("visual review must record actual-media-inspection")
            artifact_reviews = []
        else:
            artifact_reviews = review.get("artifacts", [])
            if not isinstance(artifact_reviews, list):
                failures.append("visual review artifacts must be a list")
                artifact_reviews = []
            if review.get("conclusion") != status:
                failures.append("visual review conclusion must match visual status")
    else:
        artifact_reviews = []
    reviews_by_digest = {
        item.get("artifact_sha256"): item
        for item in artifact_reviews
        if isinstance(item, dict) and nonempty(item.get("artifact_sha256"))
    }
    if status in {"PASS", "FAIL"} and (
        len(artifact_reviews) != len(reviews_by_digest)
        or len(reviews_by_digest) != len(artifacts)
    ):
        failures.append("every visual artifact requires exactly one bound review")
    for index, artifact in enumerate(artifacts):
        prefix = f"visual.artifacts[{index}]"
        if not isinstance(artifact, dict):
            failures.append(f"{prefix} must be an object")
            continue
        for field in BINDINGS:
            if artifact.get(field) != binding.get(field):
                failures.append(f"{prefix}.{field} binding mismatch")
        if artifact.get("successful_test_attempt") is not True:
            failures.append(f"{prefix} is not bound to a successful attempt")
        kind = artifact.get("kind")
        if kind not in {"video", "screenshot"}:
            failures.append(f"{prefix}.kind must be video or screenshot")
            continue
        try:
            path = resolve_media(repo, artifact.get("path"))
            actual_digest = sha256(path)
            if actual_digest != artifact.get("sha256"):
                failures.append(f"{prefix}.sha256 mismatch")
            probed = media_checker(path, kind)
        except (EvidenceError, OSError, subprocess.SubprocessError) as exc:
            failures.append(f"{prefix}: {exc}")
            continue
        dimensions = artifact.get("dimensions")
        if (
            not isinstance(dimensions, dict)
            or dimensions.get("width") != probed["width"]
            or dimensions.get("height") != probed["height"]
        ):
            failures.append(f"{prefix}.dimensions mismatch")
        duration = probed.get("duration_seconds")
        if kind == "video" and (
            not number(artifact.get("duration_seconds"))
            or abs(float(artifact["duration_seconds"]) - duration) > 0.25
        ):
            failures.append(f"{prefix}.duration_seconds mismatch")
        if not nonempty(artifact.get("device")) and not isinstance(
            artifact.get("viewport"), dict
        ):
            failures.append(f"{prefix} requires device or viewport")
        if status in {"PASS", "FAIL"}:
            artifact_review = reviews_by_digest.get(artifact.get("sha256"))
            if (
                isinstance(artifact_review, dict)
                and artifact_review.get("conclusion") != status
            ):
                failures.append(f"{prefix}.review conclusion must match visual status")
            validate_artifact_review(
                artifact, artifact_review, duration, failures, prefix
            )


def evaluate_receipt(
    receipt: dict,
    repo: Path,
    media_checker: Callable[[Path, str], dict] = probe_media,
) -> dict:
    failures: list[str] = []
    concerns: list[str] = []
    if receipt.get("schema_version") != 1:
        failures.append("schema_version must be 1")
    binding = receipt.get("binding")
    if not isinstance(binding, dict) or any(
        not nonempty(binding.get(field)) for field in BINDINGS
    ):
        failures.append("binding requires revision/environment/scenario/run/attempt")
        binding = binding if isinstance(binding, dict) else {}
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict):
        evidence = {}
        failures.append("all evidence classes are required")
    statuses: list[str] = []
    for name in CLASSES:
        item = evidence.get(name)
        if not isinstance(item, dict):
            failures.append(f"evidence.{name} is required")
            continue
        status = item.get("status")
        required = item.get("required")
        if status not in STATUSES or not isinstance(required, bool):
            failures.append(f"evidence.{name} requires valid required + status")
            continue
        if required and status == "N/A" or not required and status != "N/A":
            failures.append(f"evidence.{name} required/status mismatch")
        if required:
            statuses.append(status)
        if name != "visual" and status == "PASS" and not nonempty(item.get("proof")):
            failures.append(f"evidence.{name}.proof is required for PASS")
        if (
            name == "automated"
            and required
            and item.get("attempt_id") != binding.get("attempt_id")
        ):
            failures.append("automated attempt binding mismatch")
    visual = evidence.get("visual")
    if isinstance(visual, dict):
        validate_visual(visual, binding, repo, media_checker, failures)
    if failures or "FAIL" in statuses:
        derived = "FAIL"
    elif "NOT_REVIEWED" in statuses:
        derived = "CONCERNS"
    elif statuses and all(status == "PASS" for status in statuses):
        derived = "PASS"
    else:
        derived = "FAIL"
        failures.append("required evidence classes cannot produce PASS")
    claimed = receipt.get("overall_status")
    if claimed != derived:
        message = f"claimed overall_status {claimed!r} conflicts with derived {derived}"
        (concerns if derived == "CONCERNS" else failures).append(message)
    return {"status": derived, "failures": failures, "concerns": concerns}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--repo", default=".")
    args = parser.parse_args()
    try:
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        result = evaluate_receipt(receipt, Path(args.repo).expanduser().resolve())
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {
            "status": "FAIL",
            "failures": [f"missing or invalid review receipt: {exc}"],
            "concerns": [],
        }
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

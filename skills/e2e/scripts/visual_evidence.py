#!/usr/bin/env python3
"""Validate E2E evidence composition, media provenance, and review receipts."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TypeGuard

SCRIPT_DIR = Path(__file__).resolve().parent
BOUNDED_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks/scripts"
if str(BOUNDED_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(BOUNDED_SCRIPTS))

from bounded_run import run_captured

STATUSES = {"PASS", "FAIL", "NOT_REVIEWED", "N/A"}
CLASSES = ("automated", "persisted_state", "deployment", "visual")
BINDINGS = ("revision", "environment", "scenario_id", "run_id", "attempt_id")
LAYOUT_FIELDS = ("overflow", "clipping", "spacing", "responsive")
VISUAL_PURPOSES = {"behavior-proof", "new-ui-concept", "existing-ui-prototype", "existing-ui-static-preview"}
EXISTING_UI_PURPOSES = {"existing-ui-prototype", "existing-ui-static-preview"}
PROVENANCE_CLASSES = {"independently_measured", "trusted_system_readback", "caller_asserted"}
PASS_CAPABLE_PROVENANCE = {"independently_measured", "trusted_system_readback"}
PROTOTYPE_LABELS = {
    "running-product": "running product",
    "production-component": "production-component prototype",
    "running-product-static-preview": "static preview on current app screen",
}
MAX_SAMPLE_GAP_SECONDS = 10.0
REPOSITORY_SNAPSHOT = re.compile(r"^sha256:[0-9a-f]{64}$")


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
    decoded = run_captured([ffmpeg, "-v", "error", "-i", str(path), "-f", "null", "-"], timeout=600, grace=2)
    if decoded.returncode:
        raise EvidenceError(f"media decode failed: {path}")
    result = run_captured(
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
        timeout=60,
        grace=2,
    )
    if result.returncode:
        raise EvidenceError(f"media probe failed: {path}")
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
        video_stream = next(stream for stream in payload.get("streams", []) if stream.get("codec_type") == "video")
        duration = float(payload.get("format", {}).get("duration", 0)) if kind == "video" else None
        return {
            "duration_seconds": duration,
            "width": int(video_stream["width"]),
            "height": int(video_stream["height"]),
        }
    except (KeyError, StopIteration, TypeError, UnicodeDecodeError, ValueError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"media metadata invalid: {path}") from exc


def nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def string_map(value: object) -> TypeGuard[dict[str, str]]:
    return (
        isinstance(value, dict) and bool(value) and all(nonempty(key) and nonempty(item) for key, item in value.items())
    )


def nonempty_string_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and bool(value) and all(map(nonempty, value))


def number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def validate_field_source(value: object, failures: list[str], prefix: str, *, pass_capable: bool = False) -> None:
    if value not in PROVENANCE_CLASSES:
        failures.append(f"{prefix} must be independently_measured, trusted_system_readback, or caller_asserted")
    elif pass_capable and value not in PASS_CAPABLE_PROVENANCE:
        failures.append(f"{prefix} cannot use caller_asserted evidence for PASS")


def validate_provenance_tree(
    value: object, failures: list[str], prefix: str = "receipt", inherited: str | None = None
) -> None:
    if isinstance(value, dict):
        source = value.get("field_source_class", inherited)
        if source not in PROVENANCE_CLASSES:
            failures.append(f"{prefix} has fields without a provenance class")
            source = None
        for key, item in value.items():
            if key == "field_source_class" or key.endswith("_source"):
                continue
            validate_provenance_tree(item, failures, f"{prefix}.{key}", source)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            validate_provenance_tree(item, failures, f"{prefix}[{index}]", inherited)


def valid_viewport(value: object) -> bool:
    return (
        isinstance(value, dict)
        and number(value.get("width"))
        and float(value["width"]) > 0
        and number(value.get("height"))
        and float(value["height"]) > 0
    )


def validate_proof_target(receipt: dict, failures: list[str]) -> dict:
    target = receipt.get("proof_target")
    if not isinstance(target, dict):
        failures.append("proof_target is required")
        return {}
    if not nonempty(target.get("id")) or not nonempty(target.get("surface")):
        failures.append("proof_target requires id + surface")
    claims = target.get("visible_claims")
    if not string_map(claims):
        failures.append("proof_target.visible_claims requires id-to-description entries")
    forbidden = target.get("forbidden_visible_states")
    if not isinstance(forbidden, list) or not all(nonempty(item) for item in forbidden):
        failures.append("proof_target.forbidden_visible_states must be recorded")
    return target


def resolve_media(repo: Path, value: object) -> Path:
    if not nonempty(value):
        raise EvidenceError("artifact path is required")
    path = Path(str(value)).expanduser()
    resolved = (repo / path).resolve() if not path.is_absolute() else path.resolve()
    if not resolved.is_file():
        raise EvidenceError(f"artifact missing or unreadable: {value}")
    return resolved


def validate_production_sources(prototype: dict, repo: Path, failures: list[str]) -> None:
    sources = prototype.get("production_sources")
    if not isinstance(sources, list) or len(sources) < 2:
        failures.append("prototype.production_sources requires DESIGN.md + production UI owner")
        return
    seen: set[str] = set()
    for index, source in enumerate(sources):
        prefix = f"prototype.production_sources[{index}]"
        if not isinstance(source, dict) or not nonempty(source.get("path")) or not nonempty(source.get("sha256")):
            failures.append(f"{prefix} requires path + sha256")
            continue
        relative = Path(source["path"])
        if relative.is_absolute() or ".." in relative.parts:
            failures.append(f"{prefix}.path must be repository-relative")
            continue
        key = relative.as_posix()
        if key in seen:
            failures.append("prototype.production_sources paths must be unique")
            continue
        seen.add(key)
        try:
            resolved = resolve_media(repo, key)
            if resolved != repo / relative:
                failures.append(f"{prefix}.path must not escape the product repo")
            if sha256(resolved) != source["sha256"]:
                failures.append(f"{prefix}.sha256 mismatch")
        except (EvidenceError, OSError) as exc:
            failures.append(f"{prefix}: {exc}")
    if not sources or not isinstance(sources[0], dict) or sources[0].get("path") != "DESIGN.md":
        failures.append("prototype.production_sources must start with DESIGN.md")


def validate_prototype(
    receipt: dict,
    visual: dict,
    proof_target: dict,
    repo: Path,
    media_checker: Callable[[Path, str], dict],
    failures: list[str],
) -> dict:
    purpose = visual.get("purpose")
    if purpose not in VISUAL_PURPOSES:
        failures.append("visual.purpose must identify the evidence use")
        return {}
    prototype = receipt.get("prototype")
    if purpose == "new-ui-concept":
        if not isinstance(prototype, dict) or prototype.get("surface_kind") != "new":
            failures.append("new UI concept prototype.surface_kind must be new")
        elif not nonempty(prototype.get("new_surface_reason")):
            failures.append("new UI concept requires prototype.new_surface_reason")
        return {}
    if purpose not in EXISTING_UI_PURPOSES:
        return {}
    accepted = receipt.get("accepted_requirements")
    items = accepted.get("items") if isinstance(accepted, dict) else None
    if not isinstance(accepted, dict) or not nonempty(accepted.get("source")) or not string_map(items):
        failures.append("accepted_requirements requires source + id-to-description items")
        items = {}
    claims = proof_target.get("visible_claims")
    if isinstance(claims, dict) and set(items) != set(claims):
        failures.append("proof target must cover every accepted requirement exactly")
    if not isinstance(prototype, dict):
        failures.append("prototype context is required")
        return {}
    if prototype.get("surface_kind") != "existing":
        failures.append("existing UI evidence requires prototype.surface_kind existing")
    validate_production_sources(prototype, repo, failures)
    provenance = prototype.get("render_provenance")
    if not isinstance(provenance, dict):
        failures.append("prototype.render_provenance is required")
        provenance = {}
    kind = provenance.get("kind")
    allowed_kinds = (
        {"running-product-static-preview"}
        if purpose == "existing-ui-static-preview"
        else {"running-product", "production-component"}
    )
    if kind not in allowed_kinds:
        failures.append("existing UI prototype requires product UI or its components")
    expected_label = PROTOTYPE_LABELS.get(kind) if isinstance(kind, str) else None
    if expected_label and provenance.get("presentation_label") != expected_label:
        failures.append("prototype presentation label contradicts render provenance")
    if kind == "production-component":
        try:
            generator = resolve_media(repo, provenance.get("generator_path"))
            if repo not in generator.parents:
                failures.append("prototype generator must belong to the product repo")
            if sha256(generator) != provenance.get("generator_sha256"):
                failures.append("prototype generator sha256 mismatch")
        except (EvidenceError, OSError) as exc:
            failures.append(f"prototype generator: {exc}")
    if purpose == "existing-ui-static-preview" and provenance.get("route") != proof_target.get("surface"):
        failures.append("static preview route must match the exact proof target surface")
    references = prototype.get("reference_artifacts")
    if not isinstance(references, list) or not references:
        failures.append("prototype.reference_artifacts requires a real before screen")
        return {"presentation_label": expected_label, "reference_sha256s": set()}
    reference_digests: set[str] = set()
    delivery_digests = visual.get("delivery_artifact_sha256s")
    output_digests = set(delivery_digests) if nonempty_string_list(delivery_digests) else set()
    for index, reference in enumerate(references):
        prefix = f"prototype.reference_artifacts[{index}]"
        if not isinstance(reference, dict):
            failures.append(f"{prefix} must be an object")
            continue
        if any(not nonempty(reference.get(field)) for field in ("environment", "revision", "surface")):
            failures.append(f"{prefix} requires environment + revision + surface")
        review = reference.get("review")
        if (
            not isinstance(review, dict)
            or review.get("method") != "actual-media-inspection"
            or review.get("conclusion") != "PASS"
            or not nonempty(review.get("observed_subject"))
        ):
            failures.append(f"{prefix}.review requires a PASS actual-media inspection")
        elif review.get("field_source_class") != "independently_measured":
            failures.append(f"{prefix}.review.field_source_class must be independently_measured")
        try:
            path = resolve_media(repo, reference.get("path"))
            digest = sha256(path)
            if digest != reference.get("sha256"):
                failures.append(f"{prefix}.sha256 mismatch")
            if digest in output_digests:
                failures.append(f"{prefix} must be distinct from prototype output")
            reference_digests.add(digest)
            reference_kind = reference.get("kind")
            probed = media_checker(path, reference_kind if isinstance(reference_kind, str) else "")
            if reference_kind != "screenshot":
                failures.append(f"{prefix}.kind must be screenshot")
            if reference.get("dimensions") != {"width": probed["width"], "height": probed["height"]}:
                failures.append(f"{prefix}.dimensions mismatch")
        except (EvidenceError, OSError, ValueError) as exc:
            failures.append(f"{prefix}: {exc}")
    return {"presentation_label": expected_label, "reference_sha256s": reference_digests}


def validate_timeline(review: dict, duration: float, failures: list[str], prefix: str) -> None:
    timeline = review.get("timeline")
    if not isinstance(timeline, dict):
        failures.append(f"{prefix}.timeline is required")
        return
    if timeline.get("coverage") != "complete" or timeline.get("continuous_playback") is not True:
        failures.append(f"{prefix}.timeline must declare complete continuous inspection")
    start = timeline.get("start")
    final = timeline.get("final")
    samples = timeline.get("samples")
    if not isinstance(start, dict) or not number(start.get("timestamp_seconds")) or not nonempty(start.get("observed")):
        failures.append(f"{prefix}.timeline.start requires timestamp + observation")
    elif abs(float(start["timestamp_seconds"])) > 0.25:
        failures.append(f"{prefix}.timeline.start must bind media start")
    if not isinstance(final, dict) or not number(final.get("timestamp_seconds")) or not nonempty(final.get("observed")):
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
            failures.append(f"{prefix}.timeline.samples[{index}] requires timestamp + observation")
            continue
        timestamps.append(float(sample["timestamp_seconds"]))
    if not timestamps:
        return
    timestamps.sort()
    if timestamps[0] < 0 or timestamps[-1] > duration:
        failures.append(f"{prefix}.timeline samples must remain inside media")
    if timestamps[0] > 0.25 or abs(timestamps[-1] - duration) > 0.25:
        failures.append(f"{prefix}.timeline samples must cover media start + end")
    if any(right - left > MAX_SAMPLE_GAP_SECONDS for left, right in itertools.pairwise(timestamps)):
        failures.append(f"{prefix}.timeline sample gap exceeds {MAX_SAMPLE_GAP_SECONDS:g}s")


def validate_artifact_review(
    artifact: dict,
    review: object,
    duration: float | None,
    proof_target: dict,
    prototype: dict,
    failures: list[str],
    prefix: str,
) -> None:
    if not isinstance(review, dict):
        failures.append(f"{prefix}.review is required")
        return
    validate_field_source(
        review.get("field_source_class"),
        failures,
        f"{prefix}.review.field_source_class",
        pass_capable=review.get("conclusion") == "PASS",
    )
    if review.get("artifact_sha256") != artifact.get("sha256"):
        failures.append(f"{prefix}.review digest binding mismatch")
    target_id = proof_target.get("id")
    if review.get("proof_target_id") != target_id:
        failures.append(f"{prefix}.review proof-target binding mismatch")
    if review.get("conclusion") not in {"PASS", "FAIL"}:
        failures.append(f"{prefix}.review conclusion must be PASS or FAIL")
    if not isinstance(review.get("subject_match"), bool):
        failures.append(f"{prefix}.review.subject_match must be recorded")
    elif review.get("conclusion") == "PASS" and review["subject_match"] is not True:
        failures.append(f"{prefix}.review subject does not match proof target")
    if not nonempty(review.get("observed_subject")):
        failures.append(f"{prefix}.review.observed_subject is required")
    if prototype:
        if review.get("requirements_match") is not True:
            failures.append(f"{prefix}.review does not match accepted requirements")
        if review.get("reference_match") is not True:
            failures.append(f"{prefix}.review does not match the real before screen")
        anchors = review.get("preserved_reference_anchors")
        if not nonempty_string_list(anchors):
            failures.append(f"{prefix}.review.preserved_reference_anchors must be recorded")
        reference_sha256s = review.get("reference_sha256s")
        if not nonempty_string_list(reference_sha256s) or set(reference_sha256s) != prototype.get("reference_sha256s"):
            failures.append(f"{prefix}.review reference digest binding mismatch")
        if review.get("presentation_label") != prototype.get("presentation_label"):
            failures.append(f"{prefix}.review presentation label mismatch")
    required_ids = artifact.get("required_step_ids")
    target_claims = proof_target.get("visible_claims")
    claim_ids = set(target_claims) if isinstance(target_claims, dict) else set()
    steps = review.get("required_steps")
    if not nonempty_string_list(required_ids):
        failures.append(f"{prefix}.required_step_ids are required")
        required_ids = []
    elif len(required_ids) != len(set(required_ids)):
        failures.append(f"{prefix}.required_step_ids must be unique")
    elif not set(required_ids).issubset(claim_ids):
        failures.append(f"{prefix}.required_step_ids are outside proof target")
    if not isinstance(steps, list):
        failures.append(f"{prefix}.review required_steps are required")
        steps = []
    observed_ids: list[str] = []
    for index, step in enumerate(steps):
        if not isinstance(step, dict) or not nonempty(step.get("id")):
            failures.append(f"{prefix}.review.required_steps[{index}] requires id")
            continue
        observed_ids.append(step["id"])
        if step.get("artifact_sha256") != artifact.get("sha256"):
            failures.append(f"{prefix}.review.required_steps[{index}] digest mismatch")
        if not number(step.get("timestamp_seconds")) and not nonempty(step.get("frame")):
            failures.append(f"{prefix}.review.required_steps[{index}] requires timestamp or frame")
        if (
            number(step.get("timestamp_seconds"))
            and duration is not None
            and not 0 <= float(step["timestamp_seconds"]) <= duration
        ):
            failures.append(f"{prefix}.review.required_steps[{index}] timestamp is outside media")
    if sorted(observed_ids) != sorted(required_ids):
        failures.append(f"{prefix}.review required-step accounting is incomplete")
    for field in ("authentication_or_error_screens", "irrelevant_or_stalled_sections"):
        if not isinstance(review.get(field), list):
            failures.append(f"{prefix}.review.{field} must be recorded")
    layout = review.get("layout_findings")
    if not isinstance(layout, dict) or any(not isinstance(layout.get(field), list) for field in LAYOUT_FIELDS):
        failures.append(f"{prefix}.review.layout_findings requires overflow/clipping/spacing/responsive lists")
    if artifact.get("kind") == "video" and duration is not None:
        validate_timeline(review, duration, failures, f"{prefix}.review")
    elif not nonempty(review.get("observed_start_state")) or not nonempty(review.get("observed_final_state")):
        failures.append(f"{prefix}.review requires observed start + final states")


def validate_visual(
    visual: dict,
    binding: dict,
    proof_target: dict,
    prototype: dict,
    repo: Path,
    media_checker: Callable[[Path, str], dict],
    failures: list[str],
) -> None:
    required = visual.get("required") is True
    requested = visual.get("requested") is True
    produced = visual.get("produced") is True
    artifacts = visual.get("artifacts")
    if not (required or requested or produced or artifacts):
        return
    if (requested or produced or artifacts) and not required:
        failures.append("visual evidence requested/produced but not required")
    if required and (not produced or not isinstance(artifacts, list) or not artifacts):
        failures.append("required visual artifact is missing")
        return
    if not isinstance(artifacts, list):
        artifacts = []
    delivery_digests = visual.get("delivery_artifact_sha256s")
    if not nonempty_string_list(delivery_digests) or len(delivery_digests) != len(set(delivery_digests)):
        failures.append("visual.delivery_artifact_sha256s requires unique digests")
        delivery_digests = []
    review = visual.get("review")
    status = visual.get("status")
    if status in {"PASS", "FAIL"}:
        if not isinstance(review, dict) or review.get("method") != "actual-media-inspection":
            failures.append("visual review must record actual-media-inspection")
            artifact_reviews = []
        else:
            artifact_reviews = review.get("artifacts", [])
            if not isinstance(artifact_reviews, list):
                failures.append("visual review artifacts must be a list")
                artifact_reviews = []
            if review.get("conclusion") != status:
                failures.append("visual review conclusion must match visual status")
            validate_field_source(
                review.get("field_source_class"),
                failures,
                "visual.review.field_source_class",
                pass_capable=status == "PASS",
            )
    else:
        artifact_reviews = []
    reviews_by_digest = {
        item.get("artifact_sha256"): item
        for item in artifact_reviews
        if isinstance(item, dict) and nonempty(item.get("artifact_sha256"))
    }
    if status in {"PASS", "FAIL"} and (
        len(artifact_reviews) != len(reviews_by_digest) or len(reviews_by_digest) != len(artifacts)
    ):
        failures.append("every visual artifact requires exactly one bound review")
    artifact_digests = {
        item.get("sha256") for item in artifacts if isinstance(item, dict) and nonempty(item.get("sha256"))
    }
    if not set(delivery_digests).issubset(artifact_digests):
        failures.append("visual delivery references an unbound artifact")
    delivered_claims: set[str] = set()
    for index, artifact in enumerate(artifacts):
        prefix = f"visual.artifacts[{index}]"
        if not isinstance(artifact, dict):
            failures.append(f"{prefix} must be an object")
            continue
        for field in BINDINGS:
            if artifact.get(field) != binding.get(field):
                failures.append(f"{prefix}.{field} binding mismatch")
        if artifact.get("proof_target_id") != proof_target.get("id"):
            failures.append(f"{prefix}.proof_target_id binding mismatch")
        if artifact.get("sha256") in delivery_digests:
            required_ids = artifact.get("required_step_ids")
            if isinstance(required_ids, list):
                delivered_claims.update(item for item in required_ids if isinstance(item, str))
        if artifact.get("successful_test_attempt") is not True:
            failures.append(f"{prefix} is not bound to a successful attempt")
        validate_field_source(
            artifact.get("successful_test_attempt_source"),
            failures,
            f"{prefix}.successful_test_attempt_source",
            pass_capable=artifact.get("successful_test_attempt") is True,
        )
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
        except (EvidenceError, OSError, ValueError) as exc:
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
            duration is None
            or not number(artifact.get("duration_seconds"))
            or abs(float(artifact["duration_seconds"]) - duration) > 0.25
        ):
            failures.append(f"{prefix}.duration_seconds mismatch")
        viewport = artifact.get("viewport")
        if viewport is not None and not valid_viewport(viewport):
            failures.append(f"{prefix}.viewport requires positive finite width + height")
        if not nonempty(artifact.get("device")) and not valid_viewport(viewport):
            failures.append(f"{prefix} requires device or viewport")
        if status in {"PASS", "FAIL"}:
            artifact_review = reviews_by_digest.get(artifact.get("sha256"))
            if isinstance(artifact_review, dict) and artifact_review.get("conclusion") != status:
                failures.append(f"{prefix}.review conclusion must match visual status")
            validate_artifact_review(artifact, artifact_review, duration, proof_target, prototype, failures, prefix)
    target_claims = proof_target.get("visible_claims")
    required_claims = set(target_claims) if isinstance(target_claims, dict) else set()
    if delivered_claims != required_claims:
        failures.append("delivered visual artifacts do not cover the proof target")


def evaluate_receipt(receipt: dict, repo: Path, media_checker: Callable[[Path, str], dict] = probe_media) -> dict:
    failures: list[str] = []
    concerns: list[str] = []
    validate_provenance_tree(receipt, failures)
    if receipt.get("schema_version") != 4:
        failures.append("schema_version must be 4")
    binding = receipt.get("binding")
    if not isinstance(binding, dict) or any(not nonempty(binding.get(field)) for field in BINDINGS):
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
        validate_field_source(
            item.get("field_source_class"),
            failures,
            f"evidence.{name}.field_source_class",
            pass_capable=required and status == "PASS",
        )
        if required and status == "N/A" or not required and status != "N/A":
            failures.append(f"evidence.{name} required/status mismatch")
        if required:
            statuses.append(status)
        if name != "visual" and status == "PASS" and not nonempty(item.get("proof")):
            failures.append(f"evidence.{name}.proof is required for PASS")
        if name == "automated" and required and item.get("attempt_id") != binding.get("attempt_id"):
            failures.append("automated attempt binding mismatch")
    visual = evidence.get("visual")
    if isinstance(visual, dict):
        visual_active = bool(
            visual.get("required") is True
            or visual.get("requested") is True
            or visual.get("produced") is True
            or visual.get("artifacts")
        )
        proof_target = validate_proof_target(receipt, failures) if visual_active else {}
        prototype = (
            validate_prototype(receipt, visual, proof_target, repo, media_checker, failures) if visual_active else {}
        )
        validate_visual(visual, binding, proof_target, prototype, repo, media_checker, failures)
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


def parent_provenance(
    receipt: dict,
    repo: Path,
    repository_snapshot: str,
    receipt_path: str,
    media_checker: Callable[[Path, str], dict] = probe_media,
    evaluated: dict | None = None,
) -> dict:
    """Build parent-owned snapshot + visual-proof binding without self-reference."""
    if not REPOSITORY_SNAPSHOT.fullmatch(repository_snapshot):
        raise EvidenceError("repository snapshot binding is invalid")
    result = evaluated or evaluate_receipt(receipt, repo, media_checker)
    if result["status"] != "PASS":
        raise EvidenceError("visual evidence receipt is not PASS")
    binding = receipt["binding"]
    visual = receipt["evidence"]["visual"]
    review = visual["review"]
    return {
        "repository_snapshot_id": repository_snapshot,
        "receipt_path": receipt_path,
        "visual_revision": binding["revision"],
        "environment": binding["environment"],
        "scenario_id": binding["scenario_id"],
        "proof_target_id": receipt["proof_target"]["id"],
        "run_id": binding["run_id"],
        "attempt_id": binding["attempt_id"],
        "successful_test_attempt": all(artifact["successful_test_attempt"] for artifact in visual["artifacts"]),
        "artifact_sha256s": [artifact["sha256"] for artifact in visual["artifacts"]],
        "delivery_artifact_sha256s": visual["delivery_artifact_sha256s"],
        "receipt_status": result["status"],
        "actual_media_inspection": (review["method"] == "actual-media-inspection" and review["conclusion"] == "PASS"),
        "field_provenance": {
            "repository_snapshot_id": "trusted_system_readback",
            "receipt_path": "trusted_system_readback",
            "visual_revision": "trusted_system_readback",
            "environment": "trusted_system_readback",
            "scenario_id": "trusted_system_readback",
            "proof_target_id": "caller_asserted",
            "run_id": "trusted_system_readback",
            "attempt_id": "trusted_system_readback",
            "successful_test_attempt": "independently_measured",
            "artifact_sha256s": "independently_measured",
            "delivery_artifact_sha256s": "independently_measured",
            "receipt_status": "independently_measured",
            "actual_media_inspection": review["field_source_class"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--repository-snapshot")
    args = parser.parse_args()
    try:
        receipt = json.loads(Path(args.receipt).read_text(encoding="utf-8"))
        repo = Path(args.repo).expanduser().resolve()
        result = evaluate_receipt(receipt, repo)
        if args.repository_snapshot and result["status"] == "PASS":
            result["provenance"] = parent_provenance(
                receipt, repo, args.repository_snapshot, args.receipt, evaluated=result
            )
    except (EvidenceError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        result = {"status": "FAIL", "failures": [f"missing or invalid review receipt: {exc}"], "concerns": []}
    print(json.dumps(result, separators=(",", ":"), ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

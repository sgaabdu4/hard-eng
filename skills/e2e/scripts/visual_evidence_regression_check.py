#!/usr/bin/env python3
"""Synthetic regressions for the E2E visual-evidence gate."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from visual_evidence import EvidenceError, evaluate_receipt, parent_provenance, probe_media

ROOT = Path(__file__).resolve().parents[3]


def base_receipt(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    binding = {
        "revision": "revision-1",
        "environment": "test-environment",
        "scenario_id": "scenario-1",
        "run_id": "run-1",
        "attempt_id": "attempt-1",
    }
    proof_target = {
        "id": "visible-result",
        "surface": "example result screen",
        "visible_claims": {
            "step-1": "The first required state is visible.",
            "step-2": "The final required state is visible.",
        },
        "forbidden_visible_states": ["login-only", "loading-only"],
    }
    return {
        "schema_version": 4,
        "field_source_class": "caller_asserted",
        "proof_target": proof_target,
        "binding": binding,
        "evidence": {
            "automated": {
                "field_source_class": "trusted_system_readback",
                "required": True,
                "status": "PASS",
                "attempt_id": "attempt-1",
                "proof": "runner pass",
            },
            "persisted_state": {
                "field_source_class": "trusted_system_readback",
                "required": True,
                "status": "PASS",
                "proof": "state read-back",
            },
            "deployment": {
                "field_source_class": "trusted_system_readback",
                "required": True,
                "status": "PASS",
                "proof": "revision served",
            },
            "visual": {
                "field_source_class": "independently_measured",
                "purpose": "behavior-proof",
                "required": True,
                "requested": True,
                "produced": True,
                "status": "PASS",
                "delivery_artifact_sha256s": [digest],
                "artifacts": [
                    {
                        **binding,
                        "proof_target_id": "visible-result",
                        "kind": "video",
                        "path": str(path),
                        "sha256": digest,
                        "duration_seconds": 12.0,
                        "dimensions": {"width": 1280, "height": 720},
                        "viewport": {"width": 1280, "height": 720},
                        "device": "desktop",
                        "successful_test_attempt": True,
                        "successful_test_attempt_source": "trusted_system_readback",
                        "required_step_ids": ["step-1", "step-2"],
                    }
                ],
                "review": {
                    "field_source_class": "independently_measured",
                    "method": "actual-media-inspection",
                    "conclusion": "PASS",
                    "artifacts": [
                        {
                            "field_source_class": "independently_measured",
                            "artifact_sha256": digest,
                            "proof_target_id": "visible-result",
                            "conclusion": "PASS",
                            "subject_match": True,
                            "observed_subject": "example result screen",
                            "required_steps": [
                                {
                                    "id": "step-1",
                                    "description": "first visible step",
                                    "artifact_sha256": digest,
                                    "timestamp_seconds": 2.0,
                                },
                                {
                                    "id": "step-2",
                                    "description": "final visible step",
                                    "artifact_sha256": digest,
                                    "timestamp_seconds": 10.0,
                                },
                            ],
                            "timeline": {
                                "coverage": "complete",
                                "continuous_playback": True,
                                "start": {
                                    "timestamp_seconds": 0.0,
                                    "observed": "initial state",
                                },
                                "final": {
                                    "timestamp_seconds": 12.0,
                                    "observed": "final state",
                                },
                                "samples": [
                                    {
                                        "timestamp_seconds": 0.0,
                                        "observed": "initial state",
                                    },
                                    {
                                        "timestamp_seconds": 6.0,
                                        "observed": "transition",
                                    },
                                    {
                                        "timestamp_seconds": 12.0,
                                        "observed": "final state",
                                    },
                                ],
                            },
                            "authentication_or_error_screens": [],
                            "irrelevant_or_stalled_sections": [],
                            "layout_findings": {
                                "overflow": [],
                                "clipping": [],
                                "spacing": [],
                                "responsive": [],
                            },
                        }
                    ],
                },
            },
        },
        "overall_status": "PASS",
    }


def existing_ui_prototype(receipt: dict, reference: Path, generator: Path) -> dict:
    prototype = copy.deepcopy(receipt)
    reference_digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    generator_digest = hashlib.sha256(generator.read_bytes()).hexdigest()
    prototype["accepted_requirements"] = {
        "source": "thread:user-message-1",
        "items": copy.deepcopy(prototype["proof_target"]["visible_claims"]),
    }
    prototype["prototype"] = {
        "render_provenance": {
            "kind": "production-component",
            "presentation_label": "production-component prototype",
            "generator_path": str(generator),
            "generator_sha256": generator_digest,
        },
        "reference_artifacts": [
            {
                "kind": "screenshot",
                "path": str(reference),
                "sha256": reference_digest,
                "environment": "production",
                "revision": "baseline-1",
                "surface": "current example result screen",
                "dimensions": {"width": 1280, "height": 720},
                "review": {
                    "field_source_class": "independently_measured",
                    "method": "actual-media-inspection",
                    "conclusion": "PASS",
                    "observed_subject": "current example result screen",
                },
            }
        ],
    }
    prototype["evidence"]["visual"]["purpose"] = "existing-ui-prototype"
    artifact_review = prototype["evidence"]["visual"]["review"]["artifacts"][0]
    artifact_review.update(
        {
            "requirements_match": True,
            "reference_match": True,
            "reference_sha256s": [reference_digest],
            "preserved_reference_anchors": ["summary", "details", "history"],
            "presentation_label": "production-component prototype",
        }
    )
    return prototype


def fake_probe(_path: Path, _kind: str) -> dict:
    return {"duration_seconds": 12.0, "width": 1280, "height": 720}


def expect(
    receipt: dict, status: str, reason: str, failure: str | None = None
) -> None:
    result = evaluate_receipt(receipt, Path.cwd(), fake_probe)
    if result["status"] != status:
        raise AssertionError(f"{reason}: expected {status}, got {result}")
    if failure and not any(failure in item for item in result["failures"]):
        raise AssertionError(f"{reason}: missing failure {failure!r}: {result}")


def check_template() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "assets/visual-review-receipt.template.json"
    )
    template = json.loads(path.read_text(encoding="utf-8"))
    visual = template.get("evidence", {}).get("visual", {})
    artifacts = visual.get("artifacts", [])
    reviews = visual.get("review", {}).get("artifacts", [])
    if (
        template.get("schema_version") != 4
        or template.get("field_source_class") != "caller_asserted"
        or set(template.get("evidence", {})) != {
            "automated",
            "persisted_state",
            "deployment",
            "visual",
        }
        or not isinstance(template.get("proof_target"), dict)
        or not (
            visual.get("purpose")
            and visual.get("delivery_artifact_sha256s")
            and template.get("accepted_requirements", {}).get("items")
            and template.get("prototype", {}).get("reference_artifacts")
            and artifacts
            and artifacts[0].get("proof_target_id")
            and artifacts[0].get("successful_test_attempt_source")
            == "trusted_system_readback"
            and reviews
            and reviews[0].get("proof_target_id")
            and reviews[0].get("field_source_class") == "independently_measured"
            and reviews[0].get("subject_match") is True
            and reviews[0].get("requirements_match") is True
            and reviews[0].get("reference_match") is True
        )
    ):
        raise AssertionError("visual review template contract is incomplete")


def check_completion_bindings() -> None:
    required = {
        "AGENTS.md": "receipt-listed delivery path/hash",
        "skills/e2e/SKILL.md": "references/visual-evidence.md",
        "skills/e2e/references/visual-evidence.md": "delivery_artifact_sha256s",
        "skills/atomic-ui/SKILL.md": "Existing UI prototype",
        "skills/he-build/references/workflow.md": "canonical `e2e` receipt PASS",
        "skills/he-ship/references/workflow.md": "canonical `e2e` receipt validator PASS",
        "scripts/check-skill-contracts.py": "skills/e2e/scripts/visual_evidence_regression_check.py",
    }
    for relative, anchor in required.items():
        if anchor not in (ROOT / relative).read_text(encoding="utf-8"):
            raise AssertionError(f"completion binding missing: {relative}")


def check_real_decode(directory: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg or not shutil.which("ffprobe"):
        return
    path = directory / "decoded.mp4"
    result = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=64x48:duration=1",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode:
        raise AssertionError("synthetic video generation failed")
    metadata = probe_media(path, "video")
    if (
        metadata["width"] != 64
        or metadata["height"] != 48
        or metadata["duration_seconds"] <= 0
    ):
        raise AssertionError("real media decode/probe contract failed")
    receipt = base_receipt(path)
    artifact = receipt["evidence"]["visual"]["artifacts"][0]
    artifact["duration_seconds"] = metadata["duration_seconds"]
    artifact["dimensions"] = {"width": 64, "height": 48}
    review = receipt["evidence"]["visual"]["review"]["artifacts"][0]
    review["required_steps"][0]["timestamp_seconds"] = 0.2
    review["required_steps"][1]["timestamp_seconds"] = 0.8
    review["timeline"]["final"]["timestamp_seconds"] = metadata["duration_seconds"]
    review["timeline"]["samples"] = [
        {"timestamp_seconds": 0.0, "observed": "initial state"},
        {"timestamp_seconds": metadata["duration_seconds"], "observed": "final state"},
    ]
    evaluated = evaluate_receipt(receipt, Path.cwd())
    if evaluated["status"] != "PASS":
        raise AssertionError(f"real decoded media: {evaluated}")


def main() -> int:
    check_template()
    check_completion_bindings()
    with tempfile.TemporaryDirectory() as temporary:
        check_real_decode(Path(temporary))
        media = Path(temporary) / "evidence.mp4"
        media.write_bytes(b"synthetic-decodable-media")
        complete = base_receipt(media)
        reference = Path(temporary) / "reference.png"
        reference.write_bytes(b"different-synthetic-reference")
        generator = Path(__file__).resolve()
        prototype = existing_ui_prototype(complete, reference, generator)

        missing_reference = copy.deepcopy(prototype)
        missing_reference["prototype"]["reference_artifacts"] = []
        expect(
            missing_reference,
            "FAIL",
            "existing UI prototype without a real baseline",
            "reference_artifacts",
        )

        mocked_as_product = copy.deepcopy(prototype)
        mocked_provenance = mocked_as_product["prototype"]["render_provenance"]
        mocked_provenance["kind"] = "test-harness"
        mocked_provenance["presentation_label"] = "running product"
        expect(
            mocked_as_product,
            "FAIL",
            "test harness presented as the product",
            "product UI or its components",
        )

        outside_repo = copy.deepcopy(prototype)
        outside_generator = Path(temporary) / "custom-prototype.html"
        outside_generator.write_text("<main>custom mock</main>")
        outside_provenance = outside_repo["prototype"]["render_provenance"]
        outside_provenance["generator_path"] = str(outside_generator)
        outside_provenance["generator_sha256"] = hashlib.sha256(
            outside_generator.read_bytes()
        ).hexdigest()
        expect(
            outside_repo,
            "FAIL",
            "custom prototype outside the product repo",
            "must belong to the product repo",
        )

        omitted_requirement = copy.deepcopy(prototype)
        omitted_requirement["accepted_requirements"]["items"][
            "skip-redundant-details"
        ] = "Do not ask for details the sales flow already captured."
        expect(
            omitted_requirement,
            "FAIL",
            "prototype omits accepted completed-lead behavior",
            "cover every accepted requirement",
        )

        requirement_mismatch = copy.deepcopy(prototype)
        requirement_mismatch["evidence"]["visual"]["review"]["artifacts"][0][
            "requirements_match"
        ] = False
        expect(
            requirement_mismatch,
            "FAIL",
            "prototype contradicts accepted flow",
            "accepted requirements",
        )

        removed_existing_sections = copy.deepcopy(prototype)
        removed_existing_sections["evidence"]["visual"]["review"]["artifacts"][0][
            "preserved_reference_anchors"
        ] = []
        expect(
            removed_existing_sections,
            "FAIL",
            "prototype removes current screen sections",
            "preserved_reference_anchors",
        )

        malformed_reference_binding = copy.deepcopy(prototype)
        malformed_reference_binding["evidence"]["visual"]["review"]["artifacts"][
            0
        ]["reference_sha256s"] = None
        expect(
            malformed_reference_binding,
            "FAIL",
            "malformed prototype reference binding",
            "reference digest binding mismatch",
        )

        repository_snapshot = "sha256:" + "a" * 64
        provenance = parent_provenance(
            complete,
            Path.cwd(),
            repository_snapshot,
            "features/example/visual-review-receipt.json",
            fake_probe,
        )
        if (
            provenance["repository_snapshot_id"] != repository_snapshot
            or provenance["visual_revision"] != "revision-1"
            or provenance["visual_revision"] == repository_snapshot
            or provenance["receipt_status"] != "PASS"
            or provenance["actual_media_inspection"] is not True
        ):
            raise AssertionError("parent visual provenance conflated revision + snapshot")

        unreviewed = copy.deepcopy(complete)
        unreviewed["evidence"]["visual"]["status"] = "NOT_REVIEWED"
        unreviewed["evidence"]["visual"].pop("review")
        expect(unreviewed, "CONCERNS", "runner PASS without visual review")

        missing_review = copy.deepcopy(complete)
        missing_review["evidence"]["visual"].pop("review")
        expect(missing_review, "FAIL", "visual PASS without review receipt")

        nonvisual = copy.deepcopy(complete)
        nonvisual.pop("proof_target")
        nonvisual["evidence"]["visual"] = {
            "field_source_class": "caller_asserted",
            "required": False,
            "requested": False,
            "produced": False,
            "status": "N/A",
        }
        expect(nonvisual, "PASS", "nonvisual evidence has no visual target cost")

        wrong_subject = copy.deepcopy(complete)
        wrong_subject_review = wrong_subject["evidence"]["visual"]["review"][
            "artifacts"
        ][0]
        wrong_subject_review["subject_match"] = False
        wrong_subject_review["observed_subject"] = "checkout-only"
        expect(
            wrong_subject,
            "FAIL",
            "valid artifact with wrong visual subject",
            "subject does not match proof target",
        )

        caller_status = copy.deepcopy(complete)
        caller_status["evidence"]["automated"][
            "field_source_class"
        ] = "caller_asserted"
        expect(
            caller_status,
            "FAIL",
            "caller assertion presented as automated proof",
            "cannot use caller_asserted evidence for PASS",
        )

        unclassified_fields = copy.deepcopy(complete)
        unclassified_fields.pop("field_source_class")
        expect(
            unclassified_fields,
            "FAIL",
            "receipt fields without an inherited provenance class",
            "fields without a provenance class",
        )

        caller_review = copy.deepcopy(complete)
        caller_review["evidence"]["visual"]["review"]["artifacts"][0][
            "field_source_class"
        ] = "caller_asserted"
        expect(
            caller_review,
            "FAIL",
            "caller assertion presented as visual inspection",
            "cannot use caller_asserted evidence for PASS",
        )

        wrong_target = copy.deepcopy(complete)
        wrong_target["evidence"]["visual"]["artifacts"][0][
            "proof_target_id"
        ] = "checkout"
        expect(
            wrong_target,
            "FAIL",
            "artifact reused for another proof target",
            "proof_target_id binding mismatch",
        )

        wrong_delivery = copy.deepcopy(complete)
        wrong_delivery["evidence"]["visual"]["delivery_artifact_sha256s"] = [
            "0" * 64
        ]
        expect(
            wrong_delivery,
            "FAIL",
            "final delivery uses an unreviewed artifact",
            "delivery references an unbound artifact",
        )

        login_only = copy.deepcopy(complete)
        login_only["evidence"]["visual"]["status"] = "FAIL"
        login_only["evidence"]["visual"]["review"]["conclusion"] = "FAIL"
        login_review = login_only["evidence"]["visual"]["review"]["artifacts"][0]
        login_review["conclusion"] = "FAIL"
        login_review["authentication_or_error_screens"] = [
            {"timestamp_seconds": 0.0, "observed": "authentication screen throughout"}
        ]
        login_review["required_steps"] = []
        expect(login_only, "FAIL", "PASS manifest with login-only video")

        partial = copy.deepcopy(complete)
        partial["evidence"]["visual"]["status"] = "FAIL"
        partial["evidence"]["visual"]["review"]["conclusion"] = "FAIL"
        partial_review = partial["evidence"]["visual"]["review"]["artifacts"][0]
        partial_review["conclusion"] = "FAIL"
        partial_review["required_steps"] = partial_review["required_steps"][:1]
        expect(partial, "FAIL", "partial target flow")

        stale = copy.deepcopy(complete)
        stale["evidence"]["visual"]["artifacts"][0]["run_id"] = "stale-run"
        expect(stale, "FAIL", "stale video")
        try:
            parent_provenance(
                stale, Path.cwd(), repository_snapshot,
                "features/example/visual-review-receipt.json", fake_probe,
            )
        except EvidenceError:
            pass
        else:
            raise AssertionError("parent provenance accepted stale attempt binding")

        wrong_attempt = copy.deepcopy(complete)
        wrong_attempt["evidence"]["visual"]["artifacts"][0][
            "attempt_id"
        ] = "attempt-0"
        expect(wrong_attempt, "FAIL", "wrong successful attempt")
        try:
            parent_provenance(
                wrong_attempt, Path.cwd(), repository_snapshot,
                "features/example/visual-review-receipt.json", fake_probe,
            )
        except EvidenceError:
            pass
        else:
            raise AssertionError("parent provenance accepted wrong attempt")

        mismatched = copy.deepcopy(complete)
        mismatched["evidence"]["visual"]["artifacts"][0]["sha256"] = "0" * 64
        expect(mismatched, "FAIL", "digest mismatch")
        try:
            parent_provenance(
                mismatched, Path.cwd(), repository_snapshot,
                "features/example/visual-review-receipt.json", fake_probe,
            )
        except EvidenceError:
            pass
        else:
            raise AssertionError("parent provenance accepted digest mismatch")

        missing = copy.deepcopy(complete)
        missing["evidence"]["visual"]["artifacts"][0]["path"] = str(
            Path(temporary) / "missing.mp4"
        )
        expect(missing, "FAIL", "missing requested artifact")

        missing_timestamp = copy.deepcopy(complete)
        missing_timestamp["evidence"]["visual"]["review"]["artifacts"][0][
            "required_steps"
        ][0].pop("timestamp_seconds")
        expect(missing_timestamp, "FAIL", "missing step timestamp")

        contradictory = copy.deepcopy(complete)
        contradictory["evidence"]["visual"]["status"] = "FAIL"
        contradictory["evidence"]["visual"]["review"]["conclusion"] = "FAIL"
        expect(contradictory, "FAIL", "automated PASS plus visual FAIL")

        for viewport in ({}, {"width": 0, "height": 720}, {"width": "1280", "height": 720}):
            malformed_viewport = copy.deepcopy(complete)
            malformed_viewport["evidence"]["visual"]["artifacts"][0]["viewport"] = viewport
            expect(malformed_viewport, "FAIL", "malformed viewport binding")

        expect(complete, "PASS", "complete bound evidence")
    print("visual-evidence-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

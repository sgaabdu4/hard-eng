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

from visual_evidence import evaluate_receipt, probe_media

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
    return {
        "schema_version": 1,
        "binding": binding,
        "evidence": {
            "automated": {
                "required": True,
                "status": "PASS",
                "attempt_id": "attempt-1",
                "proof": "runner pass",
            },
            "persisted_state": {
                "required": True,
                "status": "PASS",
                "proof": "state read-back",
            },
            "deployment": {
                "required": True,
                "status": "PASS",
                "proof": "revision served",
            },
            "visual": {
                "required": True,
                "requested": True,
                "produced": True,
                "status": "PASS",
                "artifacts": [
                    {
                        **binding,
                        "kind": "video",
                        "path": str(path),
                        "sha256": digest,
                        "duration_seconds": 12.0,
                        "dimensions": {"width": 1280, "height": 720},
                        "viewport": {"width": 1280, "height": 720},
                        "device": "desktop",
                        "successful_test_attempt": True,
                        "required_step_ids": ["step-1", "step-2"],
                    }
                ],
                "review": {
                    "method": "actual-media-inspection",
                    "conclusion": "PASS",
                    "artifacts": [
                        {
                            "artifact_sha256": digest,
                            "conclusion": "PASS",
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


def fake_probe(_path: Path, _kind: str) -> dict:
    return {"duration_seconds": 12.0, "width": 1280, "height": 720}


def expect(receipt: dict, status: str, reason: str) -> None:
    result = evaluate_receipt(receipt, Path.cwd(), fake_probe)
    if result["status"] != status:
        raise AssertionError(f"{reason}: expected {status}, got {result}")


def check_template() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "assets/visual-review-receipt.template.json"
    )
    template = json.loads(path.read_text(encoding="utf-8"))
    if template.get("schema_version") != 1 or set(template.get("evidence", {})) != {
        "automated",
        "persisted_state",
        "deployment",
        "visual",
    }:
        raise AssertionError("visual review template contract is incomplete")


def check_completion_bindings() -> None:
    required = {
        "AGENTS.md": "$e2e` actual-media receipt PASS before goal/build/ship/final PASS",
        "skills/e2e/SKILL.md": "references/visual-evidence.md",
        "skills/he-build/references/workflow.md": "canonical `$e2e` receipt PASS",
        "skills/he-ship/references/workflow.md": "canonical `$e2e` receipt validator PASS",
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

        unreviewed = copy.deepcopy(complete)
        unreviewed["evidence"]["visual"]["status"] = "NOT_REVIEWED"
        unreviewed["evidence"]["visual"].pop("review")
        expect(unreviewed, "CONCERNS", "runner PASS without visual review")

        missing_review = copy.deepcopy(complete)
        missing_review["evidence"]["visual"].pop("review")
        expect(missing_review, "FAIL", "visual PASS without review receipt")

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

        mismatched = copy.deepcopy(complete)
        mismatched["evidence"]["visual"]["artifacts"][0]["sha256"] = "0" * 64
        expect(mismatched, "FAIL", "digest mismatch")

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

        expect(complete, "PASS", "complete bound evidence")
    print("visual-evidence-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

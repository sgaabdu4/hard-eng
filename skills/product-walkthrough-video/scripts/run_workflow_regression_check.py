#!/usr/bin/env python3
"""Regression checks for immutable attempts and sanitized phase failures."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

sys.dont_write_bytecode = True

RUNNER = Path(__file__).with_name("run_workflow.py").resolve()
MEDIA_PIPELINE = Path(__file__).with_name("media_pipeline.py").resolve()
SKILL_ROOT = RUNNER.parent.parent
PYTHON = Path(sys.executable).resolve()
PHASES = ("discovery", "scenario", "storyboard", "capture", "render", "qa")
EXPECTED_PACKAGE_FILES = frozenset(
    {
        "SKILL.md",
        "agents/openai.yaml",
        "references/job-contract.md",
        "references/narration-security.md",
        "references/workflow.md",
        "scripts/media_common.py",
        "scripts/media_manifest.py",
        "scripts/media_narration.py",
        "scripts/media_pipeline.py",
        "scripts/media_render.py",
        "scripts/playwright_capture.mjs",
        "scripts/run_workflow.py",
        "scripts/run_workflow_regression_check.py",
    }
)
SAFETY = {
    "data_source": "synthetic-only",
    "allow_production_data": False,
    "allow_client_pii": False,
    "allow_production_credentials": False,
    "allow_production_mutation": False,
    "allow_external_session_links": False,
    "allow_upload": False,
}
SENTINEL = "DO_NOT_COPY_PRIVATE_VALUE_9482"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def git_env() -> dict[str, str]:
    return {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }


def validate_package_inventory() -> None:
    actual = frozenset(
        path.relative_to(SKILL_ROOT).as_posix()
        for path in SKILL_ROOT.rglob("*")
        if path.is_file()
    )
    require(
        actual == EXPECTED_PACKAGE_FILES,
        "package inventory must match thirteen canonical files",
    )


def actor_source() -> str:
    return f"""#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

mode, job_raw, root_raw, phase, evidence_raw = sys.argv[1:]
job = Path(job_raw)
root = Path(root_raw)
evidence = Path(evidence_raw)
root.mkdir(parents=True, exist_ok=True)

if not job.is_file():
    raise SystemExit(8)

if mode == "success":
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text("phase evidence\\n", encoding="utf-8")
    raise SystemExit(0)

if mode == "missing-failure":
    raise SystemExit(9)

failed_media = root / "failed-frame.bin"
failed_media.write_bytes(b"synthetic failed frame")
receipt = {{
    "schema_version": 1,
    "attempt_id": root.name,
    "phase": phase,
    "status": "fail",
    "last_completed_step_id": "open-page.after",
    "failing_step_id": "open-menu.before",
    "error": {{"type": "SyntheticFailure", "message": "bounded redacted failure"}},
    "same_origin_requests": [{{"method": "GET", "path": "/api/example", "status": 200}}],
    "page_errors": [{{"type": "PageError", "message": "bounded page error"}}],
    "console_errors": [{{"type": "ConsoleError", "message": "bounded console error"}}],
    "request_failures": [{{"method": "GET", "path": "/api/failed", "type": "aborted", "message": "bounded request failure"}}],
    "server_logs": ["bounded server line"],
    "cleanup": [{{"actor": "browser", "status": "closed"}}, {{"actor": "server", "status": "stopped"}}],
    "approach_fingerprint": "synthetic local actor + bounded runner",
    "original_violation": "phase exits nonzero",
    "artifacts": [{{
        "path": str(failed_media),
        "sha256": hashlib.sha256(failed_media.read_bytes()).hexdigest(),
        "bytes": failed_media.stat().st_size,
    }}],
}}
if mode == "invalid-failure":
    receipt["stack"] = "{SENTINEL}"
    receipt["same_origin_requests"][0]["path"] = "/api/example?value={SENTINEL}"
(root / f"{{phase}}-failure.json").write_text(json.dumps(receipt), encoding="utf-8")
raise SystemExit(9)
"""


def make_project(base: Path, name: str, actor_mode: str) -> tuple[Path, Path]:
    root = base / name
    root.mkdir(parents=True)
    attempt = root / f"attempt-{name}"
    ledger = root / "coverage.md"
    ledger.write_text(
        "| ID | Capability |\n|---|---|\n| T-01 | Synthetic capability |\n",
        encoding="utf-8",
    )
    scenes = root / "scenes.json"
    write_json(
        scenes,
        {
            "schema_version": 1,
            "scenes": [
                {
                    "id": "scene-1",
                    "coverage_ids": ["T-01"],
                    "chapter": "Synthetic chapter",
                    "route_state": "/example + ready",
                    "target_locator": "role=button[name='Example']",
                    "action": "Open example",
                    "expected_result": "Example is visible",
                    "duration_seconds": 2,
                    "hold_seconds": 0,
                    "camera_target": "example button",
                    "zoom": 1.2,
                    "caption": "Example",
                    "narration": "",
                    "safety_mode": "synthetic-read-only",
                }
            ],
        },
    )
    actor = root / "phase_actor.py"
    actor.write_text(actor_source(), encoding="utf-8")
    job = (root / "job.json").resolve()
    phases: dict[str, Any] = {}
    for phase in PHASES:
        evidence = attempt / "evidence" / f"{phase}.txt"
        phases[phase] = {
            "external_effect": "none",
            "argv": [
                str(PYTHON),
                str(actor),
                actor_mode,
                str(job),
                str(attempt),
                phase,
                str(evidence),
            ],
            "cwd": str(root),
            "evidence": [str(evidence)],
            "timeout_seconds": 10,
        }
    write_json(
        job,
        {
            "schema_version": 1,
            "mode": "preview",
            "project": {"name": f"Synthetic {name}", "root": str(root)},
            "artifacts": {"root": str(attempt), "receipts": str(attempt / "receipts")},
            "coverage_ledger": str(ledger),
            "scene_manifest": str(scenes),
            "required_coverage_ids": ["T-01"],
            "narration": {"mode": "captions-only"},
            "safety": SAFETY,
            "phases": phases,
        },
    )
    return job, attempt


def invoke(job: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), "-B", str(RUNNER), *args, "--job", str(job)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )


def invoke_media(job: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(PYTHON), "-B", str(MEDIA_PIPELINE), *args, "--job", str(job)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=30,
        check=False,
    )


def object_sha256(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fake_media_tool_source(kind: str, *, long_silence: bool) -> str:
    if kind == "ffprobe":
        return """#!/usr/bin/env python3
import json
print(json.dumps({"format": {"duration": "2.0"}, "streams": [{"codec_type": "video", "codec_name": "h264"}, {"codec_type": "audio", "codec_name": "aac"}]}))
"""
    silence_output = (
        "[silencedetect] silence_start: 0.0\\n[silencedetect] silence_end: 0.9 | silence_duration: 0.9\\n"
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


def make_media_project(
    base: Path, name: str, *, long_silence: bool = False
) -> tuple[Path, Path, Path]:
    root = base / name
    root.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=git_env(),
        timeout=10,
        check=True,
    )
    (root / ".gitignore").write_text(
        ".env.local\n.walkthrough-cache/\nartifacts/\n", encoding="utf-8"
    )
    (root / ".env.local").write_text(
        f"ELEVEN_LABS_API_KEY={SENTINEL}\n", encoding="utf-8"
    )
    visual = root / "visual.png"
    visual.write_bytes(b"synthetic visual" * 16)
    ffmpeg = root / "ffmpeg-fixture"
    ffprobe = root / "ffprobe-fixture"
    ffmpeg.write_text(
        fake_media_tool_source("ffmpeg", long_silence=long_silence), encoding="utf-8"
    )
    ffprobe.write_text(
        fake_media_tool_source("ffprobe", long_silence=False), encoding="utf-8"
    )
    ffmpeg.chmod(0o700)
    ffprobe.chmod(0o700)
    text = "A friendly synthetic walkthrough."
    scene_manifest = root / "scenes.json"
    write_json(
        scene_manifest,
        {"schema_version": 1, "scenes": [{"id": "welcome", "narration": text}]},
    )
    settings = {
        "stability": 0.35,
        "similarity_boost": 0.85,
        "style": 0.3,
        "use_speaker_boost": True,
    }
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
                "credential": {
                    "source": "project-env",
                    "path": ".env.local",
                    "variable": "ELEVEN_LABS_API_KEY",
                },
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
            "artifacts": {
                "root": str(artifact_root),
                "receipts": str(artifact_root / "receipts"),
            },
            "scene_manifest": str(scene_manifest),
            "media_manifest": str(media_manifest),
            "narration": {"mode": "elevenlabs"},
        },
    )
    settings_owner = {
        "voice_id": "fixture-voice",
        "model_id": "fixture-model",
        "settings": settings,
    }
    approval = root / "approval.json"
    write_json(
        approval,
        {
            "status": "approved",
            "job_sha256": sha256(job),
            "script_sha256": object_sha256([{"id": "welcome", "text": text}]),
            "settings_sha256": object_sha256(settings_owner),
            "characters": len(text),
            "impact": "zero requests because the fixture cache is warm",
            "user_reply": "approved fixture",
        },
    )
    cache_key = object_sha256(
        {
            "text": text,
            "voice_id": "fixture-voice",
            "model_id": "fixture-model",
            "settings": settings,
        }
    )
    cached = root / ".walkthrough-cache" / "narration-v1" / f"{cache_key}.mp3"
    cached.parent.mkdir(parents=True)
    cached.write_bytes(b"synthetic cached narration" * 16)
    return job, approval, scene_manifest


def phase_receipt(attempt: Path, phase: str = "discovery") -> dict[str, Any]:
    return json.loads(
        (attempt / "receipts" / f"{phase}.json").read_text(encoding="utf-8")
    )


def case_validate_attempt_id(base: Path) -> None:
    job, attempt = make_project(base, "validate", "success")
    result = invoke(job, "validate")
    require(result.returncode == 0, "valid job was rejected")
    payload = json.loads(result.stdout)
    require(
        payload.get("attempt_id") == attempt.name,
        "validation omitted derived attempt ID",
    )


def case_success_receipt_is_immutable(base: Path) -> None:
    job, attempt = make_project(base, "success", "success")
    first = invoke(job, "run", "--phase", "discovery")
    require(first.returncode == 0, "successful phase was rejected")
    receipt_path = attempt / "receipts" / "discovery.json"
    marker_path = attempt / "attempt.json"
    require(
        receipt_path.is_file() and marker_path.is_file(),
        "attempt binding or phase receipt missing",
    )
    receipt = phase_receipt(attempt)
    require(
        receipt.get("attempt_id") == attempt.name, "phase receipt omitted attempt ID"
    )
    before = sha256(receipt_path)
    second = invoke(job, "run", "--phase", "discovery")
    require(second.returncode != 0, "same-attempt phase rerun was accepted")
    require(
        sha256(receipt_path) == before, "same-attempt rerun changed immutable receipt"
    )


def case_stale_phase_job_path_is_rejected(base: Path) -> None:
    job, _ = make_project(base, "stale-phase-job", "success")
    document = json.loads(job.read_text(encoding="utf-8"))
    argv = document["phases"]["discovery"]["argv"]
    argv[argv.index(str(job))] = str(job.with_name("prior-job.json"))
    write_json(job, document)
    result = invoke(job, "validate")
    require(result.returncode != 0, "phase argv accepted a stale job path")
    require(
        "exact current job path" in result.stderr,
        "stale job-path rejection was not explicit",
    )


def case_valid_failure_is_bound(base: Path) -> None:
    job, attempt = make_project(base, "valid-failure", "valid-failure")
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "nonzero actor was reported as pass")
    receipt = phase_receipt(attempt)
    failure = receipt.get("failure_evidence", {})
    require(
        receipt.get("status") == "fail" and receipt.get("exit_code") == 9,
        "failed phase receipt is incomplete",
    )
    require(
        failure.get("status") == "valid",
        "valid sanitized failure evidence was not accepted",
    )
    require(
        failure.get("sha256") == sha256(attempt / "discovery-failure.json"),
        "failure receipt hash mismatch",
    )
    artifacts = failure.get("artifacts", [])
    require(
        len(artifacts) == 1
        and artifacts[0].get("sha256") == sha256(attempt / "failed-frame.bin"),
        "failed artifact hash missing",
    )


def case_missing_failure_gets_runner_receipt(base: Path) -> None:
    job, attempt = make_project(base, "missing-failure", "missing-failure")
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "missing failure evidence was accepted")
    fallback_path = attempt / "discovery-failure.json"
    require(fallback_path.is_file(), "runner did not persist generic failure evidence")
    fallback = json.loads(fallback_path.read_text(encoding="utf-8"))
    require(
        fallback.get("last_completed_step_id") is None,
        "runner fallback invented a completed actor step",
    )
    require(
        fallback.get("failing_step_id") == "discovery.actor",
        "runner fallback omitted the stable actor step",
    )
    require(
        fallback.get("error")
        == {
            "type": "ActorExit",
            "message": "phase actor exited 9 without actor-owned failure evidence",
        },
        "runner fallback error is not bounded and deterministic",
    )
    require(
        fallback.get("cleanup") == [{"actor": "phase-actor", "status": "closed"}],
        "runner fallback cleanup is not explicit",
    )
    receipt = phase_receipt(attempt)
    failure = receipt.get("failure_evidence", {})
    require(
        failure.get("status") == "valid",
        "runner fallback failure evidence was not validated",
    )
    require(
        failure.get("sha256") == sha256(fallback_path),
        "runner fallback hash is not bound",
    )


def case_invalid_failure_is_redacted(base: Path) -> None:
    job, attempt = make_project(base, "invalid-failure", "invalid-failure")
    result = invoke(job, "run", "--phase", "discovery")
    require(result.returncode != 0, "invalid failure evidence was accepted")
    receipt_path = attempt / "receipts" / "discovery.json"
    combined = result.stdout + result.stderr + receipt_path.read_text(encoding="utf-8")
    require(
        SENTINEL not in combined, "invalid failure material leaked into runner output"
    )
    receipt = phase_receipt(attempt)
    require(
        receipt.get("failure_evidence", {}).get("status") == "invalid",
        "invalid failure evidence was not classified",
    )


def case_changed_job_requires_new_attempt(base: Path) -> None:
    job, attempt = make_project(base, "changed-job", "valid-failure")
    first = invoke(job, "run", "--phase", "discovery")
    require(first.returncode != 0, "fixture failure did not fail")
    receipt_path = attempt / "receipts" / "discovery.json"
    before = sha256(receipt_path)
    document = json.loads(job.read_text(encoding="utf-8"))
    document["project"]["name"] = "Changed job bytes"
    write_json(job, document)
    second = invoke(job, "run", "--phase", "discovery")
    require(second.returncode != 0, "changed job reused a bound attempt root")
    require(
        sha256(receipt_path) == before, "changed job altered failed-attempt receipt"
    )


def case_media_pipeline_warm_cache_forward(base: Path) -> None:
    render_source = MEDIA_PIPELINE.with_name("media_render.py").read_text(
        encoding="utf-8"
    )
    require(
        render_source.count("areverse") == 2 and "stop_periods" not in render_source,
        "audio trim does not isolate leading/trailing silence",
    )
    job, approval, scene_manifest = make_media_project(base, "media-forward")
    outputs: list[str] = []
    for arguments in (
        ("validate",),
        ("preflight", "--phase", "narration", "--approval", str(approval)),
        ("narration", "--approval", str(approval)),
        ("render",),
        ("qa",),
    ):
        result = invoke_media(job, *arguments)
        outputs.append(result.stdout + result.stderr)
        require(result.returncode == 0, f"media pipeline failed at {arguments[0]}")
    require(
        SENTINEL not in "".join(outputs), "project credential leaked into media output"
    )
    root = Path(json.loads(job.read_text(encoding="utf-8"))["artifacts"]["root"])
    narration_receipt = json.loads(
        (root / "narration.json").read_text(encoding="utf-8")
    )
    require(
        narration_receipt.get("requests") == 0,
        "warm-cache narration made a provider request",
    )
    require(
        narration_receipt.get("cache_hits") == 1, "warm-cache narration was not reused"
    )
    require((root / "final.mp4").is_file(), "render omitted final media")
    require((root / "qa-mechanical.json").is_file(), "QA omitted its receipt")
    require((root / "contact-sheet.png").is_file(), "QA omitted its contact sheet")
    scenes = json.loads(scene_manifest.read_text(encoding="utf-8"))
    scenes["scenes"][0]["narration"] = "Stale narration"
    write_json(scene_manifest, scenes)
    stale = invoke_media(job, "validate")
    require(stale.returncode != 0, "media manifest accepted stale scene narration")


def case_media_qa_rejects_random_pause(base: Path) -> None:
    job, approval, _ = make_media_project(base, "media-silence", long_silence=True)
    for arguments in (("narration", "--approval", str(approval)), ("render",)):
        result = invoke_media(job, *arguments)
        require(
            result.returncode == 0,
            f"silence fixture failed before QA at {arguments[0]}",
        )
    qa_result = invoke_media(job, "qa")
    require(qa_result.returncode != 0, "QA accepted an excessive leading pause")
    root = Path(json.loads(job.read_text(encoding="utf-8"))["artifacts"]["root"])
    failure = json.loads((root / "qa-failure.json").read_text(encoding="utf-8"))
    require(
        failure.get("failing_step_id") == "qa.silence-boundaries",
        "QA failure omitted its silence boundary",
    )
    require(
        not (root / "qa-mechanical.json").exists(), "failed QA wrote a success receipt"
    )


CASES: tuple[tuple[str, Callable[[Path], None]], ...] = (
    ("validate-attempt-id", case_validate_attempt_id),
    ("success-receipt-immutable", case_success_receipt_is_immutable),
    ("stale-phase-job-rejected", case_stale_phase_job_path_is_rejected),
    ("valid-failure-bound", case_valid_failure_is_bound),
    ("missing-failure-fallback-bound", case_missing_failure_gets_runner_receipt),
    ("invalid-failure-redacted", case_invalid_failure_is_redacted),
    ("changed-job-new-attempt", case_changed_job_requires_new_attempt),
    ("media-pipeline-warm-cache-forward", case_media_pipeline_warm_cache_forward),
    ("media-qa-rejects-random-pause", case_media_qa_rejects_random_pause),
)


def main() -> int:
    validate_package_inventory()
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=[name for name, _ in CASES])
    args = parser.parse_args()
    selected = [item for item in CASES if args.case is None or item[0] == args.case]
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="product-walkthrough-runner-") as raw:
        base = Path(raw)
        for name, check in selected:
            try:
                check(base)
            except (
                AssertionError,
                OSError,
                ValueError,
                subprocess.SubprocessError,
                json.JSONDecodeError,
            ) as exc:
                failures.append(f"{name}: {exc}")
    if failures:
        for failure in failures:
            print(f"run-workflow-regression: FAIL | {failure}", file=sys.stderr)
        return 1
    print(f"run-workflow-regression: PASS | checks={len(selected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

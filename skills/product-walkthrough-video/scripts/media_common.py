#!/usr/bin/env python3
"""Shared immutable-output, credential, and failure helpers for walkthrough media."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from media_manifest import MediaContractError, read_bytes_no_follow, read_json, reject_symlink_components, require

DETERMINISTIC_SCRIPTS = Path(__file__).resolve().parents[2] / "deterministic-checks" / "scripts"
if str(DETERMINISTIC_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DETERMINISTIC_SCRIPTS))

from bounded_run import run_captured

ALLOWED_ENVIRONMENT = ("HOME", "LANG", "LC_ALL", "PATH", "TMPDIR", "TZ")


def write_json_once(path: Path, value: dict[str, Any], step: str) -> None:
    require(not path.exists(), step, f"refusing to overwrite immutable output: {path}")
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    write_bytes_once(path, payload, step)


def write_bytes_once(path: Path, payload: bytes, step: str) -> None:
    reject_symlink_components(path, step, include_final=False)
    require(not path.exists(), step, f"refusing to overwrite immutable output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    reject_symlink_components(path, step, include_final=False)
    descriptor, temporary_raw = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as exc:
        raise MediaContractError(step, f"refusing to overwrite immutable output: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)
    parent = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(parent)
    finally:
        os.close(parent)


def copy_once(source: Path, destination: Path, step: str) -> None:
    write_bytes_once(destination, read_bytes_no_follow(source, step), step)


def clean_environment() -> dict[str, str]:
    result = {key: os.environ[key] for key in ALLOWED_ENVIRONMENT if key in os.environ}
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    return result


def git_environment() -> dict[str, str]:
    return {key: value for key, value in clean_environment().items() if not key.startswith("GIT_")}


def run_checked(
    argv: list[str],
    step: str,
    *,
    capture_stdout: bool = False,
    capture_stderr: bool = False,
    timeout_seconds: int = 600,
    input_data: bytes | None = None,
) -> subprocess.CompletedProcess[str]:
    result = run_captured(
        argv, timeout=float(timeout_seconds), grace=2.0, env=clean_environment(), input_data=input_data
    )
    if result.returncode == 124:
        raise MediaContractError(step, "local media command timed out")
    if not result.terminal:
        raise MediaContractError(step, "local media process group did not stop")
    if result.stdout_truncated or result.stderr_truncated:
        raise MediaContractError(step, "local media command exceeded its output limit")
    if result.returncode != 0:
        raise MediaContractError(step, f"local media command exited {result.returncode}")
    return subprocess.CompletedProcess(
        argv,
        result.returncode,
        result.stdout.decode("utf-8", errors="replace") if capture_stdout else None,
        result.stderr.decode("utf-8", errors="replace") if capture_stderr else None,
    )


def probe_mp3(context: dict[str, Any], payload: bytes, step: str) -> dict[str, Any]:
    result = run_checked(
        [str(context["ffprobe"]), "-v", "error", "-show_streams", "-show_format", "-of", "json", "-i", "pipe:0"],
        step,
        capture_stdout=True,
        input_data=payload,
        timeout_seconds=60,
    )
    try:
        value = json.loads(result.stdout or "")
    except json.JSONDecodeError as exc:
        raise MediaContractError(step, "FFprobe returned invalid audio JSON") from exc
    streams = value.get("streams") if isinstance(value, dict) else None
    media_format = value.get("format") if isinstance(value, dict) else None
    require(isinstance(streams, list), step, "FFprobe audio streams are missing")
    require(isinstance(media_format, dict), step, "FFprobe audio format is missing")
    assert isinstance(streams, list)
    assert isinstance(media_format, dict)
    require(
        any(
            isinstance(stream, dict)
            and stream.get("codec_type") == "audio"
            and stream.get("codec_name") in {"mp3", "mp3float"}
            for stream in streams
        ),
        step,
        "audio is not decodable MP3",
    )
    require("mp3" in str(media_format.get("format_name", "")).split(","), step, "audio container is not MP3")
    return value


def approval_receipt(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    step = "narration.approval"
    value = read_json(path, step)
    required = {"status", "job_sha256", "script_sha256", "settings_sha256", "characters", "impact", "user_reply"}
    require(required.issubset(value), step, "paid approval receipt is incomplete")
    require(value["status"] == "approved", step, "paid approval is not approved")
    require(value["job_sha256"] == context["job_sha256"], step, "paid approval job hash mismatch")
    require(value["script_sha256"] == context["script_sha256"], step, "paid approval script hash mismatch")
    require(value["settings_sha256"] == context["settings_sha256"], step, "paid approval settings hash mismatch")
    require(value["characters"] == context["characters"], step, "paid approval character count mismatch")
    return value


def git_result(root: Path, argv: list[str]) -> int:
    executable = shutil.which("git")
    if executable is None:
        return 126
    return run_captured([executable, "-C", str(root), *argv], timeout=20, grace=2.0, env=git_environment()).returncode


def credential_preflight(context: dict[str, Any]) -> dict[str, Any]:
    step = "narration.credential-preflight"
    credential = context["credential"]
    if credential["source"] == "project-env":
        relative = credential["path"].relative_to(context["root"])
        ignored = git_result(context["root"], ["check-ignore", "-q", "--", str(relative)]) == 0
        tracked = git_result(context["root"], ["ls-files", "--error-unmatch", "--", str(relative)]) == 0
        require(ignored and not tracked, step, "project credential file must be ignored and untracked")
        present = False
        with credential["path"].open("rb") as handle:
            expected = credential["variable"].encode("ascii")
            for line in handle:
                stripped = line.strip()
                if stripped.startswith(b"export "):
                    stripped = stripped[7:].lstrip()
                key, separator, _ = stripped.partition(b"=")
                if separator and key.strip() == expected:
                    present = True
                    break
        require(present, step, "credential variable is absent")
        return {"source": "project-env", "path_policy": "ignored-untracked", "variable_present": True}
    security = Path("/usr/bin/security")
    require(security.is_file(), step, "macOS security tool is unavailable")
    result = run_checked(
        [str(security), "find-generic-password", "-a", credential["account"], "-s", credential["service"]],
        step,
        timeout_seconds=20,
    )
    require(result.returncode == 0, step, "keychain item is absent")
    return {"source": "keychain", "item_present": True}


def read_credential(context: dict[str, Any]) -> str:
    step = "narration.credential-read"
    credential = context["credential"]
    if credential["source"] == "project-env":
        matches: list[str] = []
        expected = credential["variable"]
        with credential["path"].open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                if stripped.startswith("export "):
                    stripped = stripped[7:].lstrip()
                key, separator, value = stripped.partition("=")
                if separator and key.strip() == expected:
                    matches.append(value.strip().strip("'\""))
        require(len(matches) == 1 and bool(matches[0]), step, "credential variable must occur exactly once")
        return matches[0]
    result = run_captured(
        ["/usr/bin/security", "find-generic-password", "-a", credential["account"], "-s", credential["service"], "-w"],
        timeout=20,
        grace=2.0,
        env=clean_environment(),
    )
    require(
        result.returncode == 0 and result.terminal and bool(result.stdout.strip()),
        step,
        "keychain credential retrieval failed",
    )
    return result.stdout.decode("utf-8").strip()


def failure_receipt(context: dict[str, Any], phase: str, error: MediaContractError) -> None:
    if phase not in {"narration", "render", "qa"}:
        return
    path = context["artifact_root"] / f"{phase}-failure.json"
    if path.exists():
        return
    message = re.sub(r"[\r\n]+", " ", str(error))[:512]
    write_json_once(
        path,
        {
            "schema_version": 1,
            "attempt_id": context["artifact_root"].name,
            "phase": phase,
            "status": "fail",
            "last_completed_step_id": None,
            "failing_step_id": error.step,
            "error": {"type": type(error).__name__, "message": message},
            "same_origin_requests": [],
            "page_errors": [],
            "console_errors": [],
            "request_failures": [],
            "server_logs": [],
            "cleanup": [{"actor": "elevenlabs" if phase == "narration" else "ffmpeg", "status": "closed"}],
            "approach_fingerprint": f"global media_pipeline.py + {phase} mode",
            "original_violation": (f"{phase} did not produce its declared success artifact"),
            "artifacts": [],
        },
        f"{phase}.failure-receipt",
    )

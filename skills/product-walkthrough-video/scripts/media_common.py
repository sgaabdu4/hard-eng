#!/usr/bin/env python3
"""Shared immutable-output, credential, and failure helpers for walkthrough media."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from media_manifest import MediaContractError, SECRET_NAME, digest, read_json, require


def write_json_once(path: Path, value: dict[str, Any], step: str) -> None:
    require(not path.exists(), step, f"refusing to overwrite immutable output: {path}")
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    write_bytes_once(path, payload, step)


def write_bytes_once(path: Path, payload: bytes, step: str) -> None:
    require(not path.exists(), step, f"refusing to overwrite immutable output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
        path.chmod(0o600)
    except FileExistsError as exc:
        raise MediaContractError(
            step, f"refusing to overwrite immutable output: {path}"
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)


def copy_once(source: Path, destination: Path, step: str) -> None:
    write_bytes_once(destination, source.read_bytes(), step)


def clean_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if SECRET_NAME.search(key) is None
    }


def git_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in clean_environment().items()
        if not key.startswith("GIT_")
    }


def run_checked(
    argv: list[str],
    step: str,
    *,
    capture_stdout: bool = False,
    capture_stderr: bool = False,
    timeout_seconds: int = 600,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
            stderr=subprocess.PIPE if capture_stderr else subprocess.DEVNULL,
            text=True,
            env=clean_environment(),
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaContractError(step, "local media command timed out") from exc
    if result.returncode != 0:
        raise MediaContractError(
            step, f"local media command exited {result.returncode}"
        )
    return result


def approval_receipt(path: Path, context: dict[str, Any]) -> dict[str, Any]:
    step = "narration.approval"
    value = read_json(path, step)
    required = {
        "status",
        "job_sha256",
        "script_sha256",
        "settings_sha256",
        "characters",
        "impact",
        "user_reply",
    }
    require(required.issubset(value), step, "paid approval receipt is incomplete")
    require(value["status"] == "approved", step, "paid approval is not approved")
    require(
        value["job_sha256"] == context["job_sha256"],
        step,
        "paid approval job hash mismatch",
    )
    require(
        value["script_sha256"] == context["script_sha256"],
        step,
        "paid approval script hash mismatch",
    )
    require(
        value["settings_sha256"] == context["settings_sha256"],
        step,
        "paid approval settings hash mismatch",
    )
    require(
        value["characters"] == context["characters"],
        step,
        "paid approval character count mismatch",
    )
    return value


def git_result(root: Path, argv: list[str]) -> int:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *argv],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=git_environment(),
            check=False,
            timeout=20,
        ).returncode
    except subprocess.TimeoutExpired:
        return 124


def credential_preflight(context: dict[str, Any]) -> dict[str, Any]:
    step = "narration.credential-preflight"
    credential = context["credential"]
    if credential["source"] == "project-env":
        relative = credential["path"].relative_to(context["root"])
        ignored = (
            git_result(context["root"], ["check-ignore", "-q", "--", str(relative)])
            == 0
        )
        tracked = (
            git_result(
                context["root"],
                ["ls-files", "--error-unmatch", "--", str(relative)],
            )
            == 0
        )
        require(
            ignored and not tracked,
            step,
            "project credential file must be ignored and untracked",
        )
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
        return {
            "source": "project-env",
            "path_policy": "ignored-untracked",
            "variable_present": True,
        }
    security = Path("/usr/bin/security")
    require(security.is_file(), step, "macOS security tool is unavailable")
    result = run_checked(
        [
            str(security),
            "find-generic-password",
            "-a",
            credential["account"],
            "-s",
            credential["service"],
        ],
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
        require(
            len(matches) == 1 and bool(matches[0]),
            step,
            "credential variable must occur exactly once",
        )
        return matches[0]
    try:
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-a",
                credential["account"],
                "-s",
                credential["service"],
                "-w",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=clean_environment(),
            check=False,
            timeout=20,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaContractError(step, "keychain retrieval timed out") from exc
    require(
        result.returncode == 0 and bool(result.stdout.strip()),
        step,
        "keychain credential retrieval failed",
    )
    return result.stdout.strip()


def failure_receipt(
    context: dict[str, Any], phase: str, error: MediaContractError
) -> None:
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
            "cleanup": [
                {
                    "actor": "elevenlabs" if phase == "narration" else "ffmpeg",
                    "status": "closed",
                }
            ],
            "approach_fingerprint": f"global media_pipeline.py + {phase} mode",
            "original_violation": (
                f"{phase} did not produce its declared success artifact"
            ),
            "artifacts": [],
        },
        f"{phase}.failure-receipt",
    )

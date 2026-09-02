#!/usr/bin/env python3
"""Bounded JSON HTTP client shared by the Jira Cloud and Azure DevOps tracker adapters; secrets never leave redacted."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import tracker_probe

REQUEST_TIMEOUT = 30
MAX_BODY = 1 << 20
JSON = "application/json"


class TrackerError(RuntimeError):
    pass


def request(
    method: str,
    url: str,
    authorization: str,
    creds: dict[str, str],
    payload: object | None = None,
    *,
    content_type: str = JSON,
) -> tuple[int, dict[str, object] | list[object] | str]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": authorization, "Accept": JSON}
    if body is not None:
        headers["Content-Type"] = content_type
    http_request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(http_request, timeout=REQUEST_TIMEOUT) as response:
            status, raw = response.status, response.read(MAX_BODY)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(MAX_BODY)
    except (urllib.error.URLError, OSError, ValueError) as error:
        raise TrackerError(tracker_probe.redact(f"{method} {url} failed: {error}", creds)) from error
    text = raw.decode("utf-8", "replace")
    try:
        parsed: dict[str, object] | list[object] | str = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        parsed = text
    return status, parsed


def expect(
    method: str,
    url: str,
    authorization: str,
    creds: dict[str, str],
    payload: object | None,
    *,
    label: str,
    content_type: str = JSON,
) -> dict[str, object] | list[object] | str:
    status, parsed = request(method, url, authorization, creds, payload, content_type=content_type)
    if status not in (200, 201, 204):
        detail = json.dumps(parsed)[:200] if not isinstance(parsed, str) else parsed[:200]
        raise TrackerError(tracker_probe.redact(f"{label} returned {status}: {detail}", creds))
    return parsed

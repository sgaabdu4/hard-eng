#!/usr/bin/env python3
"""Keep the explicit recovery exception narrow and authorization-specific."""

from __future__ import annotations

from pathlib import Path

from execution_evidence import FINGERPRINT, EvidenceError, validate_execution


def validate_reopen_authorization(
    repo: Path,
    plan: Path,
    fingerprint: str,
    session_id: str,
    request_digest: str,
    *,
    recover_invalid_authorization: bool = False,
) -> str:
    if recover_invalid_authorization and (not session_id.strip() or not FINGERPRINT.fullmatch(request_digest)):
        raise EvidenceError("authorization recovery requires a runtime session id and request digest")
    try:
        return validate_execution(repo, plan, fingerprint, session_id, request_digest)
    except EvidenceError as error:
        recoverable = str(error).startswith(("invalid receipt authorization.json", "authorization receipt "))
        if not recover_invalid_authorization or not recoverable:
            raise
        return "recovered"

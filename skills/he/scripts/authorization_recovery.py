#!/usr/bin/env python3
"""Keep the explicit recovery exception narrow and authorization-specific."""

from __future__ import annotations

from pathlib import Path

from execution_evidence import EvidenceError, validate_execution


def validate_reopen_authorization(
    repo: Path, plan: Path, fingerprint: str, *, recover_invalid_authorization: bool = False
) -> str:
    try:
        return validate_execution(repo, plan, fingerprint)
    except EvidenceError as error:
        recoverable = str(error).startswith(("invalid receipt authorization.json", "authorization receipt "))
        if not recover_invalid_authorization or not recoverable:
            raise
        return "recovered"

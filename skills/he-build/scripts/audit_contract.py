#!/usr/bin/env python3
"""Structured result contract for the Hard Eng final auditor."""

from __future__ import annotations

import re


PLAN_PATH = re.compile(r"^features/[^/]+/PLAN\.md$")
SNAPSHOT = re.compile(r"^sha256:[0-9a-f]{64}$")
FINDING_ID = re.compile(r"^A-[1-9][0-9]*$")
EVIDENCE_CITATION = re.compile(
    r"(?:^|[\s`(])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+:[1-9][0-9]*"
    r"|(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9]+[^\n]{0,80}\bhunk\b"
)
VERDICTS = {"pass", "concerns", "fail"}
AXES = {"standards", "spec"}
SEVERITIES = {"critical", "medium", "low", "info"}
FINDING_KEYS = {"id", "axis", "severity", "evidence", "risk", "fix", "required"}
RESULT_KEYS = {"snapshot_id", "verdict", "findings", "unknowns", "summary"}
MAX_TEXT = 800
MAX_SUMMARY = 1200
MAX_FINDINGS = 40
MAX_UNKNOWNS = 20
USAGE_REQUIRED = ("input_tokens", "cached_input_tokens", "output_tokens")
USAGE_OPTIONAL = ("reasoning_output_tokens",)


class AuditError(ValueError):
    pass


class RetryableAuditError(AuditError):
    """One unit stalled before producing any review item."""


def finding_issue(finding: dict[str, object], snapshot: str) -> list[str]:
    def clean(value: object) -> str:
        return re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()

    evidence = (
        f"audit={finding['id']}; snapshot={snapshot}; axis={finding['axis']}; "
        f"severity={finding['severity']}; source={clean(finding['evidence'])}"
    )
    action = f"disposition=open; proof=pending; re-audit=pending; fix={clean(finding['fix'])}"
    return ["issue", evidence, clean(finding["risk"]), "$he-build", action]


def parse_usage(raw: object) -> dict[str, int]:
    if (
        not isinstance(raw, dict)
        or any(type(raw.get(key)) is not int for key in USAGE_REQUIRED)
        or any(key in raw and type(raw[key]) is not int for key in USAGE_OPTIONAL)
    ):
        raise AuditError("codex audit usage event is invalid")
    keys = (*USAGE_REQUIRED, *(key for key in USAGE_OPTIONAL if key in raw))
    usage = {key: raw[key] for key in keys}
    if any(value < 0 for value in usage.values()):
        raise AuditError("codex audit usage event is invalid")
    return usage


def output_schema() -> dict[str, object]:
    finding = {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(FINDING_KEYS),
        "properties": {
            "id": {"type": "string", "pattern": FINDING_ID.pattern},
            "axis": {"type": "string", "enum": sorted(AXES)},
            "severity": {"type": "string", "enum": sorted(SEVERITIES)},
            "evidence": {
                "type": "string", "minLength": 1, "maxLength": MAX_TEXT,
                "pattern": EVIDENCE_CITATION.pattern,
            },
            "risk": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
            "fix": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
            "required": {"type": "boolean"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": sorted(RESULT_KEYS),
        "properties": {
            "snapshot_id": {"type": "string", "pattern": SNAPSHOT.pattern},
            "verdict": {"type": "string", "enum": sorted(VERDICTS)},
            "findings": {"type": "array", "maxItems": MAX_FINDINGS, "items": finding},
            "unknowns": {
                "type": "array",
                "maxItems": MAX_UNKNOWNS,
                "items": {"type": "string", "minLength": 1, "maxLength": MAX_TEXT},
            },
            "summary": {"type": "string", "minLength": 1, "maxLength": MAX_SUMMARY},
        },
    }


def validate_result(result: object, expected_snapshot: str) -> dict[str, object]:
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise AuditError("invalid audit result keys")
    if result["snapshot_id"] != expected_snapshot or not SNAPSHOT.fullmatch(str(result["snapshot_id"])):
        raise AuditError("audit snapshot mismatch")
    if result["verdict"] not in VERDICTS:
        raise AuditError("invalid audit verdict")
    if not isinstance(result["summary"], str) or not result["summary"].strip() or len(result["summary"]) > MAX_SUMMARY:
        raise AuditError("invalid audit summary")
    unknowns = result["unknowns"]
    if not isinstance(unknowns, list) or len(unknowns) > MAX_UNKNOWNS or any(
        not isinstance(item, str) or not item.strip() or len(item) > MAX_TEXT for item in unknowns
    ):
        raise AuditError("invalid audit unknowns")
    findings = result["findings"]
    if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
        raise AuditError("invalid audit findings")
    seen: set[str] = set()
    required_count = 0
    for finding in findings:
        if not isinstance(finding, dict) or set(finding) != FINDING_KEYS:
            raise AuditError("invalid audit finding keys")
        finding_id = finding["id"]
        if not isinstance(finding_id, str) or not FINDING_ID.fullmatch(finding_id) or finding_id in seen:
            raise AuditError("invalid or duplicate audit finding ID")
        seen.add(finding_id)
        if finding["axis"] not in AXES or finding["severity"] not in SEVERITIES:
            raise AuditError("invalid audit finding classification")
        for field in ("evidence", "risk", "fix"):
            if not isinstance(finding[field], str) or not finding[field].strip() or len(finding[field]) > MAX_TEXT:
                raise AuditError(f"invalid audit finding {field}")
        if not EVIDENCE_CITATION.search(finding["evidence"]):
            raise AuditError("audit finding evidence lacks exact path:line or hunk citation")
        if not isinstance(finding["required"], bool):
            raise AuditError("invalid audit finding required flag")
        if finding["severity"] in {"critical", "medium"} and not finding["required"]:
            raise AuditError("critical/medium audit finding must be required")
        if finding["severity"] == "info" and finding["required"]:
            raise AuditError("info audit finding cannot be required")
        required_count += int(finding["required"])
    verdict = result["verdict"]
    if required_count and verdict != "fail":
        raise AuditError("required audit finding requires fail verdict")
    if verdict == "pass" and (required_count or unknowns):
        raise AuditError("audit pass has required findings or unknowns")
    if verdict == "fail" and not required_count:
        raise AuditError("audit fail has no required finding")
    if verdict == "concerns" and not findings and not unknowns:
        raise AuditError("audit concerns has no evidence")
    return result

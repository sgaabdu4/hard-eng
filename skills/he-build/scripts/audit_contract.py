#!/usr/bin/env python3
"""Structured result contract for the Hard Eng final auditor."""

from __future__ import annotations

import re


PLAN_PATH = re.compile(r"^features/[^/]+/PLAN\.md$")
SNAPSHOT = re.compile(r"^sha256:[0-9a-f]{64}$")
FINDING_ID = re.compile(r"^A-[1-9][0-9]*$")
EVIDENCE_CITATION = re.compile(
    r"(?:^|[\s`(])(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+:[1-9][0-9]*"
    r"|(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+[^\n]{0,80}\bhunk\b"
)
EVIDENCE_PATH_CITATION = re.compile(
    r"(?:^|[\s`(])((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)"
    r"(?::[1-9][0-9]*|[^\n]{0,80}\bhunk\b)"
)
VERDICTS = {"pass", "concerns", "fail"}
AXES = {"standards", "spec"}
SEVERITIES = {"critical", "medium", "low", "info"}
ROOT_ID = re.compile(
    r"^((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+)::"
    r"[a-z0-9][a-z0-9-]{0,79}$"
)
FINDING_REQUIRED_KEYS = {
    "id", "axis", "severity", "root", "evidence", "risk", "fix", "required",
}
FINDING_KEYS = FINDING_REQUIRED_KEYS | {"related_evidence"}
RESULT_KEYS = {"snapshot_id", "verdict", "findings", "unknowns", "summary"}
CHILD_RESULT_KEYS = RESULT_KEYS - {"snapshot_id"}
MAX_TEXT = 800
MAX_SUMMARY = 1200
MAX_FINDINGS = 40
MAX_UNKNOWNS = 20
USAGE_REQUIRED = ("input_tokens", "cached_input_tokens", "output_tokens")
USAGE_OPTIONAL = ("reasoning_output_tokens",)
VISUAL_REVISION_EQUALITY = (
    "must equal", "must match", "should equal", "should match",
    "required to equal", "required to match", "does not equal", "does not match",
    "differs from", "mismatch",
)


class AuditError(ValueError):
    pass


class RetryableAuditError(AuditError):
    """One unit stalled before producing any review item."""


def self_referential_visual_snapshot_claim(value: object) -> bool:
    if not isinstance(value, str):
        return False
    text = re.sub(r"[`_*]+", "", value.lower()).replace("_", " ")
    visual_revision = "binding.revision" in text or "visual revision" in text
    repository_snapshot = any(
        marker in text
        for marker in ("repository snapshot", "hard eng snapshot", "snapshot id")
    )
    return (
        visual_revision
        and repository_snapshot
        and any(marker in text for marker in VISUAL_REVISION_EQUALITY)
    )


def finding_issue(finding: dict[str, object], snapshot: str) -> list[str]:
    def clean(value: object) -> str:
        return re.sub(r"\s+", " ", str(value)).replace("|", "/").strip()

    sources = [str(finding["evidence"]), *finding.get("related_evidence", [])]
    evidence = (
        f"audit={finding['id']}; snapshot={snapshot}; axis={finding['axis']}; "
        f"severity={finding['severity']}; root={clean(finding['root'])}; "
        f"source={clean(' || '.join(sources))}"
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
        "required": sorted(FINDING_REQUIRED_KEYS),
        "properties": {
            "id": {"type": "string", "pattern": FINDING_ID.pattern},
            "axis": {"type": "string", "enum": sorted(AXES)},
            "severity": {"type": "string", "enum": sorted(SEVERITIES)},
            "root": {"type": "string", "pattern": ROOT_ID.pattern},
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
        "required": sorted(CHILD_RESULT_KEYS),
        "properties": {
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


def finding_root_bound_to_citation(finding: object) -> bool:
    if not isinstance(finding, dict):
        return False
    root = finding.get("root")
    evidence = finding.get("evidence")
    match = ROOT_ID.fullmatch(root) if isinstance(root, str) else None
    if match is None or not isinstance(evidence, str):
        return False
    cited = tuple(item.group(1) for item in EVIDENCE_PATH_CITATION.finditer(evidence))
    return match.group(1) in cited


def validate_finding_fields(
    finding: object, seen: set[str], *, allow_missing_required: bool = False,
    allow_missing_root: bool = False, require_citation: bool = True,
) -> bool | None:
    keys = set(finding) if isinstance(finding, dict) else set()
    missing = FINDING_REQUIRED_KEYS - keys
    allowed_missing = ({"required"} if allow_missing_required else set()) | (
        {"root"} if allow_missing_root else set()
    )
    if not isinstance(finding, dict) or missing - allowed_missing or keys - FINDING_KEYS:
        missing_text = ",".join(sorted(missing)) or "none"
        extra_text = ",".join(sorted(keys - FINDING_KEYS)) or "none"
        raise AuditError(f"invalid audit finding keys: missing={missing_text}; extra={extra_text}")
    finding_id = finding["id"]
    if not isinstance(finding_id, str) or not FINDING_ID.fullmatch(finding_id) or finding_id in seen:
        raise AuditError("invalid or duplicate audit finding ID")
    seen.add(finding_id)
    if finding["axis"] not in AXES or finding["severity"] not in SEVERITIES:
        raise AuditError("invalid audit finding classification")
    for field in ("evidence", "risk", "fix"):
        if not isinstance(finding[field], str) or not finding[field].strip() or len(finding[field]) > MAX_TEXT:
            raise AuditError(f"invalid audit finding {field}")
    if require_citation and not EVIDENCE_CITATION.search(finding["evidence"]):
        raise AuditError("audit finding evidence lacks exact path:line or hunk citation")
    root = finding.get("root")
    if root is not None:
        match = ROOT_ID.fullmatch(root) if isinstance(root, str) else None
        if match is None or (require_citation and not finding_root_bound_to_citation(finding)):
            raise AuditError("audit finding root is not bound to cited owner")
    related = finding.get("related_evidence", [])
    if (
        not isinstance(related, list)
        or any(not isinstance(item, str) for item in related)
        or len(related) != len(set(related))
        or any(
            not item.strip() or len(item) > MAX_TEXT
            or (require_citation and not EVIDENCE_CITATION.search(item))
            for item in related
        )
    ):
        raise AuditError("invalid audit finding related evidence")
    if "required" not in finding:
        return None
    if not isinstance(finding["required"], bool):
        raise AuditError("invalid audit finding required flag")
    if finding["severity"] in {"critical", "medium"} and not finding["required"]:
        raise AuditError("critical/medium audit finding must be required")
    if finding["severity"] == "info" and finding["required"]:
        raise AuditError("info audit finding cannot be required")
    return finding["required"]


def validate_result(
    result: object, expected_snapshot: str, *,
    max_findings: int = MAX_FINDINGS, max_unknowns: int = MAX_UNKNOWNS,
    max_related_evidence: int = MAX_FINDINGS,
) -> dict[str, object]:
    if (
        type(max_findings) is not int or type(max_unknowns) is not int
        or type(max_related_evidence) is not int
        or min(max_findings, max_unknowns, max_related_evidence) < 0
    ):
        raise AuditError("invalid audit evidence limits")
    if not isinstance(result, dict) or set(result) != RESULT_KEYS:
        raise AuditError("invalid audit result keys")
    if result["snapshot_id"] != expected_snapshot or not SNAPSHOT.fullmatch(str(result["snapshot_id"])):
        raise AuditError("audit snapshot mismatch")
    if result["verdict"] not in VERDICTS:
        raise AuditError("invalid audit verdict")
    if not isinstance(result["summary"], str) or not result["summary"].strip() or len(result["summary"]) > MAX_SUMMARY:
        raise AuditError("invalid audit summary")
    unknowns = result["unknowns"]
    if not isinstance(unknowns, list) or len(unknowns) > max_unknowns or any(
        not isinstance(item, str) or not item.strip() or len(item) > MAX_TEXT for item in unknowns
    ):
        raise AuditError("invalid audit unknowns")
    if any(self_referential_visual_snapshot_claim(item) for item in unknowns):
        raise AuditError("audit unknown conflates visual revision with repository snapshot")
    findings = result["findings"]
    if not isinstance(findings, list) or len(findings) > max_findings:
        raise AuditError("invalid audit findings")
    seen: set[str] = set()
    required_count = 0
    for finding in findings:
        related = finding.get("related_evidence", []) if isinstance(finding, dict) else []
        related_claims = related if isinstance(related, list) else []
        if isinstance(finding, dict) and self_referential_visual_snapshot_claim(
            " ".join(
                [*(str(finding.get(field, "")) for field in ("evidence", "risk", "fix")),
                 *related_claims]
            )
        ):
            raise AuditError("audit finding conflates visual revision with repository snapshot")
        if isinstance(related, list) and len(related) > max_related_evidence:
            raise AuditError("audit finding exceeds related evidence capacity")
        required_count += int(validate_finding_fields(finding, seen))
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

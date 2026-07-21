#!/usr/bin/env python3
"""Select full inventory or bounded finding re-audit from canonical PLAN evidence."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import PurePosixPath

from audit_contract import AuditError, EVIDENCE_PATH_CITATION
from audit_inventory import risk_review_scopes
from audit_packet import partition_review_scopes
from audit_result import aggregate_audit_results, aggregate_evidence_limits
from plan_contract import audit_receipt_snapshot
from plan_items import parse_active_items
from repository_index import repository_source_index


AUDIT_POLICY_HEADING = "## Audit policy"
RISK_TIERS = {"standard", "critical"}
AUDIT_ROOT = re.compile(
    r"; root=((?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.[A-Za-z0-9]+::"
    r"[a-z0-9][a-z0-9-]{0,79}); source="
)


def audit_risk_tier(plan_text: str) -> str:
    lines = plan_text.splitlines()
    headings = [index for index, line in enumerate(lines) if line.strip() == AUDIT_POLICY_HEADING]
    if not headings:
        return "critical"
    if len(headings) != 1:
        raise AuditError("PLAN requires at most one Audit policy section")
    start = headings[0] + 1
    end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ")), len(lines))
    values = [
        line.split("=", 1)[1].strip()
        for line in lines[start:end]
        if line.strip().startswith("- risk_tier =") and "=" in line
    ]
    if len(values) != 1 or values[0] not in RISK_TIERS:
        raise AuditError("Audit policy requires risk_tier = standard|critical")
    return values[0]


def _safe_citation_paths(value: str) -> tuple[str, ...]:
    paths = []
    for match in EVIDENCE_PATH_CITATION.finditer(" " + value.replace("source=", "source= ")):
        path = match.group(1)
        parts = PurePosixPath(path).parts
        if path.startswith("/") or not parts or any(part in {"", ".", ".."} for part in parts):
            raise AuditError("audit re-audit evidence contains an unsafe path")
        if path not in paths:
            paths.append(path)
    return tuple(paths)


def pending_reaudit_items(plan_text: str, current_snapshot: str):
    if "## Active items" not in plan_text.splitlines():
        return ()
    pending = []
    for item_id, row in parse_active_items(plan_text).items():
        if not row[2].startswith("audit=") or row[6] != "closed":
            continue
        if audit_receipt_snapshot(row) == current_snapshot:
            continue
        paths = _safe_citation_paths(row[2])
        if not paths:
            raise AuditError(f"audit re-audit item lacks cited owner paths: {item_id}")
        root_match = AUDIT_ROOT.search(row[2])
        pending.append((item_id, paths, root_match.group(1) if root_match else None))
    return tuple(pending)


def prior_audit_roots(plan_text: str) -> set[str]:
    if "## Active items" not in plan_text.splitlines():
        return set()
    roots = set()
    for row in parse_active_items(plan_text).values():
        if not row[2].startswith("audit="):
            continue
        match = AUDIT_ROOT.search(row[2])
        if match:
            roots.add(match.group(1))
    return roots


def repeated_audit_roots(plan_text: str, result: dict[str, object]) -> tuple[str, ...]:
    previous = prior_audit_roots(plan_text)
    findings = result.get("findings", [])
    current = {
        finding.get("root")
        for finding in findings
        if isinstance(finding, dict) and isinstance(finding.get("root"), str)
    }
    return tuple(sorted(previous & current))


def build_review_scopes(
    root, plan, snapshot: str, full_changed_paths: tuple[str, ...], *,
    max_related_sections: int, max_related_bytes: int, max_packet_bytes: int,
    build_evidence_provenance: str,
):
    plan_text = plan.read_text(encoding="utf-8")
    risk_tier = audit_risk_tier(plan_text)
    items = pending_reaudit_items(plan_text, snapshot)
    if not items:
        built = partition_review_scopes(
            root, plan, full_changed_paths,
            max_related_sections=max_related_sections,
            max_related_bytes=max_related_bytes,
            max_packet_bytes=max_packet_bytes,
            build_evidence_provenance=build_evidence_provenance,
        )
        return "inventory", risk_tier, risk_review_scopes(built, risk_tier)
    owner_paths = tuple(dict.fromkeys(paths[0] for _, paths, _ in items))
    built = partition_review_scopes(
        root, plan, owner_paths,
        max_related_sections=max_related_sections,
        max_related_bytes=max_related_bytes,
        max_packet_bytes=max_packet_bytes,
        repository_index=repository_source_index(root),
        build_evidence_provenance=build_evidence_provenance,
    )
    scopes = []
    assigned = set()
    for scope in built:
        targets = [
            {
                "item": item_id, "citedPaths": paths,
                **({"semanticRoot": root} if root else {}),
            }
            for item_id, paths, root in items if paths[0] in scope.primary_paths
        ]
        assigned.update(target["item"] for target in targets)
        target = "## Re-audit target\n" + json.dumps(
            targets, separators=(",", ":"), sort_keys=True,
        )
        packet = f"{scope.packet}\n\n{target}"
        packet_bytes = len(packet.encode("utf-8", "surrogateescape"))
        if packet_bytes > max_packet_bytes:
            raise AuditError("audit re-audit target exceeds fixed packet limit")
        scopes.append(replace(
            scope, packet=packet, packet_bytes=packet_bytes, review_pass="re-audit",
            packet_units=(*scope.packet_units, ("Re-audit target", len(target))),
        ))
    if assigned != {item_id for item_id, _, _ in items}:
        raise AuditError("audit re-audit target coverage mismatch")
    return "re-audit", risk_tier, risk_review_scopes(
        tuple(scopes), risk_tier, re_audit=True,
    )


def complete_reviews(mode: str, scopes, reviewed, snapshot: str):
    if mode not in {"inventory", "re-audit"} or len(reviewed) != len(scopes):
        raise AuditError("audit result count mismatch")
    combined = aggregate_audit_results(
        snapshot, tuple(result for _, result in reviewed),
        aggregate_evidence_limits(len(reviewed)),
    )
    return tuple(reviewed), combined, (tuple(scopes),)

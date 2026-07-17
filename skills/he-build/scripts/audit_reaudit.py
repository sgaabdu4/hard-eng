#!/usr/bin/env python3
"""Select full inventory or bounded finding re-audit from canonical PLAN evidence."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import PurePosixPath

from audit_contract import AuditError, EVIDENCE_PATH_CITATION
from audit_inventory import converge_inventory, semantic_root_keys
from audit_packet import partition_review_scopes
from audit_result import aggregate_audit_results, aggregate_evidence_limits
from plan_contract import audit_receipt_snapshot
from plan_items import parse_active_items
from repository_index import repository_source_index


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
        pending.append((item_id, paths))
    return tuple(pending)


def build_review_scopes(
    root, plan, snapshot: str, full_changed_paths: tuple[str, ...], *,
    max_related_sections: int, max_related_bytes: int, max_packet_bytes: int,
    build_evidence_provenance: str,
):
    items = pending_reaudit_items(plan.read_text(encoding="utf-8"), snapshot)
    if not items:
        return "inventory", partition_review_scopes(
            root, plan, full_changed_paths,
            max_related_sections=max_related_sections,
            max_related_bytes=max_related_bytes,
            max_packet_bytes=max_packet_bytes,
            build_evidence_provenance=build_evidence_provenance,
            inventory_passes=True,
        )
    owner_paths = tuple(dict.fromkeys(paths[0] for _, paths in items))
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
            {"item": item_id, "citedPaths": paths}
            for item_id, paths in items if paths[0] in scope.primary_paths
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
    if assigned != {item_id for item_id, _ in items}:
        raise AuditError("audit re-audit target coverage mismatch")
    return "re-audit", tuple(scopes)


def complete_reviews(
    mode: str, scopes, reviewed, snapshot: str, review_convergence, *, max_packet_bytes: int,
):
    if mode == "inventory":
        return converge_inventory(
            scopes, reviewed, snapshot, review_convergence,
            max_packet_bytes=max_packet_bytes,
        )
    if mode != "re-audit" or len(reviewed) != len(scopes):
        raise AuditError("audit re-audit result count mismatch")
    combined = aggregate_audit_results(
        snapshot, tuple(result for _, result in reviewed),
        aggregate_evidence_limits(len(reviewed)),
    )
    metadata = {
        "rounds": 0, "stable": True, "newRoots": 0,
        "totalRoots": len(semantic_root_keys(combined)),
    }
    return tuple(reviewed), combined, metadata, (tuple(scopes),)

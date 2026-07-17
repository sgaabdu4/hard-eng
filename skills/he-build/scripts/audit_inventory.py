#!/usr/bin/env python3
"""Review-pass expansion and rule scope for Hard Eng final audits."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from audit_contract import AuditError
from audit_result import aggregate_audit_results, aggregate_evidence_limits


MAX_CONVERGENCE_ROUNDS = 2


def inventory_review_scopes(scopes):
    return tuple(
        replace(
            scope,
            coverage_paths=scope.coverage_paths if review_pass == "owner-first" else (),
            review_pass=review_pass,
        )
        for review_pass in ("owner-first", "boundary-first")
        for scope in scopes
    )


def semantic_root_keys(result: dict[str, object]) -> set[tuple[str, str]]:
    return {
        (finding["axis"], finding["root"])
        for finding in result["findings"]
    }


def convergence_review_scopes(
    scopes, roots: set[tuple[str, str]], round_index: int, max_packet_bytes: int,
):
    base = tuple(scope for scope in scopes if scope.review_pass == "owner-first")
    if not base:
        raise AuditError("audit convergence requires owner-first inventory scopes")
    converged = []
    for scope in base:
        scoped_roots = sorted(
            f"{axis}|{root}" for axis, root in roots
            if not scope.citation_paths or root.split("::", 1)[0] in scope.citation_paths
        )
        ledger = json.dumps(scoped_roots, ensure_ascii=False, separators=(",", ":"))
        section = f"## Parent-known semantic roots\nround={round_index}\n{ledger}"
        packet = f"{scope.packet}\n\n{section}"
        packet_bytes = len(packet.encode("utf-8", "surrogateescape"))
        if packet_bytes > max_packet_bytes:
            raise AuditError("audit convergence ledger exceeds fixed packet limit")
        converged.append(replace(
            scope, packet=packet, packet_bytes=packet_bytes, review_pass="convergence",
            packet_units=(*scope.packet_units, ("Parent-known semantic roots", len(section))),
        ))
    if tuple(path for scope in converged for path in scope.coverage_paths) != tuple(
        path for scope in base for path in scope.coverage_paths
    ):
        raise AuditError("audit convergence changed primary path coverage")
    return tuple(converged)


def converge_inventory(
    scopes, initial_reviewed, snapshot: str, review_round, *, max_packet_bytes: int,
    max_rounds: int = MAX_CONVERGENCE_ROUNDS,
):
    if type(max_rounds) is not int or max_rounds < 1:
        raise AuditError("audit convergence requires a positive round limit")
    reviewed = list(initial_reviewed)
    if len(reviewed) != len(scopes):
        raise AuditError("audit inventory result count mismatch")
    executed_batches = [tuple(scopes)]
    combined = aggregate_audit_results(
        snapshot, tuple(result for _, result in reviewed),
        aggregate_evidence_limits(len(reviewed)),
    )
    known = semantic_root_keys(combined)
    last_added = 0
    for round_index in range(1, max_rounds + 1):
        round_scopes = convergence_review_scopes(
            scopes, known, round_index, max_packet_bytes,
        )
        round_reviewed = tuple(review_round(round_index, round_scopes))
        if len(round_reviewed) != len(round_scopes):
            raise AuditError("audit convergence result count mismatch")
        reviewed.extend(round_reviewed)
        executed_batches.append(round_scopes)
        combined = aggregate_audit_results(
            snapshot, tuple(result for _, result in reviewed),
            aggregate_evidence_limits(len(reviewed)),
        )
        current = semantic_root_keys(combined)
        added = current - known
        if not added:
            metadata = {"rounds": round_index, "stable": True, "newRoots": 0,
                        "totalRoots": len(current)}
            return tuple(reviewed), combined, metadata, tuple(executed_batches)
        known = current
        last_added = len(added)
    metadata = {"rounds": max_rounds, "stable": False, "newRoots": last_added,
                "totalRoots": len(known)}
    return tuple(reviewed), combined, metadata, tuple(executed_batches)


def applicable_rule_paths(tracked: tuple[str, ...], scoped: tuple[str, ...]) -> tuple[str, ...]:
    rules = []
    for relative in tracked:
        path = Path(relative)
        if path.name not in {"AGENTS.md", "AGENTS.override.md"}:
            continue
        parent = path.parent.as_posix()
        if parent == "." or any(item == parent or item.startswith(parent + "/") for item in scoped):
            rules.append(relative)
    return tuple(sorted(rules, key=lambda value: (len(Path(value).parts), value)))

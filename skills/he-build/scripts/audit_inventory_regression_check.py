#!/usr/bin/env python3
"""Regression proof for risk-tiered final audit and finding re-audit."""

from __future__ import annotations

from audit_packet import ReviewScope


def _items(*rows: str, risk_tier: str | None = None) -> str:
    policy = "" if risk_tier is None else f"## Audit policy\n- risk_tier = {risk_tier}\n\n"
    header = "| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |"
    return policy + "\n".join(
        ("## Active items", header, "|---|---|---|---|---|---|---|", *rows)
    )


def _scope(paths=("owner.py",)) -> ReviewScope:
    return ReviewScope(
        tuple(paths), tuple(paths), "packet", (), (("packet", 6),),
        0, 0, 6, tuple(paths), "single",
    )


def check_risk_tier_regressions(module, fail, snapshot: str) -> None:
    if module.audit_risk_tier("# Legacy PLAN\n") != "critical":
        fail("legacy PLAN without audit policy did not fail closed to critical")
    for tier in ("standard", "critical"):
        if module.audit_risk_tier(f"## Audit policy\n- risk_tier = {tier}\n") != tier:
            fail(f"PLAN audit policy lost {tier} tier")
    for invalid in (
        "## Audit policy\n- risk_tier = unknown\n",
        "## Audit policy\n- risk_tier = standard\n- risk_tier = critical\n",
        "## Audit policy\n\n",
    ):
        try:
            module.audit_risk_tier(invalid)
        except module.AuditError:
            pass
        else:
            fail("malformed PLAN audit policy was accepted")

    calls = []
    original_partition = module.partition_review_scopes

    class Plan:
        def __init__(self, value): self.value = value
        def read_text(self, **_kwargs): return self.value

    def partition(_root, _plan, paths, **kwargs):
        calls.append((tuple(paths), kwargs))
        return (_scope(paths),)

    module.partition_review_scopes = partition
    try:
        for tier, expected_passes in (
            ("standard", ("standard",)),
            ("critical", ("owner-first", "boundary-first")),
        ):
            mode, actual_tier, scopes = module.build_review_scopes(
                object(), Plan(_items(risk_tier=tier)), snapshot, ("whole-change.py",),
                max_related_sections=4, max_related_bytes=4096, max_packet_bytes=4096,
                build_evidence_provenance="receipt",
            )
            if (mode != "inventory" or actual_tier != tier
                    or tuple(scope.review_pass for scope in scopes) != expected_passes
                    or tuple(path for scope in scopes for path in scope.coverage_paths)
                    != ("whole-change.py",)):
                fail("initial audit did not apply PLAN risk tier exactly")
    finally:
        module.partition_review_scopes = original_partition


def check_reaudit_regressions(module, fail, snapshot: str) -> None:
    old = "sha256:" + "9" * 64
    row = (
        "| I-1 | issue | audit=A-1; snapshot=" + old
        + "; axis=standards; severity=critical; source=owner.py:7 / tests/owner_test.py:9 "
        "| risk | $he-build | disposition=fixed; proof=focused-pass; re-audit=pending | closed |"
    )
    text = _items(row, risk_tier="critical")
    if module.pending_reaudit_items(text, snapshot) != (
        ("I-1", ("owner.py", "tests/owner_test.py")),
    ):
        fail("audit re-audit did not select pending cited item exactly once")

    calls = []
    original_partition = module.partition_review_scopes
    original_index = module.repository_source_index

    class Plan:
        def __init__(self, value): self.value = value
        def read_text(self, **_kwargs): return self.value

    def partition(_root, _plan, paths, **kwargs):
        calls.append((tuple(paths), kwargs))
        return (_scope(paths),)

    module.partition_review_scopes = partition
    module.repository_source_index = lambda _root: object()
    try:
        mode, tier, scopes = module.build_review_scopes(
            object(), Plan(text), snapshot, ("whole-change.py",),
            max_related_sections=4, max_related_bytes=4096, max_packet_bytes=4096,
            build_evidence_provenance="receipt",
        )
        if (mode != "re-audit" or tier != "critical"
                or calls[0][0] != ("owner.py",)
                or tuple(scope.review_pass for scope in scopes)
                != ("re-audit-owner-first", "re-audit-boundary-first")
                or any('"item":"I-1"' not in scope.packet for scope in scopes)):
            fail("critical re-audit lost target accounting or independent passes")
    finally:
        module.partition_review_scopes = original_partition
        module.repository_source_index = original_index

    clean = {"snapshot_id": snapshot, "verdict": "pass", "findings": [],
             "unknowns": [], "summary": "scoped item verified"}
    reviewed, combined, batches = module.complete_reviews(
        "re-audit", scopes, tuple(({}, clean) for _ in scopes), snapshot,
    )
    if (len(reviewed) != 2 or combined["verdict"] != "pass"
            or batches != (tuple(scopes),)):
        fail("risk-tier re-audit did not stop after its selected clean passes")

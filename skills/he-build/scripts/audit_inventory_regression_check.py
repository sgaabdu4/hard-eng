#!/usr/bin/env python3
"""Regression proof for same-snapshot audit inventory convergence."""

from __future__ import annotations

from dataclasses import replace

from audit_packet import ReviewScope


def _items(*rows: str) -> str:
    header = "| ID | Type | Evidence | Impact | Owner | Next proof/action | Status |"
    return "\n".join(("## Active items", header, "|---|---|---|---|---|---|---|", *rows))


def check_reaudit_regressions(module, fail, snapshot: str) -> None:
    old = "sha256:" + "9" * 64
    text = _items(
        "| I-1 | issue | audit=A-1; snapshot=" + old + "; axis=standards; severity=critical; source=owner.py:7 / tests/owner_test.py:9 | risk | $he-build | disposition=fixed; proof=focused-pass; re-audit=pending | closed |",
        "| I-2 | issue | audit=A-2; snapshot=" + old + "; axis=spec; severity=medium; source=current.py:2 | risk | $he-build | disposition=rejected; proof=source-proof; re-audit=pass@" + snapshot + " | closed |",
        "| I-3 | issue | audit=A-3; snapshot=" + old + "; axis=spec; severity=medium; source=stale.py:3 | risk | $he-build | disposition=fixed; proof=test-pass; re-audit=pass@" + old + " | closed |",
    )
    pending = module.pending_reaudit_items(text, snapshot)
    if pending != (("I-1", ("owner.py", "tests/owner_test.py")), ("I-3", ("stale.py",))):
        fail("audit re-audit did not select every pending/stale cited item exactly once")
    invalid = _items(
        "| I-1 | issue | audit=A-1; snapshot=" + old + "; axis=standards; severity=critical; source=no citation | risk | $he-build | disposition=fixed; proof=pass; re-audit=pending | closed |",
    )
    try:
        module.pending_reaudit_items(invalid, snapshot)
    except module.AuditError:
        pass
    else:
        fail("audit re-audit accepted an item without a cited owner")
    calls = []
    original_partition = module.partition_review_scopes
    original_index = module.repository_source_index

    class Plan:
        def __init__(self, value): self.value = value
        def read_text(self, **_kwargs): return self.value

    def partition(_root, _plan, paths, **kwargs):
        calls.append((tuple(paths), kwargs))
        return (ReviewScope(
            tuple(paths), tuple(paths), "packet", (), (("packet", 6),),
            0, 0, 6, tuple(paths), "single",
        ),)

    module.partition_review_scopes = partition
    module.repository_source_index = lambda _root: object()
    try:
        mode, scopes = module.build_review_scopes(
            object(), Plan(text), snapshot, ("whole-change.py",),
            max_related_sections=4, max_related_bytes=4096, max_packet_bytes=4096,
            build_evidence_provenance="receipt",
        )
        if (mode != "re-audit" or len(calls) != 1
                or calls[0][0] != ("owner.py", "stale.py")
                or calls[0][1].get("inventory_passes") is not None
                or len(scopes) != 1 or scopes[0].review_pass != "re-audit"
                or '"item":"I-1"' not in scopes[0].packet
                or '"item":"I-3"' not in scopes[0].packet
                or "whole-change.py" in scopes[0].primary_paths):
            fail("audit re-audit replayed the full base inventory or lost target accounting")
        calls.clear()
        current_only = _items(text.splitlines()[4])
        mode, _ = module.build_review_scopes(
            object(), Plan(current_only), snapshot, ("whole-change.py",),
            max_related_sections=4, max_related_bytes=4096, max_packet_bytes=4096,
            build_evidence_provenance="receipt",
        )
        if mode != "inventory" or calls[0][0] != ("whole-change.py",) or not calls[0][1]["inventory_passes"]:
            fail("initial audit no longer performs full dual inventory")
    finally:
        module.partition_review_scopes = original_partition
        module.repository_source_index = original_index
    scope = ReviewScope(
        ("owner.py",), ("owner.py",), "packet", (), (("packet", 6),),
        0, 0, 6, ("owner.py",), "re-audit",
    )
    clean = {"snapshot_id": snapshot, "verdict": "pass", "findings": [],
             "unknowns": [], "summary": "scoped item verified"}
    reviewed, combined, metadata, batches = module.complete_reviews(
        "re-audit", (scope,), (({}, clean),), snapshot,
        lambda *_: fail("finding re-audit launched full inventory convergence"),
        max_packet_bytes=4096,
    )
    if (len(reviewed) != 1 or combined["verdict"] != "pass"
            or metadata != {"rounds": 0, "stable": True, "newRoots": 0, "totalRoots": 0}
            or batches != ((scope,),)):
        fail("audit re-audit lost scoped completion or triggered full replay")


def _result(snapshot: str, *roots: str) -> dict[str, object]:
    findings = [{
        "id": f"A-{index}", "axis": "standards", "severity": "medium",
        "root": root, "evidence": f"{root.split('::', 1)[0]}:{index}",
        "risk": f"risk-{index}", "fix": f"fix-{index}", "required": True,
    } for index, root in enumerate(roots, 1)]
    return {
        "snapshot_id": snapshot, "verdict": "fail" if findings else "pass",
        "findings": findings, "unknowns": [], "summary": "inventory fixture",
    }


def check_inventory_convergence_regressions(module, fail, snapshot: str) -> None:
    owner = ReviewScope(
        ("owner.py",), ("owner.py",), "packet", (), (("packet", 6),),
        0, 0, 6, ("owner.py", "helper.py"), "owner-first",
    )
    scopes = (owner, replace(owner, coverage_paths=(), review_pass="boundary-first"))
    initial = (({}, _result(snapshot, "owner.py::initial-root")), ({}, _result(snapshot)))
    confirmation = _result(snapshot)
    confirmation.update(verdict="concerns", unknowns=["ordered convergence unknown"])
    batches = iter((
        (({}, _result(snapshot, "owner.py::late-root", "helper.py::other-late-root")),),
        (({}, confirmation),),
    ))
    observed = []

    def review(round_index, convergence_scopes):
        observed.append((round_index, convergence_scopes))
        return next(batches)

    reviewed, combined, convergence, executed_batches = module.converge_inventory(
        scopes, initial, snapshot, review, max_packet_bytes=4096,
    )
    roots = [finding["root"] for finding in combined["findings"]]
    if (roots != ["owner.py::initial-root", "owner.py::late-root", "helper.py::other-late-root"]
            or combined["unknowns"] != ["ordered convergence unknown"]
            or len(reviewed) != 4
            or convergence != {"rounds": 2, "stable": True, "newRoots": 0, "totalRoots": 3}
            or [len(batch) for batch in executed_batches] != [2, 1, 1]):
        fail("same-snapshot convergence lost, reordered, or failed to confirm late roots")
    for round_index, round_scopes in observed:
        if (len(round_scopes) != 1 or round_scopes[0].primary_paths != owner.primary_paths
                or round_scopes[0].coverage_paths != owner.coverage_paths
                or round_scopes[0].review_pass != "convergence"
                or f"round={round_index}" not in round_scopes[0].packet):
            fail("convergence narrowed coverage or lost its round binding")
    if "owner.py::initial-root" not in observed[0][1][0].packet:
        fail("convergence pass omitted its parent-known root exclusion ledger")
    if not all(root in observed[1][1][0].packet for root in roots):
        fail("confirmation pass omitted newly discovered semantic roots")
    try:
        module.convergence_review_scopes(scopes, {("standards", roots[0])}, 1, 6)
    except module.AuditError:
        pass
    else:
        fail("convergence ledger silently overflowed its fixed packet boundary")

    unstable_batches = iter((
        (({}, _result(snapshot, "owner.py::late-root")),),
        (({}, _result(snapshot, "helper.py::still-later-root")),),
    ))
    unstable_reviewed, unstable, metadata, unstable_executed = module.converge_inventory(
        scopes, initial, snapshot,
        lambda _round, _scopes: next(unstable_batches), max_packet_bytes=4096,
    )
    unstable_roots = [finding["root"] for finding in unstable["findings"]]
    if (unstable_roots != [
            "owner.py::initial-root", "owner.py::late-root", "helper.py::still-later-root",
        ] or unstable["verdict"] != "fail" or len(unstable_reviewed) != 4
            or metadata != {"rounds": 2, "stable": False, "newRoots": 1, "totalRoots": 3}
            or [len(batch) for batch in unstable_executed] != [2, 1, 1]):
        fail("unstable inventory discarded its final root or produced a clean verdict")

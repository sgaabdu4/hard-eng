#!/usr/bin/env python3
"""Regression proof for same-snapshot audit inventory convergence."""

from __future__ import annotations

from dataclasses import replace

from audit_packet import ReviewScope


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

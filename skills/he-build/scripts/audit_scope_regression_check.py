#!/usr/bin/env python3
"""Synthetic regressions for bounded review-scope continuation."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import audit_packet


def check_audit_scope_regressions(fail) -> None:
    entry = ("dep.py", "## Related caller", "界" * 240)
    pieces = audit_packet._split_context_entry(
        entry, 40, max_related_bytes=120, max_packet_bytes=180,
    )
    if len(pieces) < 2 or "".join(piece[2] for piece in pieces) != entry[2]:
        fail("context continuation did not preserve exact UTF-8 evidence")
    with tempfile.TemporaryDirectory(prefix="he-context-shards-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        (root / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# Fixture\n", encoding="utf-8")
        original = audit_packet.review_packet_parts

        def packet_parts(*args, **kwargs):
            context = (("dep.py", "## Related caller", "x" * 420),)
            return ["# Review packet", "snapshot = fixture"], [
                ("## Primary", "owner.py changed hunk"),
                (context[0][1], context[0][2]),
            ], context

        audit_packet.review_packet_parts = packet_parts
        try:
            scopes = audit_packet.partition_review_scopes(
                root, plan, ("owner.py",), max_related_sections=2,
                max_related_bytes=120, max_packet_bytes=180,
                repository_index=object(),
            )
        finally:
            audit_packet.review_packet_parts = original
        covered = tuple(path for scope in scopes for path in scope.coverage_paths)
        if (len(scopes) < 2 or covered != ("owner.py",)
                or any(scope.primary_paths != ("owner.py",) for scope in scopes)
                or any(scope.related_sections > 2 or scope.related_bytes > 120
                       or scope.packet_bytes > 180 for scope in scopes)):
            fail("single-owner context continuation lost coverage or exceeded a shard limit")

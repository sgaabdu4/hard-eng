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
                or any(set(scope.citation_paths) != {"owner.py", "dep.py"} for scope in scopes)
                or any(scope.related_sections > 2 or scope.related_bytes > 120
                       or scope.packet_bytes > 180 for scope in scopes)):
            fail("single-owner context continuation lost coverage or exceeded a shard limit")
    with tempfile.TemporaryDirectory(prefix="he-named-import-shards-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        files = {
            "AGENTS.md": "# Rules\n- Review exact behavior.\n",
            "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
            "DESIGN.md": "# Design\n- UI = none.\n",
            "package.json": '{"name":"fixture"}\n',
            "caller.ts": "export function caller() { return 'before'; }\n",
            "filler.ts": "export const filler = '" + "x" * 24000 + "';\n",
        }
        for relative, content in files.items():
            (root / relative).write_text(content, encoding="utf-8")
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("# Fixture\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.com", "commit", "-q", "-m", "base"], check=True,
        )
        head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        plan.write_text(f"# Fixture\n- base_sha = {head}\n", encoding="utf-8")
        (root / "caller.ts").write_text(
            "import { useFeature } from './useFeature';\n"
            "import { helperFeature } from './AdminSteps.helpers';\n"
            "export function caller() { return useFeature() + helperFeature(); }\n", encoding="utf-8",
        )
        (root / "useFeature.ts").write_text(
            "export function useFeature() { return 'ready'; }\n", encoding="utf-8",
        )
        (root / "AdminSteps.helpers.ts").write_text(
            "export function helperFeature() { return 'helper'; }\n", encoding="utf-8",
        )
        primary = ("caller.ts", "filler.ts", "useFeature.ts", "AdminSteps.helpers.ts")
        scopes = audit_packet.partition_review_scopes(
            root, plan, primary, max_related_sections=8, max_related_bytes=16000,
            max_packet_bytes=6000, full_files=True, planned_unit_id="S-1",
            repository_index=audit_packet.repository_source_index(root),
        )
        covered = tuple(path for scope in scopes for path in scope.coverage_paths)
        packet = "\n".join(scope.packet for scope in scopes)
        owner_proof = all(token in packet for token in (
            "useFeature.ts", "useFeature", "AdminSteps.helpers.ts", "helperFeature",
        ))
        if len(scopes) < 2 or covered != primary or not owner_proof:
            fail("untracked local named-import owner broke deterministic shard coverage")
    with tempfile.TemporaryDirectory(prefix="he-deleted-import-graph-") as temporary:
        root = Path(temporary)
        subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
        files = {
            "AGENTS.md": "# Rules\n- Review exact behavior.\n",
            "PRODUCT.md": "# Product\n- Outcome = fixture.\n",
            "DESIGN.md": "# Design\n- UI = none.\n",
            "caller.ts": (
                "import { ownedValue } from './owner';\n"
                "export function caller() { return ownedValue(); }\n"
            ),
            "owner.ts": "export function ownedValue() { return 'legacy'; }\n",
        }
        for relative, content in files.items():
            (root / relative).write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=Fixture", "-c",
             "user.email=fixture@example.com", "commit", "-q", "-m", "base"], check=True,
        )
        head = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
        ).strip()
        plan = root / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        plan.write_text(f"# Fixture\n- base_sha = {head}\n", encoding="utf-8")
        (root / "caller.ts").unlink()
        (root / "owner.ts").unlink()
        primary = ("caller.ts", "owner.ts")
        scopes = audit_packet.partition_review_scopes(
            root, plan, primary, max_related_sections=8, max_related_bytes=16000,
            max_packet_bytes=64000, full_files=True,
            repository_index=audit_packet.repository_source_index(root),
        )
        packet = "\n".join(scope.packet for scope in scopes)
        covered = tuple(path for scope in scopes for path in scope.coverage_paths)
        if covered != primary or "ownedValue" not in packet:
            fail("planned caller+owner deletion lost its base import graph")

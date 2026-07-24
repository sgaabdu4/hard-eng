#!/usr/bin/env python3
"""Generic regression proof for explicit, token-bound legacy-v4 migration."""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "skills/he/scripts/plan_state.py"


def fail(message: str) -> None:
    raise SystemExit(f"legacy-v4-migration-contracts: FAIL: {message}")


def legacy(repo: Path, slug: str, lifecycle: str = "planning") -> str:
    approved = lifecycle != "planning"
    post_build = lifecycle in {"green", "shipped"}
    stages = (
        "repository,research,feature,flows,ux,contracts,technical,testing,"
        "rollout,slices,consistency,approval"
    )
    axes = (
        "intent-spec:pass,deterministic:pass,tests:pass,review:pass,"
        "security:na,ui-design:na,e2e-runtime:na,docs-context:pass,unknowns:pass"
    )
    values = {
        "state_version": "4", "plan_id": slug, "feature_slug": slug,
        "repository_root": str(repo), "branch": "main", "base_sha": "0" * 40,
        "head_sha": "0" * 40, "updated_at_utc": "2026-01-01T00:00:00Z",
        "lifecycle_status": lifecycle,
        "current_stage": "ship" if post_build else ("build" if approved else "plan"),
        "plan_stage": "repository" if not approved else "none",
        "approved_plan_stages": stages if approved else "none",
        "skipped_plan_stages": "none",
        "stage_status": "complete" if lifecycle == "shipped" else "in-progress",
        "next_action": "Continue safely.",
        "waiting_for": "agent", "plan_approved": "yes" if approved else "no",
        "approved_plan_digest": "sha256:" + "f" * 64 if approved else "none",
        "open_blockers": "none", "open_issues": "none", "open_unknowns": "none",
        "active_slice": "none", "slice_count": "1" if approved else "none",
        "completed_slices": "S-1" if post_build else "none",
        "build_round": "1" if post_build else "0",
        "snapshot_id": "sha256:" + "a" * 64 if post_build else "none",
        "artifact_id": "sha256:" + "b" * 64 if post_build else "none",
        "build_axes": axes if post_build else "none",
        "build_readiness": "100" if post_build else "none",
        "build_evidence": "current" if post_build else "none",
    }
    rows = "\n".join(f"- {key} = {value}" for key, value in values.items())
    return f"# Legacy\n\n## State\n{rows}\n\n## Accepted plan\n- risk_tier = standard\n"


def invoke(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args, "--repo", str(repo)],
        capture_output=True, text=True, check=False,
    )


def main() -> int:
    router = (ROOT / "skills/he/SKILL.md").read_text(encoding="utf-8")
    for anchor in ("migrate-v4", "--expect-token", "`inspect` never auto-migrates",
                   "[legacy-v4.md](references/legacy-v4.md)"):
        if anchor not in router:
            fail(f"migration router documentation missing: {anchor}")
    reference = (ROOT / "skills/he/references/legacy-v4.md").read_text(encoding="utf-8")
    for anchor in ("migrate-v4", "--expect-token", "build-ready/building approved",
                   "explicit migration rejected unchanged", "PLAN/archive unchanged"):
        if anchor not in reference:
            fail(f"migration reference documentation missing: {anchor}")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for anchor in ("### Migrating a legacy v4 plan", "migrate-v4", "--expect-token",
                   "`inspect` never converts a plan automatically", "leaves the PLAN unchanged"):
        if anchor not in readme:
            fail(f"README migration documentation missing: {anchor}")
    with tempfile.TemporaryDirectory(prefix="hard-eng-v4-") as temporary:
        repo = Path(temporary).resolve()
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        path = repo / "features/legacy/PLAN.md"
        path.parent.mkdir(parents=True)
        source = legacy(repo, "legacy")
        path.write_text(source, encoding="utf-8")
        before = path.read_bytes()
        inspected = invoke(repo, "inspect", "--plan", str(path))
        if inspected.returncode != 4 or path.read_bytes() != before:
            fail("inspect auto-migrated or mutated legacy state")
        stale = invoke(repo, "migrate-v4", "--plan", str(path), "--expect-token", "sha256:" + "0" * 64)
        if stale.returncode != 4 or path.read_bytes() != before:
            fail("stale migration token mutated legacy state")
        token = "sha256:" + hashlib.sha256(before).hexdigest()
        migrated = invoke(repo, "migrate-v4", "--plan", str(path), "--expect-token", token)
        if migrated.returncode != 0 or "result=migrated" not in migrated.stdout:
            fail(migrated.stderr.strip() or "valid migration failed")
        archives = tuple(path.parent.glob("PLAN.legacy-v4.*.md"))
        if len(archives) != 1 or archives[0].read_bytes() != before:
            fail("migration did not preserve one byte-exact archive")
        unsupported = repo / "features/unsupported/PLAN.md"
        unsupported.parent.mkdir(parents=True)
        unsupported_source = legacy(repo, "unsupported", "green")
        unsupported.write_text(unsupported_source, encoding="utf-8")
        unsupported_token = "sha256:" + hashlib.sha256(unsupported_source.encode()).hexdigest()
        rejected = invoke(
            repo, "migrate-v4", "--plan", str(unsupported), "--expect-token", unsupported_token
        )
        if (
            rejected.returncode != 4
            or unsupported.read_text(encoding="utf-8") != unsupported_source
            or tuple(unsupported.parent.glob("PLAN.legacy-v4.*.md"))
        ):
            fail("unsupported active legacy state did not fail unchanged")
    print("legacy-v4-migration-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

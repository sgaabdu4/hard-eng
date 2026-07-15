"""Learning-candidate lifecycle boundary regression."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


def check_learning_lifecycle_boundary(module, fail, init_repo, quietly) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-learning-boundary-") as temporary:
        root = Path(temporary)
        init_repo(root)
        result, _ = quietly(module.initialize, str(root), "fixture", None)
        if result != 0:
            fail("learning boundary fixture initialization failed")
        plan = root / "features/fixture/PLAN.md"
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        text = module.replace_learning_candidates(
            plan.read_text(encoding="utf-8"),
            {"L-1": (
                "L-1", "false-gate", "build audit", "Verified: open prevention gap",
                "missing boundary", "$he-build", "green transition rejection", "pending", "open",
            )},
        )
        text += "\n## Slices\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n"
        common = {
            "approved_plan_stages": ",".join(module.PLAN_STAGES), "plan_stage": "none",
            "plan_approved": "yes", "current_stage": "ship", "active_slice": "none",
            "approved_plan_digest": "sha256:" + "f" * 64,
            "slice_count": "1", "completed_slices": "S-1", "build_round": "1",
            "snapshot_id": "sha256:" + "1" * 64, "artifact_id": "sha256:" + "2" * 64,
            "build_axes": "intent-spec:pass,deterministic:pass,tests:pass,review:pass,security:pass,ui-design:na,e2e-runtime:na,docs-context:pass,unknowns:pass",
            "build_readiness": "100", "build_evidence": "current", "head_sha": head,
            "base_sha": head, "repository_root": str(root), "branch": "main",
        }
        for lifecycle, stage_status in (("green", "pending"), ("shipping", "in-progress")):
            candidate = module.replace_state(
                text, {**common, "lifecycle_status": lifecycle, "stage_status": stage_status}
            )
            candidate = candidate.replace(
                f"- approved_plan_digest = {common['approved_plan_digest']}",
                f"- approved_plan_digest = {module.approved_plan_digest(candidate)}",
            )
            try:
                module.validate_document(plan, candidate)
            except module.PlanStateError as error:
                fail(f"{lifecycle} document rejected post-green learning capture: {error}")
        shipped = module.replace_state(
            text, {**common, "lifecycle_status": "shipped", "stage_status": "complete"}
        )
        shipped = shipped.replace(
            f"- approved_plan_digest = {common['approved_plan_digest']}",
            f"- approved_plan_digest = {module.approved_plan_digest(shipped)}",
        )
        try:
            module.validate_document(plan, shipped)
        except module.PlanStateError:
            return
        fail("shipped document accepted an open learning candidate")

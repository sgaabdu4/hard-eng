"""Regression proof for stale-build checkpoint replan precedence."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from admission_regression_check import candidate_plan_text


def check_stale_build_replan_checkpoint(module, fail, init_repo, quietly) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-stale-replan-") as temporary:
        parent = Path(temporary)

        def fixture(name: str):
            root = parent / name
            init_repo(root)
            head = subprocess.check_output(
                ["git", "-C", str(root), "rev-parse", "HEAD"], text=True,
            ).strip()
            plan = root / "features/fixture/PLAN.md"
            plan.parent.mkdir(parents=True)
            plan.write_text(
                candidate_plan_text(root, head, module.repository_snapshot_id(root)),
                encoding="utf-8",
            )
            state = module.parse_state(plan.read_text(encoding="utf-8"))
            module.write_approval_receipt(root, state)
            (root / "owner.py").write_text(
                "legitimate active-slice correction\n", encoding="utf-8",
            )
            receipt = module.approval_receipt_path(root, state["plan_id"])
            return root, plan, receipt

        reset = [
            "lifecycle_status=planning",
            "current_stage=plan",
            "plan_stage=contracts",
            "approved_plan_stages=repository,research,feature,flows,ux",
            "skipped_plan_stages=none",
            "stage_status=in-progress",
            "next_action=Repair persisted contract.",
            "waiting_for=agent",
            "plan_approved=no",
            "active_slice=none",
            "slice_count=none",
            "completed_slices=none",
            "build_round=0",
            "snapshot_id=none",
            "artifact_id=none",
            "build_axes=none",
            "build_readiness=none",
            "build_evidence=none",
        ]
        root, plan, receipt = fixture("valid")
        result, output = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(plan.read_text(encoding="utf-8")),
            reset,
            [["issue", "Persisted contract defect", "Build contract unsafe", "agent",
              "Reopen contracts"]],
            [],
            [],
        )
        state = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        issue = module.parse_active_items(plan.read_text(encoding="utf-8")).get("I-1")
        if (
            result != 0
            or "result=checkpointed" not in output
            or state["lifecycle_status"] != "planning"
            or state["current_stage"] != "plan"
            or state["plan_stage"] != "contracts"
            or state["approved_plan_stages"] != "repository,research,feature,flows,ux"
            or state["plan_approved"] != "no"
            or state["approved_plan_digest"] != "none"
            or any(state[key] != "none" for key in (
                "active_slice", "slice_count", "completed_slices", "snapshot_id",
                "artifact_id", "build_axes", "build_readiness", "build_evidence",
            ))
            or state["build_round"] != "0"
            or state["open_issues"] != "I-1"
            or issue is None
            or issue[6] != "open"
            or receipt.exists()
        ):
            fail("explicit stale-build replan reset did not win atomically")

        root, plan, receipt = fixture("ordinary")
        approval_before = receipt.read_bytes()
        actual_snapshot = module.repository_snapshot_id(root)
        actual_artifact = module.repository_artifact_id(root)
        result, _ = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(plan.read_text(encoding="utf-8")),
            ["next_action=Caller requested ordinary checkpoint."],
            [],
            [],
            [],
        )
        state = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        if (
            result != 0
            or state["lifecycle_status"] != "building"
            or state["current_stage"] != "build"
            or state["plan_stage"] != "none"
            or state["snapshot_id"] != actual_snapshot
            or state["artifact_id"] != actual_artifact
            or state["next_action"] != "Repository snapshot changed; rerun final build convergence."
            or state["build_evidence"] != "stale"
            or state["plan_approved"] != "yes"
            or not receipt.is_file()
            or receipt.read_bytes() != approval_before
        ):
            fail("ordinary stale-build checkpoint bypassed snapshot reconciliation")

        root, plan, receipt = fixture("partial")
        plan_before = plan.read_bytes()
        approval_before = receipt.read_bytes()
        result, _ = quietly(
            module.checkpoint,
            str(root),
            str(plan),
            module.checkpoint_token(plan.read_text(encoding="utf-8")),
            ["lifecycle_status=planning"],
            [],
            [],
            [],
        )
        if (
            result != 4
            or plan.read_bytes() != plan_before
            or not receipt.is_file()
            or receipt.read_bytes() != approval_before
        ):
            fail("partial stale-build replan did not fail closed atomically")

"""Regression proof for atomic building-state HEAD reconciliation."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from admission_regression_check import candidate_plan_text


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def fixture(module, root: Path) -> Path:
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "f@x")
    (root / "owner.py").write_text("VALUE = 1\n", encoding="utf-8")
    git(root, "add", "owner.py")
    git(root, "commit", "-q", "-m", "base")
    head = git(root, "rev-parse", "HEAD")
    plan = root / "features/fixture/PLAN.md"
    plan.parent.mkdir(parents=True)
    text = candidate_plan_text(
        root, head, module.repository_snapshot_id(root), active="final", completed="S-1,S-2"
    ).replace(
        "- artifact_id = sha256:" + "0" * 64,
        f"- artifact_id = {module.repository_artifact_id(root)}",
    )
    plan.write_text(text, encoding="utf-8")
    module.write_approval_receipt(root, module.parse_state(text))
    return plan


def check_build_head_reconciliation(module, fail, quietly) -> None:
    with tempfile.TemporaryDirectory(prefix="he-build-head-reconcile-") as temporary:
        root = Path(temporary)
        plan = fixture(module, root)
        original_product = (root / "owner.py").read_bytes()
        (root / "owner.py").write_text("VALUE = 2\n", encoding="utf-8")
        git(root, "add", "owner.py")
        git(root, "commit", "-q", "-m", "accepted correction")
        (root / "caller.py").write_text("from owner import VALUE\n", encoding="utf-8")
        git(root, "add", "caller.py")
        git(root, "commit", "-q", "-m", "connected correction")
        stale_result, stale_output = quietly(module.inspect, str(root), str(plan))
        if stale_result != 5 or "recovery_action=reconcile-build-head" not in stale_output:
            fail("stale building HEAD did not emit its bounded recovery action")
        reconciled = subprocess.run(
            [sys.executable, str(Path(module.__file__)), "reconcile-build-head",
             "--repo", str(root), "--plan", str(plan), "--expect-token",
             module.checkpoint_token(plan.read_text(encoding="utf-8"))],
            capture_output=True, text=True, check=False,
        )
        state = module.validate_document(plan, plan.read_text(encoding="utf-8"))
        inspected, inspect_output = quietly(module.inspect, str(root), str(plan))
        if (
            reconciled.returncode != 0
            or "result=reconciled" not in reconciled.stdout
            or inspected != 0
            or "result=selected" not in inspect_output
            or state["head_sha"] != git(root, "rev-parse", "HEAD")
            or state["snapshot_id"] != module.repository_snapshot_id(root)
            or state["artifact_id"] != module.repository_artifact_id(root)
            or state["lifecycle_status"] != "building"
            or state["active_slice"] != "final"
            or state["completed_slices"] != "S-1,S-2"
            or state["build_evidence"] != "stale"
            or any(part.rsplit(":", 1)[-1] != "pending" for part in state["build_axes"].split(","))
            or (root / "owner.py").read_bytes() != original_product.replace(b"1", b"2")
            or (root / "caller.py").read_text(encoding="utf-8") != "from owner import VALUE\n"
        ):
            fail("building HEAD reconciliation lost state, evidence invalidation, or product bytes")

    with tempfile.TemporaryDirectory(prefix="he-build-head-plan-commit-") as temporary:
        root = Path(temporary)
        plan = fixture(module, root)
        git(root, "add", str(plan.relative_to(root)))
        git(root, "commit", "-q", "-m", "invalid PLAN commit")
        before = plan.read_bytes()
        result, output = quietly(
            module.reconcile_build_head,
            str(root), str(plan), module.checkpoint_token(plan.read_text(encoding="utf-8")),
        )
        if result != 4 or "committed PLAN" not in output or plan.read_bytes() != before:
            fail("building HEAD reconciliation accepted committed PLAN drift")

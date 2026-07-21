"""Regression proof that approved PLAN deletion fails lifecycle inspection."""

from __future__ import annotations

import subprocess
from pathlib import Path


def check_orphaned_plan_receipt(module, fail, init_repo, quietly) -> None:
    import tempfile
    from admission_regression_check import candidate_plan_text

    with tempfile.TemporaryDirectory(prefix="hard-eng-orphaned-plan-") as temporary:
        fixture = Path(temporary)
        root = fixture / "source"
        linked = fixture / "linked"
        init_repo(root)
        subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "-q", "--detach", str(linked)],
            check=True,
        )
        head = subprocess.check_output(
            ["git", "-C", str(linked), "rev-parse", "HEAD"], text=True,
        ).strip()
        plan = linked / "features/fixture/PLAN.md"
        plan.parent.mkdir(parents=True)
        text = candidate_plan_text(linked, head, module.repository_snapshot_id(linked))
        plan.write_text(text, encoding="utf-8")
        module.write_approval_receipt(linked, module.parse_state(text))
        result, output = quietly(module.inspect, str(root), None)
        if result != 2 or "result=none" not in output:
            fail("approved PLAN in a linked worktree looked orphaned")
        plan.unlink()
        result, output = quietly(module.inspect, str(root), None)
        if result != 4 or "orphaned approved PLAN receipt: fixture" not in output:
            fail("approved PLAN deletion became no active plan")

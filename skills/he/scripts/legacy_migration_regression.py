"""Regression proof for canonical v3 to v4 PLAN migration."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

from plan_migration import remove_digest_field


def as_v3(text: str) -> str:
    text = text.replace("- state_version = 4", "- state_version = 3", 1)
    return re.sub(r"(?m)^- approved_plan_digest = [^\n]+\n?", "", text, count=1)


def assert_preserved(before: str, after: str, fail) -> None:
    restored = after.replace("- state_version = 4", "- state_version = 3", 1)
    restored = remove_digest_field(restored)
    if restored != before:
        fail("legacy migration changed accepted PLAN content")


def check_legacy_migration(module, fail, init_repo, quietly) -> None:
    with tempfile.TemporaryDirectory(prefix="hard-eng-state-migration-") as temporary:
        root = Path(temporary)
        init_repo(root)
        result, _ = quietly(module.initialize, str(root), "fixture", None)
        if result != 0:
            fail("migration fixture initialization failed")
        plan = root / "features/fixture/PLAN.md"
        legacy = as_v3(plan.read_text(encoding="utf-8")) + (
            "\n## Accepted plan\nPreserve this.\n- plan_approved = prose-only\n"
            "- approved_plan_digest = prose-only\n"
        )
        plan.write_text(legacy, encoding="utf-8")
        result, output = quietly(module.inspect, str(root), str(plan))
        if result != 4 or "missing keys: approved_plan_digest" not in output:
            fail("legacy v3 reproduction did not fail at the compatibility boundary")
        result, output = quietly(module.migrate_state, str(root), str(plan))
        if result != 0 or "result=migrated" not in output:
            fail("legacy v3 PLAN migration failed: " + output.strip())
        migrated = plan.read_text(encoding="utf-8")
        assert_preserved(legacy, migrated, fail)
        state = module.validate_document(plan, migrated)
        if state["state_version"] != "4" or state["approved_plan_digest"] != "none":
            fail("unapproved legacy PLAN migration produced wrong v4 state")
        result, _ = quietly(module.inspect, str(root), str(plan))
        if result != 0:
            fail("migrated legacy PLAN did not inspect")
        before_repeat = plan.read_bytes()
        result, _ = quietly(module.migrate_state, str(root), str(plan))
        if result != 4 or plan.read_bytes() != before_repeat:
            fail("repeated migration did not reject without mutation")

        result, _ = quietly(module.initialize, str(root), "approved", None)
        if result != 0:
            fail("approved migration fixture initialization failed")
        approved_plan = root / "features/approved/PLAN.md"
        approved = module.replace_state(
            approved_plan.read_text(encoding="utf-8"),
            {
                "lifecycle_status": "build-ready", "current_stage": "build",
                "plan_stage": "none", "approved_plan_stages": ",".join(module.PLAN_STAGES),
                "stage_status": "pending", "next_action": "Build S-1.",
                "plan_approved": "yes", "approved_plan_digest": "sha256:" + "f" * 64,
                "slice_count": "1",
            },
        )
        approved += "\n## Slices\n| ID | Outcome |\n|---|---|\n| S-1 | Fixture |\n"
        approved = module.replace_state(
            approved, {"approved_plan_digest": module.approved_plan_digest(approved)}
        )
        module.validate_document(approved_plan, approved)
        approved_legacy = as_v3(approved)
        approved_plan.write_text(approved_legacy, encoding="utf-8")
        result, output = quietly(module.migrate_state, str(root), str(approved_plan))
        if result != 0:
            fail("approved legacy PLAN migration failed: " + output.strip())
        approved_migrated = approved_plan.read_text(encoding="utf-8")
        assert_preserved(approved_legacy, approved_migrated, fail)
        approved_state = module.validate_document(approved_plan, approved_migrated)
        module.validate_approval_receipt(root, approved_state)

        result, _ = quietly(module.initialize, str(root), "rollback", None)
        if result != 0:
            fail("migration rollback fixture initialization failed")
        rollback_plan = root / "features/rollback/PLAN.md"
        rollback_plan.write_text(as_v3(rollback_plan.read_text(encoding="utf-8")), encoding="utf-8")
        rollback_before = rollback_plan.read_bytes()
        original_write = module.repo_write
        module.repo_write = lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("injected"))
        try:
            result, _ = quietly(module.migrate_state, str(root), str(rollback_plan))
        finally:
            module.repo_write = original_write
        if result != 4 or rollback_plan.read_bytes() != rollback_before:
            fail("migration write failure changed legacy PLAN")

        result, _ = quietly(module.initialize, str(root), "post-replace", None)
        if result != 0:
            fail("post-replace rollback fixture initialization failed")
        post_plan = root / "features/post-replace/PLAN.md"
        post_plan.write_text(as_v3(post_plan.read_text(encoding="utf-8")), encoding="utf-8")
        post_before = post_plan.read_bytes()
        calls = 0
        def fail_after_replace(*args, **kwargs):
            nonlocal calls
            calls += 1
            original_write(*args, **kwargs)
            if calls == 1:
                raise OSError("injected post-replace failure")
        module.repo_write = fail_after_replace
        try:
            result, _ = quietly(module.migrate_state, str(root), str(post_plan))
        finally:
            module.repo_write = original_write
        if result != 4 or post_plan.read_bytes() != post_before:
            fail("post-replace migration failure did not restore legacy PLAN")

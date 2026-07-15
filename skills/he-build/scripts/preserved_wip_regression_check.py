#!/usr/bin/env python3
"""Regression proof for atomic admission of approved preserved WIP."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from admission_regression_check import candidate_fixture, git


def canonical_patch(root: Path, paths: tuple[str, ...]) -> bytes:
    with tempfile.TemporaryDirectory(prefix="he-preserved-index-") as temporary:
        index = Path(temporary) / "index"
        environment = {**os.environ, "GIT_INDEX_FILE": str(index)}
        subprocess.run(
            ["git", "-C", str(root), "read-tree", "HEAD"], env=environment,
            check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(root), "add", "--", *paths], env=environment,
            check=True, capture_output=True,
        )
        return subprocess.check_output(
            ["git", "-C", str(root), "diff", "--cached", "--binary", "--full-index",
             "--no-ext-diff", "--no-textconv", "HEAD", "--", *paths],
            env=environment,
        )


def update_plan(module, root: Path, plan: Path, *, active: str, completed: str) -> None:
    from plan_state import approved_plan_digest, parse_state, write_approval_receipt

    text = plan.read_text(encoding="utf-8")
    text = re.sub(r"(?m)^- active_slice = .+$", f"- active_slice = {active}", text)
    text = re.sub(r"(?m)^- completed_slices = .+$", f"- completed_slices = {completed}", text)
    text = re.sub(r"(?m)^- snapshot_id = .+$", f"- snapshot_id = {module.snapshot_id(root)}", text)
    current = parse_state(text)["approved_plan_digest"]
    text = text.replace(current, approved_plan_digest(text))
    plan.write_text(text, encoding="utf-8")
    write_approval_receipt(root, parse_state(text))


def check_preserved_wip_regressions(module, fail) -> None:
    with tempfile.TemporaryDirectory(prefix="he-preserved-wip-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch_s1 = candidate_fixture(root, module.snapshot_id)
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        (root / "caller.py").write_text(
            "from owner import public_api\nvalue = public_api('next')\n", encoding="utf-8",
        )
        support = root / "features/fixture/NOTES.md"
        support.write_text("# Accepted evidence\n", encoding="utf-8")
        plan.write_text(
            plan.read_text(encoding="utf-8")
            + "\n## Context\n- evidence = [NOTES.md](./NOTES.md)\n",
            encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-1", completed="none")
        patch_s2 = root.parent / "candidate-s2-preserved.patch"
        patch_s2.write_bytes(canonical_patch(root, ("caller.py",)))
        initial = module.snapshot_id(root)

        mismatch = patch_s1.read_bytes().replace(b"value.strip()", b"value.upper()")
        try:
            module.candidate_admission_report(root, plan, mismatch, "S-1")
        except (module.AuditError, module.CandidateError) as exc:
            if (
                module.admission_error_detail(exc) != {
                    "code": "INVALID_ACCUMULATED_STATE",
                    "reason": "PRESERVED_BYTES_MISMATCH",
                }
                or module.snapshot_id(root) != initial
            ):
                fail("preserved-byte mismatch lacked structured immutable rejection")
        else:
            fail("preserved-WIP admission accepted candidate bytes absent from the checkout")

        report_s1 = module.candidate_admission_report(root, plan, patch_s1.read_bytes(), "S-1")
        if (
            report_s1["result"] != "pass"
            or report_s1.get("candidateState") != "preserved-wip"
            or report_s1.get("preservedWipPathCount") != 3
            or module.snapshot_id(root) != initial
        ):
            fail("approved preserved WIP did not admit immutably")

        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        before_files = {path: (root / path).read_bytes() for path in ("caller.py", support.relative_to(root).as_posix())}
        applied_s1 = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch_s1), "--unit", "S-1",
             "--expect-base", report_s1["baseSnapshotId"],
             "--expect-patch", report_s1["candidateDigest"],
             "--expect-candidate", report_s1["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        receipt_s1 = json.loads(applied_s1.stdout) if applied_s1.stdout else {}
        if (
            applied_s1.returncode != 0
            or receipt_s1.get("candidateState") != "preserved-wip"
            or git(root, "diff", "--cached", "--name-only") != "owner.py"
            or any((root / path).read_bytes() != content for path, content in before_files.items())
        ):
            fail("preserved-WIP apply did not stage only the admitted active slice")

        update_plan(module, root, plan, active="S-2", completed="S-1")
        report_s2 = module.candidate_admission_report(root, plan, patch_s2.read_bytes(), "S-2")
        applied_s2 = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch_s2), "--unit", "S-2",
             "--expect-base", report_s2["baseSnapshotId"],
             "--expect-patch", report_s2["candidateDigest"],
             "--expect-candidate", report_s2["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        if (
            applied_s2.returncode != 0
            or git(root, "diff", "--cached", "--name-only").splitlines() != ["caller.py", "owner.py"]
            or support.read_text(encoding="utf-8") != "# Accepted evidence\n"
        ):
            fail("preserved WIP did not advance through the completed-slice prefix")

    with tempfile.TemporaryDirectory(prefix="he-preserved-negative-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        (root / "caller.py").write_text("unapproved future bytes\n", encoding="utf-8")
        (root / "outside.txt").write_text("unapproved\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-1", completed="none")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "UNAPPROVED_PRESERVED_PATH",
                "path": "outside.txt",
            }:
                fail("unapproved preserved WIP omitted structured path evidence")
        else:
            fail("preserved-WIP admission accepted unrelated repository dirt")

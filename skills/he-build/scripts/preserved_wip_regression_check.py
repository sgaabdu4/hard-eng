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
        raw_index = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "--git-path", "index"], text=True,
        ).strip()
        source_index = Path(raw_index)
        if not source_index.is_absolute():
            source_index = root / source_index
        index.write_bytes(source_index.read_bytes())
        base_tree = subprocess.check_output(
            ["git", "-C", str(root), "write-tree"], env=environment, text=True,
        ).strip()
        subprocess.run(
            ["git", "-C", str(root), "add", "--", *paths], env=environment,
            check=True, capture_output=True,
        )
        return subprocess.check_output(
            ["git", "-C", str(root), "diff", "--cached", "--binary", "--full-index",
             "--no-ext-diff", "--no-textconv", base_tree, "--", *paths],
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
        support = root / "features/fixture/NOTES.md"
        support.write_text("# Accepted evidence\n", encoding="utf-8")
        plan.write_text(
            plan.read_text(encoding="utf-8")
            + "\n## Context\n- evidence = [NOTES.md](./NOTES.md)\n",
            encoding="utf-8",
        )
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "planned_paths = owner.py", "planned_paths = owner.py, DESIGN.md",
            ),
            encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-1", completed="none")
        initial = module.snapshot_id(root)

        report_s1 = module.candidate_admission_report(root, plan, patch_s1.read_bytes(), "S-1")
        if (
            report_s1["result"] != "pass"
            or report_s1.get("candidateState") != "preserved-wip"
            or report_s1.get("activeAccumulatedPathCount") != 0
            or report_s1.get("preservedWipPathCount") != 2
            or module.snapshot_id(root) != initial
        ):
            fail("partial active WIP required clean future-slice paths")

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

        (root / "DESIGN.md").write_text("# Design\n- UI = completed S-1.\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-1", completed="none")
        patch_s1_round2 = root.parent / "candidate-s1-round2.patch"
        patch_s1_round2.write_bytes(canonical_patch(root, ("DESIGN.md",)))
        report_s1_round2 = module.candidate_admission_report(
            root, plan, patch_s1_round2.read_bytes(), "S-1",
        )
        if (
            report_s1_round2["result"] != "pass"
            or report_s1_round2.get("accumulatedPathCount") != 0
            or report_s1_round2.get("activeAccumulatedPathCount") != 1
            or report_s1_round2.get("candidateState") != "preserved-wip"
        ):
            fail("second active-slice candidate rejected prior active accumulation")
        applied_s1_round2 = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch_s1_round2), "--unit", "S-1",
             "--expect-base", report_s1_round2["baseSnapshotId"],
             "--expect-patch", report_s1_round2["candidateDigest"],
             "--expect-candidate", report_s1_round2["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        receipt_s1_round2 = json.loads(applied_s1_round2.stdout) if applied_s1_round2.stdout else {}
        if (
            applied_s1_round2.returncode != 0
            or receipt_s1_round2.get("activeAccumulatedPathCount") != 1
            or git(root, "diff", "--cached", "--name-only").splitlines() != ["DESIGN.md", "owner.py"]
            or support.read_text(encoding="utf-8") != "# Accepted evidence\n"
        ):
            fail("second active-slice apply did not preserve prior active accumulation")

        (root / "caller.py").write_text(
            "from owner import public_api\nvalue = public_api('next')\n", encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-2", completed="S-1")
        patch_s2 = root.parent / "candidate-s2-preserved.patch"
        patch_s2.write_bytes(canonical_patch(root, ("caller.py",)))
        git(root, "restore", "--staged", "DESIGN.md")
        update_plan(module, root, plan, active="S-2", completed="S-1")
        try:
            module.candidate_admission_report(root, plan, patch_s2.read_bytes(), "S-2")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "COMPLETED_STAGED_PATH_MISSING",
                "path": "DESIGN.md",
            }:
                fail("missing completed-slice staging lacked structured rejection")
        else:
            fail("preserved-WIP admission accepted incomplete completed-slice staging")
        git(root, "add", "DESIGN.md")
        update_plan(module, root, plan, active="S-2", completed="S-1")
        completed_owner = (root / "owner.py").read_bytes()
        (root / "owner.py").write_text("completed slice drift\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-2", completed="S-1")
        try:
            module.candidate_admission_report(root, plan, patch_s2.read_bytes(), "S-2")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "COMPLETED_PATH_DRIFT",
                "path": "owner.py",
            }:
                fail("completed-prefix drift lacked structured immutable rejection")
        else:
            fail("preserved-WIP admission accepted completed-prefix drift")
        (root / "owner.py").write_bytes(completed_owner)
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
            or git(root, "diff", "--cached", "--name-only").splitlines() != ["DESIGN.md", "caller.py", "owner.py"]
            or support.read_text(encoding="utf-8") != "# Accepted evidence\n"
        ):
            fail("preserved WIP did not advance through the completed-slice prefix")

    with tempfile.TemporaryDirectory(prefix="he-preserved-overlap-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch_s1 = candidate_fixture(root, module.snapshot_id)
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "planned_paths = caller.py", "planned_paths = owner.py",
            ),
            encoding="utf-8",
        )
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-1", completed="none")
        report_s1 = module.candidate_admission_report(root, plan, patch_s1.read_bytes(), "S-1")
        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        applied_s1 = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch_s1), "--unit", "S-1",
             "--expect-base", report_s1["baseSnapshotId"],
             "--expect-patch", report_s1["candidateDigest"],
             "--expect-candidate", report_s1["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        if applied_s1.returncode != 0:
            fail("overlapping manifest fixture failed first slice apply")
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip().upper()\n", encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-2", completed="S-1")
        patch_s2 = root.parent / "candidate-overlap-s2.patch"
        patch_s2.write_bytes(canonical_patch(root, ("owner.py",)))
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
            report_s2["result"] != "pass"
            or applied_s2.returncode != 0
            or "strip().upper()" not in (root / "owner.py").read_text(encoding="utf-8")
        ):
            fail("later slice could not increment an overlapping completed path")

    with tempfile.TemporaryDirectory(prefix="he-preserved-baseline-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        baseline_product = b"# Product\n- Outcome = unrelated user edit.\n"
        (root / "PRODUCT.md").write_bytes(baseline_product)
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "planned_paths = owner.py", "planned_paths = owner.py, DESIGN.md",
            ),
            encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-1", completed="none")
        report = module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        baseline_receipt = root / ".git/hard-eng/build-baselines/fixture.json"
        if (
            report["result"] != "pass"
            or report.get("preservedWipPathCount") != 2
            or (root / "PRODUCT.md").read_bytes() != baseline_product
            or (baseline_receipt.stat().st_mode & 0o777) != 0o600
            or (baseline_receipt.parent.stat().st_mode & 0o777) != 0o700
        ):
            fail("exact pre-build unrelated baseline did not coexist with active WIP")
        helper = Path(module.__file__).with_name("apply_admitted_patch.py")
        applied = subprocess.run(
            [sys.executable, str(helper), "--repo", str(root), "--plan", str(plan),
             "--patch", str(patch), "--unit", "S-1",
             "--expect-base", report["baseSnapshotId"],
             "--expect-patch", report["candidateDigest"],
             "--expect-candidate", report["candidateSnapshotId"]],
            capture_output=True, text=True, check=False,
        )
        if (
            applied.returncode != 0
            or git(root, "diff", "--cached", "--name-only") != "owner.py"
            or (root / "PRODUCT.md").read_bytes() != baseline_product
        ):
            fail("candidate apply staged or changed pre-build unrelated baseline")
        (root / "DESIGN.md").write_text("# Design\n- UI = next active round.\n", encoding="utf-8")
        patch_round2 = root.parent / "candidate-baseline-round2.patch"
        patch_round2.write_bytes(canonical_patch(root, ("DESIGN.md",)))
        (root / "PRODUCT.md").write_text("changed unrelated bytes\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-1", completed="none")
        try:
            module.candidate_admission_report(root, plan, patch_round2.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "PREBUILD_BASELINE_BYTES_DRIFT",
                "path": "PRODUCT.md",
            }:
                fail("unrelated baseline byte drift lacked structured rejection")
        else:
            fail("preserved-WIP admission accepted unrelated baseline byte drift")

    with tempfile.TemporaryDirectory(prefix="he-preserved-negative-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        (root / "caller.py").write_text("unapproved future bytes\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-1", completed="none")
        if module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")["result"] != "pass":
            fail("initial preserved WIP did not bind an empty unrelated baseline")
        (root / "outside.txt").write_text("unapproved\n", encoding="utf-8")
        update_plan(module, root, plan, active="S-1", completed="none")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "PREBUILD_BASELINE_PATH_SET_DRIFT",
                "path": "outside.txt",
            }:
                fail("new unrelated dirt omitted baseline path-set evidence")
        else:
            fail("preserved-WIP admission accepted new unrelated repository dirt")

    with tempfile.TemporaryDirectory(prefix="he-preserved-future-staged-") as temporary:
        root = Path(temporary).resolve() / "delivery"
        plan, patch = candidate_fixture(root, module.snapshot_id)
        (root / "owner.py").write_text(
            "def public_api(value):\n    return value.strip()\n", encoding="utf-8",
        )
        update_plan(module, root, plan, active="S-1", completed="none")
        if module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")["result"] != "pass":
            fail("initial candidate did not bind staged-path baseline")
        (root / "caller.py").write_text("future staged bytes\n", encoding="utf-8")
        git(root, "add", "caller.py")
        update_plan(module, root, plan, active="S-1", completed="none")
        try:
            module.candidate_admission_report(root, plan, patch.read_bytes(), "S-1")
        except (module.AuditError, module.CandidateError) as exc:
            if module.admission_error_detail(exc) != {
                "code": "INVALID_ACCUMULATED_STATE",
                "reason": "STAGED_PATH_OUTSIDE_PREFIX_OR_ACTIVE",
                "path": "caller.py",
            }:
                fail("future-slice staging lacked structured immutable rejection")
        else:
            fail("preserved-WIP admission accepted staged future-slice bytes")

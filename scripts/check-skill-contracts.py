#!/usr/bin/env python3
"""Repository contract entrypoint for lifecycle and deterministic safety checks."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fast_feature_loop_contracts import check_fast_feature_loop_contract


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> None:
    print(f"skill-contracts: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_plan_state_contract() -> None:
    path = ROOT / "skills/he/scripts/plan_state.py"
    spec = importlib.util.spec_from_file_location("hard_eng_plan_state", path)
    if spec is None or spec.loader is None:
        fail("cannot load plan_state.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    required_fields = {
        "state_version",
        "plan_id",
        "lifecycle_status",
        "approval_status",
        "approval_fingerprint",
        "approval_provenance",
        "green_artifact",
        "active_slice",
        "completed_slices",
        "next_action",
        "replan_reason",
    }
    actual_fields = set(getattr(module, "STATE_KEYS", ()))
    if actual_fields != required_fields:
        fail(f"lean PLAN state fields changed: {sorted(actual_fields)!r}")


def run(command: tuple[str, ...], label: str) -> tuple[str, subprocess.CompletedProcess[str]]:
    return label, subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)


def check_external_contracts() -> None:
    contracts = (
        ("Feature Brief state contract", (sys.executable, "skills/he-plan/scripts/check.py")),
        ("legacy-v4 migration contract", (sys.executable, "scripts/legacy-v4-migration-contracts.py")),
        ("build-stage contract", (sys.executable, "skills/he-build/scripts/check.py")),
        ("ship-stage contract", (sys.executable, "skills/he-ship/scripts/check.py")),
        ("visual evidence contract", (sys.executable, "skills/e2e/scripts/visual_evidence_regression_check.py")),
        ("Dart Decimate contract", (sys.executable, "skills/deterministic-checks/scripts/dart_decimate_gate_regression_check.py")),
        ("context-document structure", (sys.executable, "scripts/context-docs-contracts.py")),
        ("worktree readiness", (sys.executable, "scripts/worktree-readiness-contracts.py")),
        ("route resources", (sys.executable, "scripts/route_resource_contracts.py")),
        ("global worktree hook fixture", ("scripts/git-hooks/test.sh",)),
        ("worktree policy contract", (sys.executable, "scripts/worktree-policy-contract-check.py")),
        ("setup contract", (sys.executable, "scripts/setup-contract-check.py")),
        (
            "bounded command contract",
            (sys.executable, "skills/deterministic-checks/scripts/bounded_run_regression_check.py"),
        ),
        (
            "Appwrite ID allocation contract",
            ("node", "--test", "skills/appwrite-backend/scripts/skill-safety-contract.test.mjs"),
        ),
    )
    with ThreadPoolExecutor(max_workers=min(4, len(contracts))) as pool:
        results = tuple(
            pool.map(lambda contract: run(contract[1], contract[0]), contracts)
        )
    for label, result in results:
        if result.returncode != 0:
            fail(result.stderr.strip() or result.stdout.strip() or f"{label} failed")
        if result.stdout.strip():
            print(result.stdout.strip())


def main() -> int:
    check_fast_feature_loop_contract(ROOT, fail)
    check_plan_state_contract()
    check_external_contracts()
    print("skill-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

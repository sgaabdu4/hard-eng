#!/usr/bin/env python3
"""Repository contract entrypoint for lifecycle and deterministic safety checks."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn

from fast_feature_loop_contracts import check_fast_feature_loop_contract


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
GIT_ENV_SCRIPTS = ROOT / "skills/deterministic-checks/scripts"
if str(GIT_ENV_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(GIT_ENV_SCRIPTS))

from git_env import scrub_environ
from source_tree_coordination import atomic_json, git_private_path, tree_fingerprint
scrub_environ()
CACHE_SCHEMA = 1


def runtime_identity() -> dict[str, object]:
    def file_identity(executable: str) -> dict[str, object]:
        path = Path(executable).resolve()
        metadata = path.stat()
        return {"path": str(path), "mtime_ns": metadata.st_mtime_ns, "size": metadata.st_size}

    identity: dict[str, object] = {}
    for name in ("bash", "git", "node", "npm", "perl", "python3", "sh", "ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        identity[name] = file_identity(executable) if executable else None
    identity["current_python"] = file_identity(sys.executable)
    return identity


def proof_identity() -> tuple[Path, dict[str, object]]:
    return git_private_path(ROOT, "hard-eng-contracts-v1.json"), {
        "schema_version": CACHE_SCHEMA,
        "repository": str(ROOT.resolve()),
        "tree_digest": tree_fingerprint(ROOT, deadline=time.monotonic() + 120),
        "runtimes": runtime_identity(),
    }


def reusable(path: Path, expected: dict[str, object]) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")) == expected
    except (OSError, ValueError):
        return False


def fail(message: str) -> NoReturn:
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
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return label, subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False, env=env
    )


def check_external_contracts() -> None:
    contracts = (
        ("doc contracts", (sys.executable, "scripts/doc_contracts.py")),
        (
            "operating contracts",
            (sys.executable, "scripts/operating_contracts_regression.py"),
        ),
        ("Feature Brief state contract", (sys.executable, "skills/he-plan/scripts/check.py")),
        (
            "terminal lifecycle excludes",
            (sys.executable, "skills/he/scripts/lifecycle_excludes_regression.py"),
        ),
        ("ship-stage contract", (sys.executable, "skills/he-ship/scripts/check.py")),
        ("visual evidence contract", (sys.executable, "skills/e2e/scripts/visual_evidence_regression_check.py")),
        ("Dart Decimate contract", (sys.executable, "skills/deterministic-checks/scripts/dart_decimate_gate_regression_check.py")),
        ("project gate contract", (sys.executable, "skills/deterministic-checks/scripts/project_gate_regression_check.py")),
        (
            "source-tree coordination contract",
            (sys.executable, "skills/deterministic-checks/scripts/source_tree_coordination_regression_check.py"),
        ),
        (
            "external CLI restore contract",
            (
                sys.executable,
                "skills/deterministic-checks/scripts/external_cli_restore_regression_check.py",
            ),
        ),
        (
            "Git environment cache contract",
            (
                sys.executable,
                "skills/deterministic-checks/scripts/git_env_cache_regression_check.py",
            ),
        ),
        (
            "structured tool output contract",
            (
                sys.executable,
                "skills/deterministic-checks/scripts/structured_output_regression_check.py",
            ),
        ),
        ("slice gate contract", (sys.executable, "skills/deterministic-checks/scripts/slice_gate_regression_check.py")),
        (
            "final CONCERNS contract",
            (sys.executable, "skills/deterministic-checks/scripts/final_concerns_contract_regression_check.py"),
        ),
        ("context-document structure", (sys.executable, "scripts/context-docs-contracts.py")),
        (
            "canonical context documents",
            (sys.executable, "skills/deterministic-checks/scripts/context-docs.py", "--repo", "."),
        ),
        ("skill package regressions", (sys.executable, "scripts/skill-package-contracts-regression.py")),
        ("skill packages", (sys.executable, "scripts/skill-package-contracts.py")),
        (
            "repository learning state",
            (sys.executable, "skills/he-learn/scripts/learning_state_regression.py"),
        ),
        ("worktree readiness", (sys.executable, "scripts/worktree-readiness-contracts.py")),
        ("route resources", (sys.executable, "scripts/route_resource_contracts.py")),
        ("global worktree hook fixture", ("scripts/git-hooks/test.sh",)),
        ("worktree policy contract", (sys.executable, "scripts/worktree-policy-contract-check.py")),
        ("Git environment hygiene", (sys.executable, "scripts/git-env-hygiene-contract.py")),
        ("setup contract", (sys.executable, "scripts/setup-contract-check.py")),
        (
            "execution evidence",
            (sys.executable, "skills/he/scripts/execution_evidence_regression.py"),
        ),
        ("agent guard hooks", (sys.executable, "scripts/agent-hook-contract-check.py")),
        (
            "agent-agnostic content",
            (sys.executable, "scripts/check-agent-agnostic-content.py"),
        ),
        (
            "agent-agnostic content regressions",
            (sys.executable, "scripts/check-agent-agnostic-content-regression.py"),
        ),
        (
            "bounded command contract",
            (sys.executable, "skills/deterministic-checks/scripts/bounded_run_regression_check.py"),
        ),
        (
            "GitHub delivery contract",
            (sys.executable, "skills/deterministic-checks/scripts/github_delivery_regression_check.py"),
        ),
        (
            "Appwrite backend contracts",
            (
                "node", "--test",
                "skills/appwrite-backend/scripts/appwrite-query-contract.test.mjs",
                "skills/appwrite-backend/scripts/appwrite-schema-guard.test.mjs",
                "skills/appwrite-backend/scripts/skill-safety-contract.test.mjs",
            ),
        ),
    )
    longest_first = {
        label: index
        for index, label in enumerate(
            (
                "source-tree coordination contract",
                "Feature Brief state contract",
                "slice gate contract",
                "setup contract",
                "worktree readiness",
                "project gate contract",
                "Dart Decimate contract",
                "bounded command contract",
                "external CLI restore contract",
                "global worktree hook fixture",
            )
        )
    }
    contracts = tuple(
        sorted(contracts, key=lambda item: longest_first.get(item[0], len(longest_first)))
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
    if len(sys.argv) > 2 or (len(sys.argv) == 2 and sys.argv[1] != "--fresh"):
        fail("usage: check-skill-contracts.py [--fresh]")
    receipt, identity = proof_identity()
    if len(sys.argv) == 1 and reusable(receipt, identity):
        print("skill-contracts: PASS (exact-tree proof reused)")
        return 0
    receipt.unlink(missing_ok=True)
    check_fast_feature_loop_contract(ROOT, fail)
    check_plan_state_contract()
    check_external_contracts()
    atomic_json(receipt, identity)
    print("skill-contracts: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

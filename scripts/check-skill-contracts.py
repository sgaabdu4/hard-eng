#!/usr/bin/env python3
"""Repository contract entrypoint for lifecycle and deterministic safety checks."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import platform
import shutil
import stat
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
from bounded_run import CapturedRunResult, run_captured
scrub_environ()
CACHE_SCHEMA = 2
CONTRACT_TIMEOUT_SECONDS = 600.0
CONTRACT_GRACE_SECONDS = 2.0
IDENTITY_ENVIRONMENT = (
    "CI",
    "GIT_CEILING_DIRECTORIES",
    "GIT_CONFIG_NOSYSTEM",
    "GITHUB_ACTIONS",
    "GITHUB_REF",
    "GITHUB_SHA",
    "GITHUB_WORKFLOW",
    "HOME",
    "HARD_ENG_GIT_ENV_CACHE",
    "LANG",
    "LC_ALL",
    "NODE_PATH",
    "PATH",
    "PYTHONHASHSEED",
    "PYTHONPATH",
    "TMPDIR",
    "TZ",
    "VIRTUAL_ENV",
)
DEPENDENCY_FILES = (
    ".skill-lock.json",
    "package.json",
    "package-lock.json",
    "runtime/npm/package.json",
    "runtime/npm/package-lock.json",
    "node_modules/.package-lock.json",
)
DEPENDENCY_TREES = ("node_modules", "runtime/npm/node_modules")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path, deadline: float | None = None) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            if deadline is not None and time.monotonic() >= deadline:
                raise TimeoutError("dependency identity deadline exhausted")
            digest.update(chunk)
    return digest.hexdigest()


def file_identity(path_value: str | Path) -> dict[str, object]:
    requested = Path(path_value)
    requested_absolute = Path(os.path.abspath(requested))
    metadata = requested_absolute.lstat()
    resolved = requested_absolute.resolve(strict=True)
    resolved_metadata = resolved.stat()
    if not stat.S_ISREG(resolved_metadata.st_mode):
        raise OSError(f"runtime is not a regular file: {requested_absolute}")
    result: dict[str, object] = {
        "path": str(requested_absolute),
        "resolved_path": str(resolved),
        "mode": metadata.st_mode,
        "resolved_mode": resolved_metadata.st_mode,
        "size": resolved_metadata.st_size,
        "mtime_ns": resolved_metadata.st_mtime_ns,
        "sha256": _sha256_file(resolved),
    }
    if requested_absolute.is_symlink():
        result["link_target"] = os.readlink(requested_absolute)
    return result


def dependency_tree_digest(root: Path, deadline: float) -> str | None:
    if not root.exists() and not root.is_symlink():
        return None
    digest = hashlib.sha256()
    root_metadata = root.lstat()
    digest.update(root.relative_to(ROOT).as_posix().encode("utf-8"))
    digest.update(f"\0root-mode={root_metadata.st_mode:o}\0".encode())
    if root.is_symlink():
        raise OSError(f"dependency tree root must not be a symlink: {root}")
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise OSError(f"dependency tree root is not a directory: {root}")
    pending = [root]
    while pending:
        if time.monotonic() >= deadline:
            raise TimeoutError("dependency identity deadline exhausted")
        current = pending.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda path: path.name)
        except OSError as error:
            raise OSError(f"cannot read dependency tree: {current}") from error
        for entry in entries:
            if time.monotonic() >= deadline:
                raise TimeoutError("dependency identity deadline exhausted")
            relative = entry.relative_to(ROOT).as_posix().encode("utf-8")
            metadata = entry.lstat()
            digest.update(relative)
            digest.update(f"\0mode={metadata.st_mode:o}\0".encode())
            if entry.is_symlink():
                digest.update(b"link=")
                digest.update(os.fsencode(os.readlink(entry)))
                digest.update(b"\0")
            elif entry.is_dir():
                pending.append(entry)
            elif entry.is_file():
                digest.update(b"file=")
                digest.update(bytes.fromhex(_sha256_file(entry, deadline)))
                digest.update(b"\0")
            else:
                raise OSError(f"unsupported dependency tree entry: {entry}")
    return digest.hexdigest()


def _version_identity(executable: Path) -> dict[str, object]:
    environment = {
        key: os.environ[key]
        for key in IDENTITY_ENVIRONMENT
        if key in os.environ
    }
    try:
        result: CapturedRunResult = run_captured(
            [str(executable), "--version"],
            timeout=10.0,
            grace=1.0,
            env=environment,
        )
    except OSError as error:
        return {"launch_error": type(error).__name__}
    return {
        "returncode": result.returncode,
        "terminal": result.terminal,
        "stdout_sha256": _sha256_bytes(result.stdout),
        "stderr_sha256": _sha256_bytes(result.stderr),
    }


def _safe_environment_identity() -> dict[str, object]:
    result: dict[str, object] = {}
    for key in IDENTITY_ENVIRONMENT:
        value = os.environ.get(key)
        result[key] = (
            None
            if value is None
            else {
                "length": len(value),
                "sha256": _sha256_bytes(value.encode("utf-8", "surrogateescape")),
            }
        )
    return result


def runtime_identity() -> dict[str, object]:
    identity: dict[str, object] = {}
    for name in ("bash", "git", "node", "npm", "perl", "python3", "sh", "ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        if executable is None:
            identity[name] = None
            continue
        path = Path(executable).resolve(strict=True)
        identity[name] = {
            **file_identity(executable),
            "version": _version_identity(path),
        }
    identity["current_python"] = {
        **file_identity(sys.executable),
        "version": _version_identity(Path(sys.executable).resolve(strict=True)),
    }
    return identity


def dependency_identity(deadline: float) -> dict[str, object]:
    return {
        "descriptors": {
            relative: (
                file_identity(ROOT / relative)
                if (ROOT / relative).exists() or (ROOT / relative).is_symlink()
                else None
            )
            for relative in DEPENDENCY_FILES
        },
        "trees": {
            relative: dependency_tree_digest(ROOT / relative, deadline)
            for relative in DEPENDENCY_TREES
        },
    }


def proof_identity() -> tuple[Path, dict[str, object]]:
    deadline = time.monotonic() + 120
    return git_private_path(ROOT, "hard-eng-contracts-v1.json"), {
        "schema_version": CACHE_SCHEMA,
        "repository": str(ROOT.resolve()),
        "tree_digest": tree_fingerprint(ROOT, deadline=deadline),
        "runtimes": runtime_identity(),
        "dependencies": dependency_identity(deadline),
        "environment": _safe_environment_identity(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_implementation": platform.python_implementation(),
            "python_version": platform.python_version(),
        },
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


def run(command: tuple[str, ...], label: str) -> tuple[str, CapturedRunResult]:
    env = os.environ.copy()
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return label, run_captured(
        command,
        timeout=CONTRACT_TIMEOUT_SECONDS,
        grace=CONTRACT_GRACE_SECONDS,
        cwd=str(ROOT),
        env=env,
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
            "repository manifest",
            (sys.executable, "scripts/repository-manifest-regression.py"),
        ),
        (
            "GitHub workflow contracts",
            ("node", "scripts/github-workflow-contracts-regression.mjs"),
        ),
        (
            "Windows installer asset contracts",
            ("node", "scripts/windows-installer-assets-contract-regression.mjs"),
        ),
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
        (
            "bounded operation inventory",
            (sys.executable, "scripts/bounded-operations-contract.py"),
        ),
        (
            "setup CLI error boundary",
            (sys.executable, "scripts/setup-cli-error-contract-check.py"),
        ),
        (
            "critical behavior inventory",
            (sys.executable, "scripts/critical-behavior-inventory-contract.py"),
        ),
        (
            "license notice provenance",
            (sys.executable, "scripts/license-notice-contract.py"),
        ),
        ("repository governance", ("node", "scripts/governance-contract.mjs")),
        ("setup contract", (sys.executable, "scripts/setup-contract-check.py")),
        (
            "managed-skill update state",
            (sys.executable, "scripts/managed-skill-update-state-regression.py"),
        ),
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
            "skill-contract proof identity",
            (sys.executable, "scripts/check-skill-contracts-regression.py"),
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
        (
            "product walkthrough workflow",
            (sys.executable, "-B", "skills/product-walkthrough-video/scripts/run_workflow_regression_check.py"),
        ),
        (
            "product walkthrough containment",
            (sys.executable, "-B", "skills/product-walkthrough-video/scripts/workflow_boundary_regression_check.py"),
        ),
        (
            "product walkthrough media binding",
            (sys.executable, "-B", "skills/product-walkthrough-video/scripts/media_binding_regression_check.py"),
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
            stderr = result.stderr.decode("utf-8", "replace").strip()
            stdout = result.stdout.decode("utf-8", "replace").strip()
            fail(stderr or stdout or f"{label} failed")
        stdout = result.stdout.decode("utf-8", "replace").strip()
        if stdout:
            print(stdout)


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

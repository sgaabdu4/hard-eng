#!/usr/bin/env python3
"""Regression checks for exact GitHub delivery receipts."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, NoReturn

from bounded_run import run_captured

ROOT = Path(__file__).resolve().parents[3]
VERIFIER = ROOT / "skills/deterministic-checks/scripts/github_delivery.py"
SHA = "a" * 40
REUSABLE_SHA = "c" * 40


def fail(message: str) -> NoReturn:
    raise SystemExit(f"github-delivery-regressions: {message}")


def load_verifier() -> Any:
    specification = importlib.util.spec_from_file_location("github_delivery", VERIFIER)
    if specification is None or specification.loader is None:
        fail("verifier could not be loaded")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def fixtures() -> tuple[dict[str, Any], dict[str, Any]]:
    run = {
        "id": 123,
        "name": "Production",
        "repository": {"full_name": "owner/repository"},
        "workflow_id": 77,
        "path": ".github/workflows/production.yml@main",
        "event": "workflow_dispatch",
        "head_branch": "main",
        "run_attempt": 2,
        "check_suite_id": 456,
        "referenced_workflows": [
            {"path": "owner/reusable/.github/workflows/deploy.yml@v1", "sha": REUSABLE_SHA, "ref": "refs/tags/v1"}
        ],
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
    }
    jobs = {
        "total_count": 2,
        "jobs": [
            {
                "name": "deploy",
                "head_sha": SHA,
                "status": "completed",
                "conclusion": "success",
                "steps": [
                    {"name": "Deploy production", "status": "completed", "conclusion": "success"},
                    {"name": "Exact readback", "status": "completed", "conclusion": "success"},
                ],
            },
            {"name": "quality", "head_sha": SHA, "status": "completed", "conclusion": "success", "steps": []},
        ],
    }
    return run, jobs


def verify(module: Any, run: Any, jobs: Any) -> None:
    module.verify_delivery(
        run,
        jobs,
        repository="owner/repository",
        run_id=123,
        sha=SHA,
        workflow="Production",
        workflow_id=77,
        workflow_path=".github/workflows/production.yml@main",
        event="workflow_dispatch",
        ref="main",
        run_attempt=2,
        check_suite_id=456,
        reusable_workflows=(f"owner/reusable/.github/workflows/deploy.yml@v1::{REUSABLE_SHA}::refs/tags/v1",),
        required_jobs=("quality",),
        required_steps=("deploy::Deploy production", "deploy::Exact readback"),
    )


def expect_failure(module: Any, run: Any, jobs: Any, expected: str) -> None:
    try:
        verify(module, run, jobs)
    except module.DeliveryError as error:
        if expected not in str(error):
            fail(f"unexpected failure: {error}")
        return
    fail(f"mutation passed: {expected}")


def check_semantics(module: Any) -> None:
    run, jobs = fixtures()
    verify(module, run, jobs)

    wrong_sha_run, wrong_sha_jobs = fixtures()
    wrong_sha_run["head_sha"] = "b" * 40
    expect_failure(module, wrong_sha_run, wrong_sha_jobs, "run SHA")

    skipped_run, skipped_jobs = fixtures()
    skipped_jobs["jobs"][0]["steps"][0]["conclusion"] = "skipped"
    expect_failure(module, skipped_run, skipped_jobs, "step")

    missing_run, missing_jobs = fixtures()
    missing_jobs["jobs"] = missing_jobs["jobs"][:1]
    missing_jobs["total_count"] = 1
    expect_failure(module, missing_run, missing_jobs, "job")

    duplicate_run, duplicate_jobs = fixtures()
    duplicate_jobs["jobs"].append(dict(duplicate_jobs["jobs"][0]))
    duplicate_jobs["total_count"] = 3
    expect_failure(module, duplicate_run, duplicate_jobs, "ambiguous")

    stale_run, stale_jobs = fixtures()
    stale_jobs["jobs"][0]["head_sha"] = "b" * 40
    expect_failure(module, stale_run, stale_jobs, "job SHA")

    mutations = (
        ("id", 124, "run ID"),
        ("repository", {"full_name": "lookalike/repository"}, "repository identity"),
        ("workflow_id", 78, "workflow_id"),
        ("path", ".github/workflows/lookalike.yml@main", "path"),
        ("event", "push", "event"),
        ("head_branch", "release", "head_branch"),
        ("run_attempt", 1, "run_attempt"),
        ("check_suite_id", 999, "check_suite_id"),
        ("referenced_workflows", [], "referenced workflow"),
    )
    for field, value, expected in mutations:
        changed_run, changed_jobs = fixtures()
        changed_run[field] = value
        expect_failure(module, changed_run, changed_jobs, expected)


def check_cli() -> None:
    run, jobs = fixtures()
    with tempfile.TemporaryDirectory(prefix="github-delivery-") as temporary:
        root = Path(temporary)
        run_path = root / "run.json"
        jobs_path = root / "jobs.json"
        run_path.write_text(json.dumps(run), encoding="utf-8")
        jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
        command = [
            sys.executable,
            str(VERIFIER),
            "--run-json",
            str(run_path),
            "--jobs-json",
            str(jobs_path),
            "--run-id",
            "123",
            "--sha",
            SHA,
            "--workflow",
            "Production",
            "--expected-repository",
            "owner/repository",
            "--workflow-id",
            "77",
            "--workflow-path",
            ".github/workflows/production.yml@main",
            "--event",
            "workflow_dispatch",
            "--ref",
            "main",
            "--run-attempt",
            "2",
            "--check-suite-id",
            "456",
            "--reusable-workflow",
            f"owner/reusable/.github/workflows/deploy.yml@v1::{REUSABLE_SHA}::refs/tags/v1",
            "--require-job",
            "quality",
            "--require-step",
            "deploy::Deploy production",
        ]
        passed = run_captured(command, timeout=30, cwd=str(ROOT))
        if passed.returncode != 0 or b"github-delivery: PASS" not in passed.stdout:
            fail("valid CLI fixture did not pass")
        jobs["jobs"][0]["steps"][0]["conclusion"] = "skipped"
        jobs_path.write_text(json.dumps(jobs), encoding="utf-8")
        failed = run_captured(command, timeout=30, cwd=str(ROOT))
        if failed.returncode != 1 or b"github-delivery: FAIL" not in failed.stderr:
            fail("skipped required step did not fail CLI")


def main() -> int:
    module = load_verifier()
    check_semantics(module)
    check_cli()
    print("github-delivery-regressions: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

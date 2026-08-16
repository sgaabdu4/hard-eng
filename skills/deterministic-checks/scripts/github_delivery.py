#!/usr/bin/env python3
"""Verify one GitHub Actions run and its required jobs/steps for an exact delivery SHA."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from bounded_run import TIMEOUT_EXIT, run_captured


SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
GH_TIMEOUT_SECONDS = 30


class DeliveryError(ValueError):
    """A safe deterministic delivery-contract failure."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DeliveryError(f"invalid JSON fixture: {path}") from error


def gh_json(endpoint: str) -> Any:
    try:
        result = run_captured(
            ["gh", "api", endpoint],
            timeout=GH_TIMEOUT_SECONDS,
            grace=1,
        )
    except OSError as error:
        raise DeliveryError("GitHub API query failed") from error
    if result.returncode in {TIMEOUT_EXIT} or result.returncode != 0:
        raise DeliveryError("GitHub API query failed")
    try:
        return json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise DeliveryError("GitHub API response was not valid JSON") from error


def fetch_live(repository: str, run_id: int) -> tuple[Any, Any]:
    run = gh_json(f"repos/{repository}/actions/runs/{run_id}")
    jobs: list[Any] = []
    page = 1
    total_count: int | None = None
    while total_count is None or len(jobs) < total_count:
        payload = gh_json(
            f"repos/{repository}/actions/runs/{run_id}/jobs"
            f"?filter=latest&per_page=100&page={page}"
        )
        if not isinstance(payload, dict):
            raise DeliveryError("GitHub jobs response was invalid")
        page_jobs = payload.get("jobs")
        candidate_total = payload.get("total_count")
        if not isinstance(page_jobs, list) or not isinstance(candidate_total, int):
            raise DeliveryError("GitHub jobs response was invalid")
        if candidate_total < 0 or (total_count is not None and candidate_total != total_count):
            raise DeliveryError("GitHub jobs total changed during verification")
        total_count = candidate_total
        if not page_jobs and len(jobs) < total_count:
            raise DeliveryError("GitHub jobs pagination ended early")
        jobs.extend(page_jobs)
        page += 1
        if page > 101:
            raise DeliveryError("GitHub jobs pagination exceeded its limit")
    return run, {"total_count": total_count, "jobs": jobs}


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeliveryError(f"{label} was invalid")
    return value


def require_exact(items: list[Any], name: str, label: str) -> dict[str, Any]:
    matches = [
        item
        for item in items
        if isinstance(item, dict) and item.get("name") == name
    ]
    if len(matches) != 1:
        raise DeliveryError(f"required {label} was missing or ambiguous: {name}")
    return matches[0]


def require_success(owner: dict[str, Any], label: str) -> None:
    if owner.get("status") != "completed" or owner.get("conclusion") != "success":
        raise DeliveryError(f"required {label} did not complete successfully")


def parse_step(specification: str) -> tuple[str, str]:
    parts = specification.split("::")
    if len(parts) != 2 or not all(parts):
        raise DeliveryError("required step must use '<job>::<step>'")
    return parts[0], parts[1]


def reusable_identity(value: Any) -> tuple[str, str, str | None]:
    owner = require_mapping(value, "referenced workflow")
    path = owner.get("path")
    sha = owner.get("sha")
    ref = owner.get("ref")
    if (
        not isinstance(path, str)
        or not path
        or not isinstance(sha, str)
        or SHA_PATTERN.fullmatch(sha) is None
        or (ref is not None and (not isinstance(ref, str) or not ref))
    ):
        raise DeliveryError("referenced workflow identity was invalid")
    return path, sha, ref


def parse_reusable(specification: str) -> tuple[str, str, str | None]:
    parts = specification.split("::")
    if len(parts) not in {2, 3} or not all(parts[:2]):
        raise DeliveryError("reusable workflow must use '<path>::<sha>[::<ref>]'")
    ref = parts[2] if len(parts) == 3 and parts[2] else None
    return reusable_identity({"path": parts[0], "sha": parts[1], "ref": ref})


def verify_delivery(
    run_payload: Any,
    jobs_payload: Any,
    *,
    repository: str,
    run_id: int,
    sha: str,
    workflow: str,
    workflow_id: int,
    workflow_path: str,
    event: str,
    ref: str,
    run_attempt: int,
    check_suite_id: int,
    reusable_workflows: tuple[str, ...],
    required_jobs: tuple[str, ...],
    required_steps: tuple[str, ...],
) -> dict[str, Any]:
    run = require_mapping(run_payload, "workflow run")
    jobs_owner = require_mapping(jobs_payload, "workflow jobs")
    jobs = jobs_owner.get("jobs")
    total_count = jobs_owner.get("total_count")
    if not isinstance(jobs, list) or type(total_count) is not int or total_count != len(jobs):
        raise DeliveryError("workflow jobs were incomplete")
    repository_owner = require_mapping(run.get("repository"), "workflow repository")
    if repository_owner.get("full_name") != repository:
        raise DeliveryError("workflow repository identity did not match")
    if type(run.get("id")) is not int or run.get("id") != run_id:
        raise DeliveryError("workflow run ID did not match")
    if run.get("head_sha") != sha:
        raise DeliveryError("workflow run SHA did not match delivery SHA")
    if run.get("name") != workflow:
        raise DeliveryError("workflow run name did not match")
    expected_fields = {
        "workflow_id": workflow_id,
        "path": workflow_path,
        "event": event,
        "head_branch": ref,
        "run_attempt": run_attempt,
        "check_suite_id": check_suite_id,
    }
    for field, expected in expected_fields.items():
        actual = run.get(field)
        if type(expected) is int and type(actual) is not int:
            raise DeliveryError(f"workflow run {field} did not match")
        if actual != expected:
            raise DeliveryError(f"workflow run {field} did not match")
    actual_reusable = run.get("referenced_workflows", [])
    if not isinstance(actual_reusable, list):
        raise DeliveryError("referenced workflow identity was invalid")
    actual_identities = [reusable_identity(item) for item in actual_reusable]
    expected_identities = [parse_reusable(item) for item in reusable_workflows]
    if len(actual_identities) != len(set(actual_identities)):
        raise DeliveryError("referenced workflow identity was ambiguous")
    if len(expected_identities) != len(set(expected_identities)):
        raise DeliveryError("expected referenced workflow identity was ambiguous")
    if set(actual_identities) != set(expected_identities):
        raise DeliveryError("referenced workflow identity did not match")
    require_success(run, "workflow")

    resolved_jobs: dict[str, dict[str, Any]] = {}

    def resolve_job(name: str) -> dict[str, Any]:
        job = resolved_jobs.get(name)
        if job is None:
            job = require_exact(jobs, name, "job")
            if job.get("head_sha") != sha:
                raise DeliveryError(f"required job SHA did not match: {name}")
            require_success(job, f"job: {name}")
            resolved_jobs[name] = job
        return job

    for name in required_jobs:
        resolve_job(name)
    for specification in required_steps:
        job_name, step_name = parse_step(specification)
        job = resolve_job(job_name)
        steps = job.get("steps")
        if not isinstance(steps, list):
            raise DeliveryError(f"required job had no steps: {job_name}")
        step = require_exact(steps, step_name, "step")
        require_success(step, f"step: {specification}")

    return {
        "run_id": run.get("id"),
        "repository": repository,
        "workflow_id": workflow_id,
        "workflow_path": workflow_path,
        "run_attempt": run_attempt,
        "check_suite_id": check_suite_id,
        "required_jobs": len(set(required_jobs) | {parse_step(item)[0] for item in required_steps}),
        "required_steps": len(required_steps),
        "sha": sha,
        "workflow": workflow,
    }


def parser() -> argparse.ArgumentParser:
    owner = argparse.ArgumentParser(description=__doc__)
    owner.add_argument("--repo")
    owner.add_argument("--run-id", type=int, required=True)
    owner.add_argument("--run-json", type=Path)
    owner.add_argument("--jobs-json", type=Path)
    owner.add_argument("--sha", required=True)
    owner.add_argument("--workflow", required=True)
    owner.add_argument("--expected-repository", required=True)
    owner.add_argument("--workflow-id", type=int, required=True)
    owner.add_argument("--workflow-path", required=True)
    owner.add_argument("--event", required=True)
    owner.add_argument("--ref", required=True)
    owner.add_argument("--run-attempt", type=int, required=True)
    owner.add_argument("--check-suite-id", type=int, required=True)
    owner.add_argument("--reusable-workflow", action="append", default=[])
    owner.add_argument("--require-job", action="append", default=[])
    owner.add_argument("--require-step", action="append", default=[])
    return owner


def inputs(args: argparse.Namespace) -> tuple[Any, Any]:
    live = args.repo is not None
    fixture = args.run_json is not None or args.jobs_json is not None
    if live == fixture:
        raise DeliveryError("choose live GitHub input or JSON fixtures")
    if live:
        if (
            not isinstance(args.repo, str)
            or REPOSITORY_PATTERN.fullmatch(args.repo) is None
        ):
            raise DeliveryError("live GitHub input is invalid")
        return fetch_live(args.repo, args.run_id)
    if not isinstance(args.run_json, Path) or not isinstance(args.jobs_json, Path):
        raise DeliveryError("both JSON fixtures are required")
    return load_json(args.run_json), load_json(args.jobs_json)


def main() -> int:
    args = parser().parse_args()
    try:
        if SHA_PATTERN.fullmatch(args.sha) is None:
            raise DeliveryError("delivery SHA must be a full lowercase SHA-1")
        if REPOSITORY_PATTERN.fullmatch(args.expected_repository) is None:
            raise DeliveryError("expected repository identity is invalid")
        if (
            not args.workflow
            or not args.workflow_path.startswith(".github/workflows/")
            or not args.event
            or not args.ref
            or any(
                value < 1
                for value in (
                    args.run_id,
                    args.workflow_id,
                    args.run_attempt,
                    args.check_suite_id,
                )
            )
            or (not args.require_job and not args.require_step)
        ):
            raise DeliveryError("workflow and required job/step contract are required")
        run, jobs = inputs(args)
        receipt = verify_delivery(
            run,
            jobs,
            repository=args.expected_repository,
            run_id=args.run_id,
            sha=args.sha,
            workflow=args.workflow,
            workflow_id=args.workflow_id,
            workflow_path=args.workflow_path,
            event=args.event,
            ref=args.ref,
            run_attempt=args.run_attempt,
            check_suite_id=args.check_suite_id,
            reusable_workflows=tuple(args.reusable_workflow),
            required_jobs=tuple(args.require_job),
            required_steps=tuple(args.require_step),
        )
    except DeliveryError as error:
        print(f"github-delivery: FAIL {error}", file=sys.stderr)
        return 1
    print(
        "github-delivery: PASS"
        f" sha={receipt['sha']}"
        f" workflow={receipt['workflow']}"
        f" workflow_id={receipt['workflow_id']}"
        f" attempt={receipt['run_attempt']}"
        f" run_id={receipt['run_id']}"
        f" required_jobs={receipt['required_jobs']}"
        f" required_steps={receipt['required_steps']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

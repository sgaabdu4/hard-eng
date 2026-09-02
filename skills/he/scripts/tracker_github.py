#!/usr/bin/env python3
"""Push-mirror ticket tracker adapter over the `gh` CLI: best-effort, never authoritative, never blocks."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DETERMINISTIC_SCRIPTS = SCRIPT_DIR.parents[1] / "deterministic-checks" / "scripts"
for candidate in (SCRIPT_DIR, DETERMINISTIC_SCRIPTS):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from bounded_run import run_captured
from git_env import git_env


class TrackerError(RuntimeError):
    pass


def gh_available() -> bool:
    return shutil.which("gh") is not None


def available(config: dict[str, str], creds: dict[str, str]) -> bool:
    return gh_available() and "/" in config.get("repository", "")


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str]:
    command = ["gh", *args]
    captured = run_captured(command, timeout, env=git_env())
    return subprocess.CompletedProcess(
        command,
        captured.returncode,
        captured.stdout.decode("utf-8", "replace"),
        captured.stderr.decode("utf-8", "replace"),
    )


def _number(ref: str) -> str | None:
    tail = ref.strip().rstrip("/").rsplit("/", 1)[-1].lstrip("#")
    return tail if tail.isdigit() else None


def create_ticket(
    config: dict[str, str],
    creds: dict[str, str],
    *,
    ticket_id: str,
    title: str,
    body: str,
    kind: str,
    parent: str | None,
    blocked_by: Iterable[str],
) -> str:
    args = ["issue", "create", "--repo", config["repository"], "--title", title, "--body", body, "--label", kind]
    parent_number = _number(parent) if parent else None
    if parent_number:
        args += ["--parent", parent_number]
    blockers = [number for number in (_number(ref) for ref in blocked_by) if number]
    if blockers:
        args += ["--blocked-by", ",".join(blockers)]
    result = _run(args)
    if result.returncode != 0:
        raise TrackerError(f"gh issue create failed for {ticket_id}: {result.stderr.strip() or result.returncode}")
    url = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
    if not url:
        raise TrackerError(f"gh issue create returned no issue URL for {ticket_id}")
    return url


def update_status(config: dict[str, str], creds: dict[str, str], tracker_ref: str, status: str) -> bool:
    result = _run(["issue", "edit", tracker_ref, "--repo", config["repository"], "--add-label", status])
    if result.returncode != 0:
        raise TrackerError(f"gh issue edit failed for {tracker_ref}: {result.stderr.strip() or result.returncode}")
    return True


def close_ticket(config: dict[str, str], creds: dict[str, str], tracker_ref: str, reason: str) -> bool:
    result = _run(["issue", "close", tracker_ref, "--repo", config["repository"], "--comment", reason])
    if result.returncode != 0:
        raise TrackerError(f"gh issue close failed for {tracker_ref}: {result.stderr.strip() or result.returncode}")
    return True


def link_pr(config: dict[str, str], creds: dict[str, str], tracker_ref: str, pr_url: str) -> bool:
    result = _run(["issue", "comment", tracker_ref, "--repo", config["repository"], "--body", f"Linked PR: {pr_url}"])
    if result.returncode != 0:
        raise TrackerError(f"gh issue comment failed for {tracker_ref}: {result.stderr.strip() or result.returncode}")
    return True


def project_add(config: dict[str, str], creds: dict[str, str], tracker_ref: str) -> bool:
    project = config.get("project")
    if not project:
        return False
    owner = config["repository"].split("/", 1)[0]
    result = _run(["project", "item-add", project, "--owner", owner, "--url", tracker_ref])
    if result.returncode != 0:
        print(
            "tracker: project scope unavailable or project-add failed, continuing issues-only: "
            f"{result.stderr.strip() or result.returncode}",
            file=sys.stderr,
        )
        return False
    return True


def pull_drift(config: dict[str, str], creds: dict[str, str], tracker_refs: tuple[str, ...]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for ref in tracker_refs:
        result = _run(["issue", "view", ref, "--repo", config["repository"], "--json", "state,title,updatedAt"])
        if result.returncode != 0:
            raise TrackerError(f"gh issue view failed for {ref}: {result.stderr.strip() or result.returncode}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise TrackerError(f"gh issue view returned invalid JSON for {ref}: {error}") from error
        rows.append(
            {
                "tracker_ref": ref,
                "remote_state": str(payload.get("state", "")),
                "remote_title": str(payload.get("title", "")),
                "remote_updated_at": str(payload.get("updatedAt", "")),
            }
        )
    return rows


def best_effort(operation: Callable[[], object], *, label: str) -> object:
    try:
        return operation()
    except (OSError, subprocess.SubprocessError, TrackerError) as error:
        print(f"tracker: {label} failed (best-effort, continuing): {error}", file=sys.stderr)
        return False

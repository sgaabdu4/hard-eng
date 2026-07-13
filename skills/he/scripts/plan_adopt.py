#!/usr/bin/env python3
"""Adopt a committed build artifact into one shipping PLAN."""

from __future__ import annotations

import re
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from plan_contract import PlanStateError
from plan_transfer import atomic_write
from repository_snapshot import SnapshotError, artifact_id, is_plan, snapshot_id


State = dict[str, str]


def git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)


def require_committed_non_plan(root: Path) -> None:
    exclude = ":(exclude,glob)features/*/PLAN.md"
    diff = git(root, "diff", "--quiet", "HEAD", "--", ".", exclude)
    if diff.returncode != 0:
        raise PlanStateError("non-PLAN working changes remain after implementation commit")
    raw = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    if raw.returncode != 0:
        raise PlanStateError("cannot inspect untracked files")
    untracked = tuple(
        part.decode("utf-8", "surrogateescape") for part in raw.stdout.split(b"\0") if part
    )
    if any(not is_plan(relative) for relative in untracked):
        raise PlanStateError("untracked non-PLAN files remain after implementation commit")


def require_commit_range(root: Path, recorded: str, head: str) -> None:
    count = git(root, "rev-list", "--count", f"{recorded}..{head}")
    if count.returncode != 0 or count.stdout.strip() != b"1":
        raise PlanStateError("adopt-head requires exactly one implementation commit")
    plan_paths = git(
        root, "diff", "--name-only", "-z", recorded, head, "--", ":(glob)features/*/PLAN.md"
    )
    if plan_paths.returncode != 0 or plan_paths.stdout:
        raise PlanStateError("implementation commit contains PLAN state")


def adopt_head(
    repo_arg: str,
    plan_arg: str,
    expected_token: str,
    *,
    git_identity: Callable[[Path], tuple[Path, str, str]],
    canonical_plan: Callable[[Path, Path], Path],
    checkpoint_token: Callable[[str], str],
    document_token: Callable[[str], str],
    validate_document: Callable[[Path, str], State],
    validate_state_change: Callable[[State, State], None],
    replace_state: Callable[[str, dict[str, str]], str],
    emit: Callable[[str, str], None],
) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
        plan = canonical_plan(Path(plan_arg).expanduser(), root)
        original = plan.read_text(encoding="utf-8")
        original_token = document_token(original)
        if not re.fullmatch(r"[0-9a-f]{64}", expected_token):
            raise PlanStateError("invalid checkpoint token")
        if checkpoint_token(original) != expected_token:
            raise PlanStateError("stale checkpoint token; inspect again")
        state = validate_document(plan, original)
        if Path(state["repository_root"]).expanduser().resolve() != root or state["branch"] != branch:
            raise PlanStateError("stale repository or branch identity")
        if state["lifecycle_status"] != "shipping" or state["build_evidence"] != "current":
            raise PlanStateError("adopt-head requires current shipping evidence")
        recorded = state["head_sha"]
        if recorded in {"UNBORN", head}:
            raise PlanStateError("adopt-head requires a new committed HEAD")
        ancestor = git(root, "merge-base", "--is-ancestor", recorded, head)
        if ancestor.returncode != 0:
            raise PlanStateError("new HEAD does not descend from the built HEAD")
        require_commit_range(root, recorded, head)
        require_committed_non_plan(root)
        if artifact_id(root) != state["artifact_id"]:
            raise PlanStateError("committed artifact differs from the green snapshot")
        updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        candidate = replace_state(
            original, {"head_sha": head, "snapshot_id": snapshot_id(root), "updated_at_utc": updated}
        )
        candidate_state = validate_document(plan, candidate)
        validate_state_change(state, candidate_state)
        if document_token(plan.read_text(encoding="utf-8")) != original_token:
            raise PlanStateError("PLAN changed during adopt-head")
        atomic_write(plan, candidate.encode("utf-8"), stat.S_IMODE(plan.stat().st_mode))
    except (OSError, UnicodeError, SnapshotError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4
    emit("result", "adopted")
    emit("plan", str(plan))
    emit("head_sha", head)
    emit("updated_at_utc", updated)
    emit("checkpoint_token", checkpoint_token(candidate))
    return 0

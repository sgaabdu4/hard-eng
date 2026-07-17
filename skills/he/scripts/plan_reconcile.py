#!/usr/bin/env python3
"""Reconcile one artifact-identical shipping commit with its Hard Eng PLAN."""

from __future__ import annotations

import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from plan_contract import PlanStateError
from plan_items import rebind_audit_receipts, rebind_learning_receipts
from plan_transfer import git_location, plan_writer_lock
from repository_snapshot import SnapshotError, artifact_id, is_plan, snapshot_id
from safe_repo_io import atomic_write as repo_write, snapshot as repo_snapshot


State = dict[str, str]
RECONCILABLE = {"shipping"}


def git(root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=False)


def require_committed_non_plan(root: Path) -> None:
    exclude = ":(exclude,glob)features/*/PLAN.md"
    if git(root, "diff", "--quiet", "HEAD", "--", ".", exclude).returncode != 0:
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
        raise PlanStateError("reconcile-head requires exactly one implementation commit")
    plan_paths = git(
        root, "diff", "--name-only", "-z", recorded, head, "--", ":(glob)features/*/PLAN.md"
    )
    if plan_paths.returncode != 0 or plan_paths.stdout:
        raise PlanStateError("implementation commit contains PLAN state")


def require_build_commit_range(root: Path, recorded: str, head: str) -> None:
    if recorded in {"UNBORN", head}:
        raise PlanStateError("reconcile-build-head requires a new committed HEAD")
    if git(root, "merge-base", "--is-ancestor", recorded, head).returncode != 0:
        raise PlanStateError("new HEAD does not descend from the recorded HEAD")
    plans = git(
        root, "diff", "--name-only", "-z", recorded, head, "--", ":(glob)features/*/PLAN.md"
    )
    if plans.returncode != 0 or plans.stdout:
        raise PlanStateError("reconcile-build-head rejects committed PLAN drift")


def require_exact_artifact(root: Path, expected: str) -> None:
    require_committed_non_plan(root)
    if artifact_id(root) != expected:
        raise PlanStateError("committed artifact differs from the recorded artifact")


def reconcile_build_head(
    repo_arg: str,
    plan_arg: str,
    expected_token: str,
    *,
    git_identity: Callable[[Path], tuple[Path, str, str]],
    canonical_plan: Callable[[Path, Path], Path],
    checkpoint_token: Callable[[str], str],
    document_token: Callable[[str], str],
    validate_document: Callable[[Path, str], State],
    validate_approval_receipt: Callable[[Path, State], None],
    validate_state_change: Callable[[State, State], None],
    snapshot_reconciliation: Callable[[State, str, str], dict[str, str]],
    replace_state: Callable[[str, dict[str, str]], str],
    emit: Callable[[str, str], None],
) -> int:
    try:
        root, branch, head = git_identity(Path(repo_arg).expanduser().resolve())
        with plan_writer_lock(git_location(root, "--git-common-dir")):
            plan = canonical_plan(Path(plan_arg).expanduser(), root)
            relative = plan.relative_to(root)
            original_bytes, mode = repo_snapshot(root, relative, "PLAN")
            original = original_bytes.decode("utf-8")
            if not re.fullmatch(r"[0-9a-f]{64}", expected_token):
                raise PlanStateError("invalid checkpoint token")
            if checkpoint_token(original) != expected_token:
                raise PlanStateError("stale checkpoint token; inspect again")
            state = validate_document(plan, original)
            validate_approval_receipt(root, state)
            if Path(state["repository_root"]).expanduser().resolve() != root or state["branch"] != branch:
                raise PlanStateError("stale repository or branch identity")
            if state["lifecycle_status"] != "building":
                raise PlanStateError("reconcile-build-head requires building state")
            require_build_commit_range(root, state["head_sha"], head)
            current_snapshot = snapshot_id(root)
            current_artifact = artifact_id(root)
            updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            candidate = replace_state(original, {
                **snapshot_reconciliation(state, current_snapshot, current_artifact),
                "head_sha": head, "updated_at_utc": updated,
            })
            candidate_state = validate_document(plan, candidate)
            validate_state_change(state, candidate_state)
            current = repo_snapshot(root, relative, "PLAN")[0].decode("utf-8")
            if document_token(current) != document_token(original):
                raise PlanStateError("PLAN changed during reconcile-build-head")
            require_build_commit_range(root, state["head_sha"], head)
            if git_identity(root) != (root, branch, head):
                raise PlanStateError("repository identity changed during reconcile-build-head")
            if snapshot_id(root) != current_snapshot or artifact_id(root) != current_artifact:
                raise PlanStateError("repository content changed during reconcile-build-head")
            repo_write(root, relative, candidate.encode("utf-8"), mode)
    except (OSError, UnicodeError, SnapshotError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4
    emit("result", "reconciled")
    emit("plan", str(plan))
    emit("head_sha", head)
    emit("snapshot_id", current_snapshot)
    emit("artifact_id", current_artifact)
    emit("checkpoint_token", checkpoint_token(candidate))
    return 0


def reconcile_head(
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
        with plan_writer_lock(git_location(root, "--git-common-dir")):
            plan = canonical_plan(Path(plan_arg).expanduser(), root)
            relative = plan.relative_to(root)
            original_bytes, mode = repo_snapshot(root, relative, "PLAN")
            original = original_bytes.decode("utf-8")
            original_token = document_token(original)
            if not re.fullmatch(r"[0-9a-f]{64}", expected_token):
                raise PlanStateError("invalid checkpoint token")
            if checkpoint_token(original) != expected_token:
                raise PlanStateError("stale checkpoint token; inspect again")
            state = validate_document(plan, original)
            if Path(state["repository_root"]).expanduser().resolve() != root or state["branch"] != branch:
                raise PlanStateError("stale repository or branch identity")
            if state["lifecycle_status"] not in RECONCILABLE:
                raise PlanStateError("reconcile-head requires shipping state")
            recorded = state["head_sha"]
            if recorded in {"UNBORN", head}:
                raise PlanStateError("reconcile-head requires a new committed HEAD")
            if git(root, "merge-base", "--is-ancestor", recorded, head).returncode != 0:
                raise PlanStateError("new HEAD does not descend from the recorded HEAD")
            require_commit_range(root, recorded, head)
            require_exact_artifact(root, state["artifact_id"])
            normalized_snapshot = snapshot_id(root)
            updated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            candidate = replace_state(
                original, {"head_sha": head, "snapshot_id": normalized_snapshot, "updated_at_utc": updated}
            )
            candidate = rebind_audit_receipts(
                candidate, state["snapshot_id"], normalized_snapshot
            )
            candidate = rebind_learning_receipts(
                candidate, normalized_snapshot, state["artifact_id"]
            )
            candidate_state = validate_document(plan, candidate)
            validate_state_change(state, candidate_state)
            current = repo_snapshot(root, relative, "PLAN")[0].decode("utf-8")
            if document_token(current) != original_token:
                raise PlanStateError("PLAN changed during reconcile-head")
            require_exact_artifact(root, state["artifact_id"])
            repo_write(root, relative, candidate.encode("utf-8"), mode)
            try:
                require_exact_artifact(root, state["artifact_id"])
            except (OSError, SnapshotError, PlanStateError) as error:
                try:
                    repo_write(root, relative, original_bytes, mode)
                except (OSError, PlanStateError) as restore_error:
                    raise PlanStateError(f"reconcile rollback failed: {restore_error}") from error
                raise
    except (OSError, UnicodeError, SnapshotError, PlanStateError) as exc:
        emit("result", "invalid")
        emit("error", str(exc))
        return 4
    emit("result", "reconciled")
    emit("plan", str(plan))
    emit("head_sha", head)
    emit("updated_at_utc", updated)
    emit("checkpoint_token", checkpoint_token(candidate))
    return 0

"""Crash-consistent Hard Eng PLAN state migration."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Callable

from plan_approval import approval_receipt_path
from plan_contract import LEGACY_REQUIRED, PlanStateError, STATE_LINE, parse_state_fields


def state_bounds(lines: list[str]) -> tuple[int, int]:
    headings = [index for index, line in enumerate(lines) if line.strip() == "## State"]
    if len(headings) != 1:
        raise PlanStateError("legacy PLAN requires exactly one ## State")
    start = headings[0] + 1
    end = next((index for index in range(start, len(lines)) if lines[index].startswith("## ")), len(lines))
    return start, end


def add_digest_field(text: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = state_bounds(lines)
    matches = [
        index for index in range(start, end)
        if (match := STATE_LINE.fullmatch(lines[index].strip())) and match.group(1) == "plan_approved"
    ]
    if len(matches) != 1:
        raise PlanStateError("legacy PLAN plan_approved field count invalid")
    index = matches[0]
    ending = "\n" if lines[index].endswith("\n") else ""
    lines.insert(index + 1, f"- approved_plan_digest = none{ending}")
    return "".join(lines)


def remove_digest_field(text: str) -> str:
    lines = text.splitlines(keepends=True)
    start, end = state_bounds(lines)
    matches = [
        index for index in range(start, end)
        if (match := STATE_LINE.fullmatch(lines[index].strip()))
        and match.group(1) == "approved_plan_digest"
    ]
    if len(matches) != 1:
        raise PlanStateError("migrated PLAN approved_plan_digest field count invalid")
    lines.pop(matches[0])
    return "".join(lines)


def legacy_candidate(
    text: str,
    *,
    replace_state: Callable[[str, dict[str, str]], str],
    approved_plan_digest: Callable[[str], str],
) -> tuple[str, dict[str, str]]:
    legacy = parse_state_fields(text, LEGACY_REQUIRED)
    if legacy["state_version"] != "3":
        raise PlanStateError(
            f"state migration requires state_version 3; actual: {legacy['state_version']}"
        )
    candidate = replace_state(add_digest_field(text), {"state_version": "4"})
    digest = approved_plan_digest(candidate) if legacy["plan_approved"] == "yes" else "none"
    candidate = replace_state(candidate, {"approved_plan_digest": digest})
    restored = replace_state(candidate, {"state_version": "3"})
    restored = remove_digest_field(restored)
    if restored != text:
        raise PlanStateError("state migration changed non-schema PLAN content")
    return candidate, legacy


def migrate_plan(
    repo_arg: str,
    plan_arg: str,
    *,
    git_identity,
    canonical_plan,
    repo_snapshot,
    repo_write,
    replace_state,
    approved_plan_digest,
    validate_document,
    write_approval_receipt,
    checkpoint_token,
    document_token,
    emit,
) -> int:
    receipt_created: Path | None = None
    plan_replaced = False
    original_bytes = b""
    mode = 0
    root = Path()
    relative = Path()
    def mark_replaced() -> None:
        nonlocal plan_replaced
        plan_replaced = True
    try:
        root, _, _ = git_identity(Path(repo_arg).expanduser().resolve())
        plan = canonical_plan(Path(plan_arg).expanduser(), root)
        relative = plan.relative_to(root)
        original_bytes, mode = repo_snapshot(root, relative, "legacy PLAN")
        original = original_bytes.decode("utf-8")
        candidate, legacy = legacy_candidate(
            original, replace_state=replace_state, approved_plan_digest=approved_plan_digest
        )
        state = validate_document(plan, candidate)
        if any(state[key] != legacy[key] for key in LEGACY_REQUIRED if key != "state_version"):
            raise PlanStateError("state migration changed legacy state values")
        if repo_snapshot(root, relative, "legacy PLAN")[0] != original_bytes:
            raise PlanStateError("PLAN.md changed during state migration; retry")
        if state["approved_plan_digest"] != "none":
            receipt = approval_receipt_path(root, state["plan_id"])
            existed = os.path.lexists(receipt)
            if existed and (
                receipt.is_symlink()
                or not receipt.is_file()
                or receipt.read_text(encoding="ascii") != state["approved_plan_digest"] + "\n"
            ):
                raise PlanStateError("legacy PLAN has a conflicting approval receipt")
            if not existed:
                write_approval_receipt(root, state)
                receipt_created = receipt
        repo_write(root, relative, candidate.encode("utf-8"), mode, on_replace=mark_replaced)
    except (OSError, UnicodeError, subprocess.CalledProcessError, PlanStateError) as exc:
        rollback_error = None
        if plan_replaced:
            try:
                repo_write(root, relative, original_bytes, mode)
            except (OSError, PlanStateError) as error:
                rollback_error = error
        if receipt_created is not None:
            if rollback_error is None:
                receipt_created.unlink(missing_ok=True)
        emit("result", "invalid")
        emit("error", str(exc) if rollback_error is None else f"{exc}; rollback failed: {rollback_error}")
        return 4
    emit("result", "migrated")
    emit("plan", str(plan))
    emit("from_state_version", "3")
    emit("state_version", "4")
    emit("approved_plan_digest", state["approved_plan_digest"])
    emit("previous_document_sha256", document_token(original))
    emit("checkpoint_token", checkpoint_token(candidate))
    return 0

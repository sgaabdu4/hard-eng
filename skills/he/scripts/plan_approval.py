"""Immutable approval digest + external receipt for Hard Eng PLAN content."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path

from plan_contract import PlanStateError
from plan_transfer import git_location


PLAN_ID_LINE = re.compile(r"(?m)^- plan_id = ([a-z0-9-]+)$")
APPROVAL_LINE = re.compile(r"(?m)^- approved_plan_digest = (sha256:[0-9a-f]{64})$")


def approved_plan_digest(text: str) -> str:
    excluded = {"## State", "## Active items", "## Learning Candidates"}
    kept: list[str] = []
    skip = False
    for line in text.splitlines(keepends=True):
        if line.startswith("## "):
            skip = line.strip() in excluded
        if not skip:
            kept.append(line)
    return "sha256:" + hashlib.sha256("".join(kept).encode("utf-8")).hexdigest()


def approval_receipt_path(root: Path, plan_id: str) -> Path:
    return git_location(root, "--git-common-dir") / "hard-eng" / "approvals" / f"{plan_id}.sha256"


def orphaned_approval_receipts(root: Path) -> tuple[str, ...]:
    receipt_root = git_location(root, "--git-common-dir") / "hard-eng" / "approvals"
    if not receipt_root.exists():
        return ()
    if receipt_root.is_symlink() or not receipt_root.is_dir():
        raise PlanStateError("approval receipt owner is not a regular directory")
    receipts: dict[str, str] = {}
    for receipt in receipt_root.glob("*.sha256"):
        if receipt.is_symlink() or not receipt.is_file():
            raise PlanStateError("approval receipt is not a regular file")
        receipts[receipt.stem] = receipt.read_text(encoding="ascii").strip()
    output = subprocess.check_output(
        ["git", "-C", str(root), "worktree", "list", "--porcelain", "-z"],
        text=True,
        timeout=30,
    )
    approved_ids: set[str] = set()
    for record in output.split("\0"):
        if not record.startswith("worktree "):
            continue
        worktree = Path(record.removeprefix("worktree "))
        for plan in worktree.glob("features/*/PLAN.md"):
            if plan.is_symlink() or not plan.is_file():
                continue
            try:
                text = plan.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                continue
            plan_id = PLAN_ID_LINE.search(text)
            approval = APPROVAL_LINE.search(text)
            if (
                plan_id
                and approval
                and receipts.get(plan_id.group(1)) == approval.group(1)
                and approved_plan_digest(text) == approval.group(1)
            ):
                approved_ids.add(plan_id.group(1))
    return tuple(sorted(set(receipts) - approved_ids))


def validate_approval_receipt(root: Path, state: dict[str, str]) -> None:
    if state["approved_plan_digest"] == "none":
        return
    receipt = approval_receipt_path(root, state["plan_id"])
    if receipt.is_symlink() or not receipt.is_file():
        raise PlanStateError("approved PLAN receipt is missing")
    if receipt.read_text(encoding="ascii") != state["approved_plan_digest"] + "\n":
        raise PlanStateError("approved PLAN receipt differs from approval digest")


def write_approval_receipt(root: Path, state: dict[str, str]) -> None:
    receipt = approval_receipt_path(root, state["plan_id"])
    receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = receipt.with_name(f".{receipt.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("x", encoding="ascii") as handle:
            handle.write(state["approved_plan_digest"] + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, receipt)
    finally:
        temporary.unlink(missing_ok=True)

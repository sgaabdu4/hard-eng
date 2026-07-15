"""Immutable approval digest + external receipt for Hard Eng PLAN content."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from plan_contract import PlanStateError
from plan_transfer import git_location


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

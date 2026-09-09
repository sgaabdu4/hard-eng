#!/usr/bin/env python3
"""Every file under an active feature's receipts folder is lifecycle state for the checkpoint."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from agent_hook_contract_lib import FAILURES, ROOT, check, manifest, plan

sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env

RECEIPT_FILES = ("S-1-review-1.txt", "S-1-verify.txt", "fakes.log", "S-1.json", "media/S-1-after.png")


def checkpoint(repo: Path) -> subprocess.CompletedProcess[str]:
    command = ["perl", str(ROOT / "scripts/enforcement_policy.pl"), "check", "."]
    return subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)


def check_state(root: Path, state: str) -> None:
    repo = root / f"receipts-{state}"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    active = plan(repo, "one", state)
    receipts = active.parent / "receipts"
    for name in RECEIPT_FILES:
        target = receipts / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("evidence\n", encoding="utf-8")
    allowed = checkpoint(repo)
    check(f"{state} checkpoint accepts every receipt file as lifecycle state", allowed.returncode == 0, allowed.stderr)
    if state == "building":
        return
    stray = active.parent / "notes.txt"
    stray.write_text("extra\n", encoding="utf-8")
    blocked = checkpoint(repo)
    check(
        f"{state} checkpoint still names a text file outside receipts",
        blocked.returncode != 0 and "notes.txt" in blocked.stderr,
        blocked.stderr,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-checkpoint-receipts-") as temporary:
        root = Path(temporary).resolve()
        for state in ("planning", "build-ready", "building"):
            check_state(root, state)
    if FAILURES:
        for failure in FAILURES:
            print(f"checkpoint-receipt-paths-contract: FAIL: {failure}", file=sys.stderr)
        return 1
    print("checkpoint-receipt-paths-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

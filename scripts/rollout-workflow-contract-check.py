#!/usr/bin/env python3
"""Prove the GitHub Actions rollout workflow keeps its safety contract: workflow_dispatch only, the rollout
secret and afenso identity, one repository at a time with the 40 second pause, the report artifact, and a
launcher that runs the checked-out install.sh rather than a local machine path or npx."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/rollout-shared.yml"


def fail(message: str) -> NoReturn:
    print(f"rollout-workflow-contract: {message}", file=sys.stderr)
    raise SystemExit(1)


def top_level_block(text: str, key: str) -> str:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line == f"{key}:":
            start = index + 1
            break
    if start is None:
        fail(f"missing top-level key: {key}")
    end = start
    while end < len(lines) and (lines[end] == "" or lines[end].startswith(" ")):
        end += 1
    return "\n".join(lines[start:end])


def step_block(text: str, name: str) -> str:
    marker = f"- name: {name}\n"
    start = text.find(marker)
    if start == -1:
        fail(f"missing workflow step: {name}")
    rest = text[start + len(marker) :]
    next_step = rest.find("\n      - name:")
    return rest if next_step == -1 else rest[:next_step]


def check_only_trigger_is_workflow_dispatch(text: str) -> None:
    triggers = re.findall(r"^  ([A-Za-z_][A-Za-z0-9_-]*):", top_level_block(text, "on"), flags=re.MULTILINE)
    if triggers != ["workflow_dispatch"]:
        fail(f"workflow_dispatch must be the only trigger, found: {triggers}")


def check_rollout_secret(text: str) -> None:
    if "secrets.HARD_ENG_ROLLOUT_TOKEN" not in text:
        fail("every write must authenticate with the secrets.HARD_ENG_ROLLOUT_TOKEN secret")


def check_afenso_identity(text: str) -> None:
    if 'user.name "sgaabdu4"' not in text:
        fail('rollout commits must set git user.name "sgaabdu4"')
    if 'user.email "abid.gafoor@afenso.com"' not in text:
        fail('rollout commits must set git user.email "abid.gafoor@afenso.com"')


def check_sequential_with_pause(text: str) -> None:
    if "time.sleep(40)" not in text:
        fail("repositories must be paced with a 40 second pause between them")
    for token in ("strategy:", "matrix:", "max-parallel"):
        if token in text:
            fail(f"repositories must be processed one at a time, found parallel fan-out: {token}")


def check_report_artifact(text: str) -> None:
    upload_step = step_block(text, "Upload rollout report")
    if "if: always()" not in upload_step:
        fail("the report artifact must upload even when a repository failed (if: always())")
    if not re.search(r"actions/upload-artifact@[0-9a-f]{40} # v\d", upload_step):
        fail("actions/upload-artifact must be pinned to an immutable commit with a version comment")
    if "rollout-shared-report" not in upload_step:
        fail("the uploaded artifact must be the rollout-shared-report")


def check_launcher_is_checked_out_install(text: str) -> None:
    rollout_step = step_block(text, "Roll out to every repository")
    if not re.search(r"GITHUB_WORKSPACE.*install\.sh", rollout_step):
        fail("the launcher must run the checked-out install.sh from GITHUB_WORKSPACE")
    if "npx" in rollout_step:
        fail("the launcher must not fall back to downloading through npx")
    if "/Users/" in rollout_step:
        fail("the launcher must not reference a local machine path")


def main() -> int:
    if not WORKFLOW.is_file() or WORKFLOW.is_symlink():
        fail("rollout-shared.yml is missing or not a regular file")
    text = WORKFLOW.read_text(encoding="utf-8")
    check_only_trigger_is_workflow_dispatch(text)
    check_rollout_secret(text)
    check_afenso_identity(text)
    check_sequential_with_pause(text)
    check_report_artifact(text)
    check_launcher_is_checked_out_install(text)
    print("rollout-workflow-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

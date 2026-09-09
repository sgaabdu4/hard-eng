#!/usr/bin/env python3
"""Artifact, widget and design tools are denied inside a governed repository and left alone elsewhere."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from agent_hook_contract_lib import FAILURES, ROOT, check, denial, manifest, run_hook

sys.path.insert(0, str(ROOT / "skills/deterministic-checks/scripts"))
from git_env import git_env

BLOCKED_TOOLS = ("Artifact", "mcp__visualize__show_widget", "mcp__visualize__read_me", "design")


def payload(repo: Path, tool_name: str) -> dict:
    return {"cwd": str(repo), "tool_name": tool_name, "tool_input": {"file_path": "widget.html"}}


def check_governed_repository(root: Path) -> None:
    repo = root / "artifact-configured"
    subprocess.run(["git", "init", "-q", str(repo)], check=True, env=git_env())
    manifest(repo)
    for tool_name in BLOCKED_TOOLS:
        response, _ = run_hook("codex", "pretooluse", payload(repo, tool_name))
        reason = denial(response, "codex")
        check(f"{tool_name} tool blocks inside a governed repository", bool(reason), repr(response))
        check(f"{tool_name} denial reason names the Artifact tool", "Artifact" in (reason or ""), repr(reason))


def check_unconfigured_repository(root: Path) -> None:
    repo = root / "artifact-unconfigured"
    repo.mkdir()
    (repo / ".git").mkdir()
    response, _ = run_hook("codex", "pretooluse", payload(repo, "Artifact"))
    check("Artifact tool is allowed in an unconfigured repository", response is None, repr(response))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="hard-eng-artifact-hook-") as temporary:
        root = Path(temporary).resolve()
        check_governed_repository(root)
        check_unconfigured_repository(root)
    if FAILURES:
        for failure in FAILURES:
            print(f"artifact-tool-contract: FAIL: {failure}", file=sys.stderr)
        return 1
    print("artifact-tool-contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

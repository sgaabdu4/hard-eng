"""Git identity + freshness checks for Hard Eng PLAN state."""
from __future__ import annotations

import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


def git_identity(repo: Path) -> tuple[Path, str, str]:
    root = Path(git(repo, "rev-parse", "--show-toplevel")).resolve()
    try:
        branch = git(root, "symbolic-ref", "--short", "HEAD")
    except subprocess.CalledProcessError:
        branch = "DETACHED"
    try:
        head = git(root, "rev-parse", "--verify", "HEAD")
    except subprocess.CalledProcessError:
        head = "UNBORN"
    return root, branch, head


def plan_only_head_drift(state: dict[str, str], root: Path, head: str, plan: Path) -> bool:
    recorded = state["head_sha"]
    if recorded in {"UNBORN", head}:
        return False
    ancestor = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", recorded, head],
        capture_output=True,
        text=True,
    )
    if ancestor.returncode != 0:
        return False
    changed = {line for line in git(root, "diff", "--name-only", f"{recorded}..{head}").splitlines() if line}
    return changed <= {str(plan.relative_to(root))}


def freshness_errors(
    state: dict[str, str], root: Path, branch: str, head: str, plan: Path
) -> list[str]:
    errors: list[str] = []
    if Path(state["repository_root"]).expanduser().resolve() != root:
        errors.append("repository_root")
    if state["branch"] != branch:
        errors.append("branch")
    if state["head_sha"] != head and not plan_only_head_drift(state, root, head, plan):
        errors.append("head_sha")
    if state["base_sha"] != "UNBORN":
        exists = subprocess.run(
            ["git", "-C", str(root), "cat-file", "-e", f'{state["base_sha"]}^{{commit}}'],
            capture_output=True,
        )
        ancestor = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", state["base_sha"], head],
            capture_output=True,
        )
        if exists.returncode != 0 or head == "UNBORN" or ancestor.returncode != 0:
            errors.append("base_sha")
    return errors

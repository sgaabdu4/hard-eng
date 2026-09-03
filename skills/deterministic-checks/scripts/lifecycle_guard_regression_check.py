#!/usr/bin/env python3
"""Regression: the lifecycle guard refuses product commits and pushes while a Feature Brief is build-ready or building."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(SCRIPT_DIR)]

from git_env import git_env
from script_runner import ScriptResult, run_script

GUARD = SCRIPT_DIR / "lifecycle_guard.py"
ZERO = "0" * 40


def fail(label: str) -> None:
    print(f"lifecycle-guard regression: FAIL ({label})")
    raise SystemExit(1)


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "user.name=t", "-c", "user.email=t@x", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        env=git_env(dict(os.environ)),
        check=False,
    )
    if result.returncode != 0:
        fail(f"git {' '.join(args)}: {result.stderr}")
    return result.stdout


def plan(repo: Path, slug: str, status: str) -> None:
    path = repo / "features" / slug / "PLAN.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"# Feature Brief\n\n<!-- hard-eng-state:v1 -->\n- state_version = 1\n- lifecycle_status = {status}\n"
        "<!-- /hard-eng-state -->\n",
        encoding="utf-8",
    )


def make_repo(base: Path, name: str) -> Path:
    repo = base / name
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "app.py").write_text("print(1)\n", encoding="utf-8")
    git(repo, "add", "app.py")
    git(repo, "commit", "-qm", "base")
    return repo


def guard(repo: Path, hook: str, refs: str | None = None) -> ScriptResult:
    return run_script(GUARD, [hook, "--repo", str(repo)], stdin=refs or "")


def stage_product(repo: Path, text: str) -> None:
    (repo / "app.py").write_text(text, encoding="utf-8")
    git(repo, "add", "app.py")


def check_commit(base: Path) -> None:
    repo = make_repo(base, "commit")
    stage_product(repo, "print(2)\n")
    if guard(repo, "commit").returncode != 0:
        fail("no plan refused a product commit")
    for status in ("planning", "green", "shipped", "cancelled"):
        plan(repo, "quiet", status)
        if guard(repo, "commit").returncode != 0:
            fail(f"{status} plan refused a product commit")
    for status in ("build-ready", "building"):
        plan(repo, "loud", status)
        result = guard(repo, "commit")
        if (
            result.returncode == 0
            or "features/loud/PLAN.md = " + status not in result.stderr
            or "app.py" not in result.stderr
        ):
            fail(f"{status} plan allowed a product commit: {result!r}")
    git(repo, "reset", "-q", "app.py")
    git(repo, "add", "features/loud/PLAN.md", "features/quiet/PLAN.md")
    (repo / "features/loud/receipts").mkdir()
    (repo / "features/loud/receipts/build-steps.json").write_text("{}\n", encoding="utf-8")
    (repo / ".agents/learning").mkdir(parents=True)
    (repo / ".agents/learning/x.json").write_text("{}\n", encoding="utf-8")
    git(repo, "add", "features/loud/receipts/build-steps.json", ".agents/learning/x.json")
    if guard(repo, "commit").returncode != 0:
        fail("lifecycle-only commit was refused while building")
    stage_product(repo, "print(3)\n")
    if guard(repo, "commit").returncode == 0:
        fail("plan staged together with product files was accepted")


def check_push(base: Path) -> None:
    repo = make_repo(base, "push")
    remote = base / "remote.git"
    git(repo, "init", "-q", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "-q", "origin", "main")
    base_sha = git(repo, "rev-parse", "HEAD").strip()
    plan(repo, "loud", "building")
    (repo / "app.py").write_text("print(4)\n", encoding="utf-8")
    git(repo, "add", "features/loud/PLAN.md", "app.py")
    git(repo, "commit", "-qm", "all six slices at once")
    head = git(repo, "rev-parse", "HEAD").strip()
    refs = f"refs/heads/main {head} refs/heads/main {base_sha}\n"
    result = guard(repo, "push", refs)
    if result.returncode == 0 or "push refused" not in result.stderr:
        fail(f"push with a building plan and product changes was accepted: {result!r}")
    new_branch = f"refs/heads/feature {head} refs/heads/feature {ZERO}\n"
    if guard(repo, "push", new_branch).returncode == 0:
        fail("new-branch push with a building plan was accepted")
    if guard(repo, "push", f"refs/heads/main {ZERO} refs/heads/main {head}\n").returncode != 0:
        fail("branch deletion was refused")
    plan(repo, "loud", "green")
    git(repo, "add", "features/loud/PLAN.md")
    git(repo, "commit", "-qm", "green")
    head = git(repo, "rev-parse", "HEAD").strip()
    if guard(repo, "push", f"refs/heads/main {head} refs/heads/main {base_sha}\n").returncode != 0:
        fail("green plan push was refused")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="lifecycle-guard-") as directory:
        base = Path(directory).resolve()
        check_commit(base)
        check_push(base)
    print("lifecycle-guard regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

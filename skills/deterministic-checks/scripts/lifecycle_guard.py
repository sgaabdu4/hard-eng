#!/usr/bin/env python3
"""Refuse product-path commits and pushes while any Feature Brief in the tree is build-ready or building."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HE_SCRIPTS = SCRIPT_DIR.parents[1] / "he" / "scripts"
sys.path[:0] = [str(SCRIPT_DIR), str(HE_SCRIPTS)]

from bounded_run import run_captured
from git_env import git_env
from safe_plan_io import lifecycle_excluded

ACTIVE = {"build-ready", "building"}
STATUS = re.compile(r"(?m)^- lifecycle_status = (\S+)")
ZERO = "0" * 40
SHOWN_PATHS = 5


class LifecycleGuardError(Exception):
    pass


GIT_TIMEOUT = 30.0


def git(repo: Path, *args: str) -> str:
    result = run_captured(["git", "-C", str(repo), *args], GIT_TIMEOUT, env=git_env())
    if result.returncode != 0:
        raise LifecycleGuardError(f"git {' '.join(args)}: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout.decode("utf-8", "replace")


def status_of(text: str) -> str | None:
    match = STATUS.search(text)
    return match.group(1) if match else None


def worktree_plans(repo: Path) -> dict[str, str]:
    plans = {}
    for plan in sorted((repo / "features").glob("*/PLAN.md")):
        try:
            text = plan.read_text(encoding="utf-8")
        except OSError:
            continue
        if (status := status_of(text)) is not None:
            plans[plan.relative_to(repo).as_posix()] = status
    return plans


def revision_plans(repo: Path, revision: str) -> dict[str, str]:
    plans = {}
    listing = git(repo, "ls-tree", "-r", "--name-only", revision, "--", "features")
    for path in sorted(line for line in listing.splitlines() if re.fullmatch(r"features/[^/]+/PLAN\.md", line)):
        if (status := status_of(git(repo, "show", f"{revision}:{path}"))) is not None:
            plans[path] = status
    return plans


def product_paths(paths: list[str]) -> list[str]:
    return [path for path in paths if path and not lifecycle_excluded(Path(path))]


def refusal(hook: str, plans: dict[str, str], paths: list[str]) -> str | None:
    active = {path: status for path, status in plans.items() if status in ACTIVE}
    changed = product_paths(paths)
    if not active or not changed:
        return None
    shown = ", ".join(changed[:SHOWN_PATHS]) + (" ..." if len(changed) > SHOWN_PATHS else "")
    plans_line = "; ".join(f"{path} = {status}" for path, status in active.items())
    return (
        f"lifecycle-guard: {hook} refused: product files change while a Feature Brief is still being built\n"
        f"  plans: {plans_line}\n"
        f"  files: {shown}\n"
        "  finish the slice loop to green and ship through he-ship, or `he reopen` / cancel the plan first"
    )


def commit_error(repo: Path) -> str | None:
    staged = git(repo, "diff", "--cached", "--name-only", "--diff-filter=ACMRD").splitlines()
    return refusal("commit", worktree_plans(repo), staged)


def pushed_paths(repo: Path, local_sha: str, remote_sha: str) -> list[str]:
    if remote_sha != ZERO:
        return git(repo, "diff", "--name-only", remote_sha, local_sha).splitlines()
    commits = git(repo, "rev-list", local_sha, "--not", "--remotes").split()
    paths: list[str] = []
    for commit in commits:
        paths += git(repo, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit).splitlines()
    return sorted(set(paths))


def push_error(repo: Path, ref_lines: str) -> str | None:
    for line in ref_lines.splitlines():
        parts = line.split()
        if len(parts) != 4 or parts[1] == ZERO:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        if error := refusal("push", revision_plans(repo, local_sha), pushed_paths(repo, local_sha, remote_sha)):
            return error
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hook", choices=("commit", "push"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--refs-file", help="pre-push stdin saved to a file; defaults to stdin")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        if args.hook == "commit":
            error = commit_error(repo)
        else:
            refs = Path(args.refs_file).read_text(encoding="utf-8") if args.refs_file else sys.stdin.read()
            error = push_error(repo, refs)
    except LifecycleGuardError as failure:
        print(f"lifecycle-guard: {failure}", file=sys.stderr)
        return 1
    if error:
        print(error, file=sys.stderr)
        return 1
    print(f"lifecycle-guard: {args.hook} PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

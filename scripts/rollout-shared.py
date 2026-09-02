#!/usr/bin/env python3
"""Share Hard Eng with one repository from a fresh clone: set it up shared, commit, and push or open a pull request."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_LAUNCHER = ("npx", "-y", "github:sgaabdu4/hard-eng")
FALLBACK_BRANCH = "hard-eng-shared-wiring"
TIMEOUT_SECONDS = 900
PULL_REQUEST_BODY = (
    "Adds the committed Hard Eng shared wiring: the pinned release, the bootstrap, the guard shim, "
    "the hook entries, and the generated rule files. Every clone downloads and verifies that release at session start."
)


class RolloutError(Exception):
    pass


def run(command: list[str], *, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    process = subprocess.Popen(
        command,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise RolloutError(f"{' '.join(command)} exceeded {TIMEOUT_SECONDS} seconds") from None
    result = subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    if check and result.returncode != 0:
        raise RolloutError(f"{' '.join(command)} failed: {(result.stderr or result.stdout).strip()}")
    return result


def git(clone: Path, *arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *arguments], cwd=clone, check=check)


def clone_repository(repository: str, work: Path) -> Path:
    name = repository.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git") or "repository"
    clone = work / name
    if clone.exists():
        raise RolloutError(f"{clone} already exists; use an empty work directory")
    run(["git", "clone", "-q", repository, str(clone)], cwd=work)
    return clone


def checkout_branch(clone: Path, requested: str | None) -> str:
    if requested:
        git(clone, "checkout", "-q", requested)
        return requested
    head = git(clone, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    name = head.stdout.strip()
    if head.returncode != 0 or not name.startswith("origin/"):
        raise RolloutError("origin has no default branch; pass --branch")
    return name[len("origin/") :]


def install_shared(clone: Path, launcher: list[str], home: str | None) -> None:
    command = [*launcher, "--repo", "--shared", *(["--home", home] if home else [])]
    result = run(command, cwd=clone, check=False)
    if result.returncode != 0:
        raise RolloutError(f"Hard Eng setup failed in {clone}: {(result.stderr or result.stdout).strip()}")


def pinned_version(clone: Path) -> str:
    marker = json.loads((clone / "hard-eng.gates.json").read_text(encoding="utf-8"))
    return str(marker["hard_eng"]["pin"]["tag"])


def pending_changes(clone: Path) -> bool:
    return bool(git(clone, "status", "--porcelain", "--untracked-files=all").stdout.strip())


def commit_changes(clone: Path, message: str) -> str:
    git(clone, "add", "--all")
    git(clone, "commit", "-q", "-m", message)
    if pending_changes(clone):
        raise RolloutError(f"unexpected changes remain after the commit in {clone}")
    return git(clone, "rev-parse", "HEAD").stdout.strip()


def push_changes(clone: Path, branch: str, title: str) -> tuple[str, str | None]:
    if git(clone, "push", "-q", "origin", f"HEAD:refs/heads/{branch}", check=False).returncode == 0:
        return branch, None
    git(clone, "push", "-q", "--force-with-lease", "origin", f"HEAD:refs/heads/{FALLBACK_BRANCH}")
    command = ["gh", "pr", "create", "--base", branch, "--head", FALLBACK_BRANCH, "--title", title]
    created = run([*command, "--body", PULL_REQUEST_BODY], cwd=clone, check=False)
    lines = created.stdout.strip().splitlines()
    return FALLBACK_BRANCH, lines[-1] if created.returncode == 0 and lines else None


def report(result: dict[str, object], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, sort_keys=True))
        return
    print(f"repository: {result['repository']}")
    print(f"clone: {result['clone']}")
    print(f"version: {result['version']}")
    if not result["changed"]:
        print(f"already shared at {result['version']}; nothing to push")
    elif result["pushed"]:
        print(f"committed {result['commit']} and pushed it to {result['branch']}")
    elif result["pull_request"]:
        print(f"pushed {result['pushed_branch']}; pull request: {result['pull_request']}")
    else:
        print(f"pushed {result['pushed_branch']}; open a pull request into {result['branch']}")


def rollout(arguments: argparse.Namespace) -> dict[str, object]:
    work = (
        Path(arguments.work_dir).resolve() if arguments.work_dir else Path(tempfile.mkdtemp(prefix="hard-eng-rollout-"))
    )
    work.mkdir(parents=True, exist_ok=True)
    clone = clone_repository(arguments.repository, work)
    branch = checkout_branch(clone, arguments.branch)
    install_shared(clone, arguments.launcher, arguments.home)
    version = pinned_version(clone)
    result: dict[str, object] = {
        "repository": arguments.repository,
        "clone": str(clone),
        "branch": branch,
        "version": version,
        "changed": pending_changes(clone),
        "commit": None,
        "pushed": False,
        "pushed_branch": None,
        "pull_request": None,
    }
    if not result["changed"]:
        return result
    title = f"Share Hard Eng {version} with every clone"
    result["commit"] = commit_changes(clone, arguments.message or f"chore: share Hard Eng {version} with every clone")
    pushed_branch, pull_request = push_changes(clone, branch, title)
    result.update(pushed=pushed_branch == branch, pushed_branch=pushed_branch, pull_request=pull_request)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Share Hard Eng with one repository from a fresh clone.")
    parser.add_argument("--repository", required=True, help="anything git clone accepts: URL or path")
    parser.add_argument("--work-dir", help="empty directory for the clone (default: a new temporary directory)")
    parser.add_argument("--branch", help="target branch (default: the origin default branch)")
    parser.add_argument(
        "--launcher", nargs="+", default=list(DEFAULT_LAUNCHER), help="command that accepts --repo --shared"
    )
    parser.add_argument("--home", help="home directory the launcher should use")
    parser.add_argument("--message", help="commit message override")
    parser.add_argument("--json", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        result = rollout(arguments)
    except RolloutError as error:
        print(f"rollout-shared: FAIL: {error}", file=sys.stderr)
        return 1
    report(result, json_output=arguments.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

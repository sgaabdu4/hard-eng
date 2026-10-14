"""Try a Hard Eng release on every installed project before it merges; results stay on this machine."""

import argparse
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import IO

SOURCE = Path(__file__).resolve().parent
UPSTREAM = "sgaabdu4/hard-eng"
CACHE = Path.home() / "Library/Caches/hard-eng-canary"
SOURCE_ONLY = ("tests/", "features/", "docs/", "assets/")
SOURCE_ONLY_FILES = {
    "README.md",
    "PLAN.md",
    "DECISION.md",
    "actor-prompt.md",
    "AGENTS.override.md",
}
# Runs the project's own installed updater, told that this release is the newest verified one.
UPDATE = """
import sys
from pathlib import Path
sys.path.insert(0, ".hooks")
import update
update.latest_verified = lambda previous: sys.argv[1]
from update_runner import locked_update
print(locked_update(Path(".").resolve()))
"""


def needs_canary(names: list[str]) -> bool:
    return any(
        not name.startswith(SOURCE_ONLY) and name not in SOURCE_ONLY_FILES
        for name in names
    )


def status_text(results: dict[str, tuple[bool, str]]) -> str:
    passed = sum(ok for ok, _ in results.values())
    return f"{passed} of {len(results)} installed projects passed"


def output(command: list[str], cwd: Path = SOURCE) -> str:
    return subprocess.check_output(command, cwd=cwd, text=True, timeout=300).strip()


def installed_projects() -> list[str]:
    owners = [output(["gh", "api", "user", "-q", ".login"])]
    owners += output(["gh", "api", "user/orgs", "-q", ".[].login"]).split()
    found = {
        name
        for owner in owners
        for name in output(
            [
                *("gh", "search", "code", "--owner", owner),
                *("--filename", "hard-eng-source.json", "--limit", "200"),
                *("--json", "repository", "-q", ".[].repository.nameWithOwner"),
            ]
        ).split()
    }
    print(f"Found {len(found)} installed projects across {len(owners)} owners.")
    return sorted(
        name
        for name in found - {UPSTREAM}
        if output(["gh", "api", f"repos/{name}", "-q", ".archived"]) == "false"
    )


def step(command: list[str], cwd: Path, log: IO[str], limit: int) -> bool:
    log.write(f"\n$ {' '.join(command)}\n")
    log.flush()
    try:
        done = subprocess.run(
            command,
            check=False,
            cwd=cwd,
            stdout=log,
            stderr=subprocess.STDOUT,
            timeout=limit,
        )
    except subprocess.TimeoutExpired:
        log.write(f"Stopped after {limit} seconds.\n")
        return False
    return done.returncode == 0


def try_project(name: str, revision: str, run: Path) -> tuple[bool, str]:
    """Clone, update with the project's own updater, then run its CI check on the update."""
    work = run / name.replace("/", "__")
    log_path = work.with_suffix(".log")
    with log_path.open("w") as log:
        url = f"https://github.com/{name}.git"
        if not step(
            ["git", "clone", "-q", "--filter=blob:none", url, str(work)], run, log, 900
        ):
            return False, f"clone failed; log {log_path}"
        for command in (
            ["git", "remote", "set-url", "--push", "origin", "no-push"],
            ["git", "submodule", "update", "-q", "--init", "--recursive"],
        ):
            if not step(command, work, log, 900):
                return False, f"setup failed; log {log_path}"
        if not step([sys.executable, "-c", UPDATE, revision], work, log, 1800):
            return False, f"update failed; log {log_path}"
        # Older updaters commit on the checked-out branch instead of hard-eng/update.
        if output(["git", "branch", "--list", "hard-eng/update"], work):
            step(["git", "checkout", "-q", "hard-eng/update"], work, log, 300)
        base = output(["git", "rev-parse", "origin/HEAD"], work)
        if output(["git", "rev-parse", "HEAD"], work) == base:
            shutil.rmtree(work)
            return True, "no update needed"
        check = [sys.executable, ".hooks/hard-eng.py", "check", "--base", base]
        if not step(check, work, log, 2700):
            return False, f"check failed; log {log_path}"
    shutil.rmtree(work)
    return True, "update and check passed"


def post_status(revision: str, state: str, description: str) -> None:
    output(
        [
            *("gh", "api", f"repos/{UPSTREAM}/statuses/{revision}"),
            *("-f", f"state={state}", "-f", "context=canary"),
            *("-f", f"description={description}"),
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("revision", help="Hard Eng commit whose CI already passed")
    parser.add_argument(
        "--project", action="append", help="OWNER/NAME; rerun only these"
    )
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--post-status", action="store_true")
    args = parser.parse_args()
    if args.project and args.post_status:
        parser.error("--post-status needs a full run, not --project")
    revision = output(["git", "rev-parse", "--verify", args.revision + "^{commit}"])
    names = output(["git", "diff", "--name-only", f"origin/main...{revision}"]).split()
    if not needs_canary(names):
        print("No installed file changed; nothing to try.")
        if args.post_status:
            post_status(revision, "success", "No installed file changed")
        return 0
    projects = args.project or installed_projects()
    token = output(["gh", "auth", "token"])
    os.environ.update(GH_TOKEN=token, GITHUB_TOKEN=token)
    if CACHE.is_dir():
        shutil.rmtree(CACHE)
    run = CACHE / time.strftime("run-%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    with ThreadPoolExecutor(args.jobs) as pool:
        outcomes = pool.map(partial(try_project, revision=revision, run=run), projects)
        results = dict(zip(projects, outcomes, strict=True))
    for name, (ok, detail) in results.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    passed = all(ok for ok, _ in results.values())
    print(status_text(results))
    if args.post_status:
        post_status(revision, "success" if passed else "failure", status_text(results))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

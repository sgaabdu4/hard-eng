"""Try a Hard Eng release on every installed project before it merges; results stay on this machine."""

import argparse
import fcntl
import json
import os
import shutil
import signal
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
LOCK = CACHE.with_name("hard-eng-canary.lock")
SOURCE_ONLY = ("tests/", "features/", "docs/", "assets/")
SOURCE_ONLY_FILES = {
    "README.md",
    "PLAN.md",
    "DECISION.md",
    "AGENTS.override.md",
    "release_canary.py",
}
# Runs the project's own installed updater, told that this release is the newest verified one.
UPDATE = """
import sys
from pathlib import Path
sys.path.insert(0, ".hooks")
import update
update.latest_verified = lambda previous: sys.argv[1]
try:
    from update_runner import locked_update
except ImportError:
    locked_update = update.update
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


def installed(name: str) -> bool:
    """Whether the default branch holds Hard Eng's marker; other errors stop the run."""
    marker = f"repos/{name}/contents/.hooks/hard-eng-source.json"
    found = subprocess.run(
        ["gh", "api", marker, "--silent"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if found.returncode and "HTTP 404" not in found.stderr:
        raise RuntimeError(f"cannot read {marker}: {found.stderr.strip()}")
    return found.returncode == 0


def installed_projects() -> list[str]:
    names = output(
        [
            *(
                "gh",
                "api",
                "--paginate",
                "-q",
                ".[] | select(.archived | not) | .full_name",
            ),
            "user/repos?affiliation=owner,collaborator,organization_member&per_page=100",
        ]
    ).split()
    found = [name for name in names if name != UPSTREAM and installed(name)]
    print(f"{len(found)} of {len(names)} accessible repositories have Hard Eng.")
    return found


def step(command: list[str], cwd: Path, log: IO[str], limit: int) -> bool:
    log.write(f"\n$ {' '.join(command)}\n")
    log.flush()
    process = subprocess.Popen(
        command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True
    )
    try:
        return process.wait(timeout=limit) == 0
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
        log.write(f"Stopped after {limit} seconds.\n")
        return False


def try_project(name: str, revision: str, run: Path) -> tuple[bool, str]:
    """Clone, update with the project's own updater, then run its update PR check and every gate."""
    work = run / name.replace("/", "__")
    log_path = work.with_name(f"{work.name}.log")
    with log_path.open("w") as log:
        url = f"https://github.com/{name}.git"
        if not step(["git", "clone", "-q", url, str(work)], run, log, 1800):
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
        if output(["git", "branch", "--list", "hard-eng/update"], work) and not step(
            ["git", "checkout", "-q", "hard-eng/update"], work, log, 300
        ):
            return False, f"update branch checkout failed; log {log_path}"
        marker = json.loads((work / ".hooks/hard-eng-source.json").read_text())
        if marker.get("revision") != revision:
            return False, f"update did not apply; log {log_path}"
        base = output(["git", "rev-parse", "origin/HEAD"], work)
        check = [sys.executable, ".hooks/hard-eng.py", "check"]
        # The update PR's check can skip gates for a proven update, so every gate runs after it.
        for label, command in (
            ("update PR check", [*check, "--base", base]),
            ("full check", check),
        ):
            if not step(command, work, log, 3600):
                return False, f"{label} failed; log {log_path}"
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


def arguments() -> argparse.Namespace:
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
    return args


def main() -> int:
    args = arguments()
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another canary run is active; wait for it to finish.")
            return 1
        return canary(args)


def canary(args: argparse.Namespace) -> int:
    revision = output(["git", "rev-parse", "--verify", args.revision + "^{commit}"])
    names = output(["git", "diff", "--name-only", f"origin/main...{revision}"]).split()
    if not needs_canary(names):
        print("No installed file changed; nothing to try.")
        if args.post_status:
            post_status(revision, "success", "No installed file changed")
        return 0
    if args.post_status:
        post_status(revision, "pending", "Trying the release on installed projects")
    projects = args.project or installed_projects()
    if not projects:
        print("No installed project found; the release is untested.")
        if args.post_status:
            post_status(revision, "failure", "No installed project found")
        return 1
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

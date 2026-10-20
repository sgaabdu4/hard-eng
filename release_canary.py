"""Try a Hard Eng release on new and installed projects under Claude and Codex; results stay on this machine."""

import argparse
import fcntl
import json
import os
import re
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
STACKS = ("flutter", "nextjs", "opennext", "vite")
# A public project keeps the brownfield target reproducible and free of private names.
BROWNFIELD = (
    "https://github.com/pallets/itsdangerous.git",
    "672971d66a2ef9f85151e53283113f33d642dabd",
)
KINDS = ("installed", "scaffold", "greenfield", "brownfield")
AGENTS = ("claude", "codex")
TASK = (
    "Follow AGENTS.md and the Hard Eng workflow. In this project's main language, add a "
    "function that returns the sum of two integers and a test that proves it. Run the "
    "project's checks until they pass. Do not commit or push."
)


DOCUMENTS = {
    "PRODUCT.md": (
        "# Canary\n\nA throwaway project for a Hard Eng release trial.\n\n"
        "## Users\n\nThe Hard Eng maintainer.\n\n"
        "## Problem\n\nA release must install and pass in a real project.\n\n"
        "## Product Purpose\n\nGive the release a project to install into.\n\n"
        "## Boundaries\n\nNo users, data or deployment.\n"
    ),
    "DESIGN.md": (
        "# Canary\n\n## Overview\n\nNo visual design.\n\n"
        "## Components\n\nNone.\n\n## Do's and Don'ts\n\nKeep it minimal.\n"
    ),
}


class Failed(Exception):
    pass


def needs_canary(names: list[str]) -> bool:
    return any(
        not name.startswith(SOURCE_ONLY) and name not in SOURCE_ONLY_FILES
        for name in names
    )


def status_text(results: dict[str, tuple[bool, str]]) -> str:
    passed = sum(ok for ok, _ in results.values())
    return f"{passed} of {len(results)} canary runs passed"


def leaked_names(text: str, projects: list[str]) -> list[str]:
    """Private project names in public release text; owners are public already."""
    names = {part for name in projects for part in (name, name.split("/")[-1])}
    names.discard(UPSTREAM.split("/")[0])
    return sorted(
        name
        for name in names
        if re.search(
            rf"(?<![\w./-]){re.escape(name)}(?![\w/-]|\.\w)", text, re.IGNORECASE
        )
    )


def public_text(revision: str) -> str:
    """Commit messages, added lines and the titles and bodies of every PR in the release."""
    span = f"origin/main..{revision}"
    pulls = {pulls_of(sha) for sha in output(["git", "rev-list", span]).split()}
    diff = output(["git", "diff", f"origin/main...{revision}"]).splitlines()
    added = [line for line in diff if line.startswith("+")]
    return "\n".join([output(["git", "log", "--format=%B", span]), *added, *pulls])


def pulls_of(sha: str) -> str:
    """GitHub sometimes cuts a reply short, so one failed read is retried."""
    command = ["gh", "api", f"repos/{UPSTREAM}/commits/{sha}/pulls"]
    command += ["-q", ".[] | .title, .body"]
    for _ in range(2):
        try:
            return output(command)
        except subprocess.CalledProcessError:
            time.sleep(5)
    return output(command)


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


def repositories() -> list[tuple[str, bool, bool]]:
    """Every repository this account can read: name, private, archived."""
    rows = output(
        [
            *("gh", "api", "--paginate", "-q"),
            r'.[] | "\(.full_name) \(.private) \(.archived)"',
            "user/repos?affiliation=owner,collaborator,organization_member&per_page=100",
        ]
    ).splitlines()
    return [
        (name, private == "true", archived == "true")
        for name, private, archived in (row.split() for row in rows)
    ]


def installed_projects(found: list[tuple[str, bool, bool]]) -> list[str]:
    names = [name for name, _, archived in found if not archived and name != UPSTREAM]
    projects = [name for name in names if installed(name)]
    print(f"{len(projects)} of {len(names)} accessible repositories have Hard Eng.")
    return projects


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


def must(cwd: Path, log: IO[str], failure: str, *commands: list[str]) -> None:
    for command in commands:
        if not step(command, cwd, log, 3600):
            raise Failed(failure)


def update_installed(name: str, revision: str, work: Path, log: IO[str]) -> str:
    """Clone, then update with the project's own updater; returns the check base."""
    url = f"https://github.com/{name}.git"
    must(work.parent, log, "clone failed", ["git", "clone", "-q", url, str(work)])
    must(
        work,
        log,
        "setup failed",
        ["git", "remote", "set-url", "--push", "origin", "no-push"],
        ["git", "submodule", "update", "-q", "--init", "--recursive"],
    )
    must(work, log, "update failed", [sys.executable, "-c", UPDATE, revision])
    # Older updaters commit on the checked-out branch instead of hard-eng/update.
    if output(["git", "branch", "--list", "hard-eng/update"], work):
        must(
            work,
            log,
            "update branch checkout failed",
            ["git", "checkout", "-q", "hard-eng/update"],
        )
    marker = json.loads((work / ".hooks/hard-eng-source.json").read_text())
    if marker.get("revision") != revision:
        raise Failed("update did not apply")
    return output(["git", "rev-parse", "origin/HEAD"], work)


def add_documents(work: Path) -> None:
    """The documents an agent would fill from the project, so the first check can pass."""
    for name, text in DOCUMENTS.items():
        if not (work / name).exists():
            (work / name).write_text(text)


def folder(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower())


def install_new(kind: str, value: str, source: Path, work: Path, log: IO[str]) -> str:
    """Create the target, install Hard Eng from the release and commit; returns the pre-install commit."""
    if kind == "brownfield":
        clone = ["git", "clone", "-q", BROWNFIELD[0], str(work)]
        must(work.parent, log, "clone failed", clone)
        must(
            work,
            log,
            "clone failed",
            ["git", "checkout", "-q", "--detach", BROWNFIELD[1]],
        )
    else:
        work.mkdir()
        must(work, log, "setup failed", ["git", "init", "-q"])
    if kind == "greenfield":
        must(
            work,
            log,
            "setup failed",
            ["uv", "init", "-q", "--app"],
            ["uv", "lock", "-q"],
            ["git", "add", "--all"],
            ["git", "commit", "-q", "-m", "Create the project"],
        )
    base = output(["git", "rev-parse", "HEAD"], work) if kind == "brownfield" else ""
    new = ["--new", value] if kind == "scaffold" else []
    must(work, log, "setup failed", ["sh", str(source / "setup.sh"), str(source), *new])
    add_documents(work)
    must(
        work,
        log,
        "setup failed",
        ["git", "add", "--all"],
        ["git", "commit", "-q", "--allow-empty", "-m", "Install Hard Eng"],
    )
    return base


def prepare(
    target: tuple[str, str], revision: str, source: Path, work: Path, log: IO[str]
) -> list[tuple[str, list[str]]]:
    kind, value = target
    check = [sys.executable, ".hooks/hard-eng.py", "check"]
    if kind == "installed":
        base = update_installed(value, revision, work, log)
        # The update PR's check can skip gates for a proven update, so every gate runs after it.
        return [("update PR check", [*check, "--base", base]), ("full check", check)]
    base = install_new(kind, value, source, work, log)
    # Brownfield code predates Hard Eng's gates; only the install's own change must pass.
    return [("check", [*check, "--base", base])] if base else [("full check", check)]


def agent_command(agent: str, work: Path) -> list[str]:
    if agent == "claude":
        return ["claude", "-p", "--dangerously-skip-permissions", TASK]
    trust = f'projects."{work}".trust_level="trusted"'
    return [
        *("codex", "exec", "--enable", "hooks"),
        "--dangerously-bypass-approvals-and-sandbox",
        "-c",
        trust,
        TASK,
    ]


def hard_eng_passed(work: Path) -> bool:
    """The Stop hook records a passing check in the session file that SessionStart created."""
    sessions = (work / ".hard-eng/sessions").glob("*.json")
    return any("verified" in json.loads(path.read_text()) for path in sessions)


def git_locks(folder: str, names: list[str]) -> set[str]:
    """Git's background maintenance creates and removes these while the copy runs."""
    inside_git = ".git" in Path(folder).parts
    return {name for name in names if inside_git and name.endswith(".lock")}


def try_agent(agent: str, work: Path, log: IO[str]) -> tuple[bool, str]:
    copy = work.with_name(f"{work.name}.{agent}")
    shutil.copytree(work, copy, symlinks=True, ignore=git_locks)
    try:
        head = output(["git", "rev-parse", "HEAD"], copy)
        if not step(agent_command(agent, copy), copy, log, 3600):
            return False, f"{agent} run failed"
        must(copy, log, f"{agent} result unreadable", ["git", "add", "--all"])
        if not output(["git", "diff", "--cached", "--name-only", head], copy):
            return False, f"{agent} changed nothing"
        if not hard_eng_passed(copy):
            return False, f"{agent} ended without a passing Hard Eng check"
        return True, f"{agent} passed"
    except Failed as failure:
        return False, str(failure)
    finally:
        shutil.rmtree(copy)


def try_target(
    target: tuple[str, str],
    revision: str,
    source: Path,
    run: Path,
    agents: tuple[str, ...],
) -> dict[str, tuple[bool, str]]:
    """Prepare one target and run its checks, then one agent session per agent CLI."""
    label = " ".join(target)
    work = run / folder(label)
    log_path = work.with_name(f"{work.name}.log")
    with log_path.open("w") as log:
        try:
            for name, command in prepare(target, revision, source, work, log):
                must(work, log, f"{name} failed", command)
        except Failed as failure:
            skipped = {f"{label} / {agent}": (False, "not run") for agent in agents}
            return {label: (False, f"{failure}; log {log_path}"), **skipped}
        results = {label: (True, "install and checks passed")}
        for agent in agents:
            ok, detail = try_agent(agent, work, log)
            results[f"{label} / {agent}"] = (
                ok,
                detail if ok else f"{detail}; log {log_path}",
            )
    if all(ok for ok, _ in results.values()):
        shutil.rmtree(work)
    return results


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
    parser.add_argument(
        "--kind", action="append", choices=KINDS, help="rerun only these targets"
    )
    parser.add_argument(
        "--agent", action="append", choices=AGENTS, help="rerun only these agents"
    )
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--post-status", action="store_true")
    args = parser.parse_args()
    if (args.project or args.kind or args.agent) and args.post_status:
        parser.error("--post-status needs a full run, not --project, --kind or --agent")
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


def targets(args: argparse.Namespace, projects: list[str]) -> list[tuple[str, str]]:
    found = {
        "installed": [("installed", name) for name in args.project or projects],
        "scaffold": [("scaffold", stack) for stack in STACKS],
        "greenfield": [("greenfield", "python")],
        "brownfield": [("brownfield", "itsdangerous")],
    }
    return [target for kind in args.kind or KINDS for target in found[kind]]


def release_source(revision: str, run: Path) -> Path:
    """A checkout of the release for setup in new projects."""
    source = run / "source"
    output(["git", "clone", "-q", str(SOURCE), str(source)], run)
    output(["git", "checkout", "-q", "--detach", revision], source)
    output(["git", "submodule", "update", "-q", "--init", "--recursive"], source)
    return source


def finish(
    revision: str, args: argparse.Namespace, state: str, description: str
) -> int:
    print(description)
    if args.post_status:
        post_status(revision, state, description)
    return 0 if state == "success" else 1


def canary(args: argparse.Namespace) -> int:
    revision = output(["git", "rev-parse", "--verify", args.revision + "^{commit}"])
    names = output(["git", "diff", "--name-only", f"origin/main...{revision}"]).split()
    found = repositories()
    private = [name for name, hidden, _ in found if hidden]
    if leaks := leaked_names(public_text(revision), private):
        print(f"The release names private projects: {', '.join(leaks)}")
        return finish(revision, args, "failure", "The release names a private project")
    if not needs_canary(names):
        return finish(revision, args, "success", "No installed file changed")
    if args.post_status:
        post_status(
            revision, "pending", "Trying the release on new and installed projects"
        )
    projects = installed_projects(found) if not args.project else []
    if not args.project and not projects and "installed" in (args.kind or KINDS):
        return finish(revision, args, "failure", "No installed project found")
    token = output(["gh", "auth", "token"])
    os.environ.update(GH_TOKEN=token, GITHUB_TOKEN=token)
    if CACHE.is_dir():
        shutil.rmtree(CACHE)
    run = CACHE / time.strftime("run-%Y%m%d-%H%M%S")
    run.mkdir(parents=True)
    source = release_source(revision, run)
    agents = tuple(args.agent or AGENTS)
    attempt = partial(
        try_target, revision=revision, source=source, run=run, agents=agents
    )
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(args.jobs) as pool:
        for outcome in pool.map(attempt, targets(args, projects)):
            results.update(outcome)
    shutil.rmtree(source)
    for name, (ok, detail) in results.items():
        print(f"{'PASS' if ok else 'FAIL'} {name}: {detail}")
    passed = all(ok for ok, _ in results.values())
    return finish(
        revision, args, "success" if passed else "failure", status_text(results)
    )


if __name__ == "__main__":
    sys.exit(main())

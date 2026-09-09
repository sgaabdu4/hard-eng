"""Install and update the repository-local runtime using native Git submodules."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hard_eng import config, git_hooks
from hard_eng.common import GateError, array, checked, git, object_value, write_file

UPSTREAM = "https://github.com/sgaabdu4/hard-eng.git"
PROJECT = "sgaabdu4/hard-eng"


def latest_green(runtime: Path) -> str:
    git(runtime, "fetch", "origin", "main")
    output = checked(
        [
            "gh",
            "api",
            "--paginate",
            "--slurp",
            f"repos/{PROJECT}/actions/workflows/hard-eng-gates.yml/runs?branch=main&event=push&status=success&per_page=100",
        ],
        runtime,
    )
    successful: set[str] = set()
    pages: object = json.loads(output)
    for page in array(pages, "workflow pages"):
        for value in array(object_value(page, "workflow page").get("workflow_runs"), "workflow runs"):
            run = object_value(value, "workflow run")
            revision = run.get("head_sha")
            if (
                isinstance(revision, str)
                and run.get("conclusion") == "success"
                and run.get("status") == "completed"
                and run.get("head_branch") == "main"
                and run.get("event") == "push"
            ):
                successful.add(revision)
    for revision in git(runtime, "rev-list", "origin/main").splitlines():
        if revision in successful:
            return revision
    raise GateError("No main commit has a successful Hard Eng workflow; repair upstream CI first")


def update(root: Path) -> str:
    runtime = root / ".hard-eng"
    if not (runtime / ".git").is_file():
        raise GateError("Run the repository-local installation before session startup")
    if git(runtime, "status", "--porcelain") or git(root, "status", "--porcelain", "--", ".hard-eng"):
        raise GateError(
            "Local Hard Eng changes conflict with automatic update; preserve and resolve them first"
        )
    revision = latest_green(runtime)
    previous = git(runtime, "rev-parse", "HEAD").strip()
    if previous == revision:
        return "Hard Eng is current"
    git(runtime, "checkout", "--detach", revision)
    try:
        git(root, "commit", "--only", "-m", f"Update Hard Eng to {revision[:12]}", "--", ".hard-eng")
    except GateError:
        git(runtime, "checkout", "--detach", previous)
        raise
    return f"Updated Hard Eng to {revision[:12]} in a separate commit"


def instructions(root: Path) -> None:
    path = root / "AGENTS.md"
    reference = "Follow [.hard-eng/skills/he/SKILL.md](.hard-eng/skills/he/SKILL.md) for engineering work."
    existing = path.read_text() if path.exists() else "# Agent Rules\n"
    if reference not in existing:
        write_file(path, existing.rstrip() + "\n\n" + reference + "\n")
    claude = root / "CLAUDE.md"
    if not claude.exists():
        write_file(claude, "@AGENTS.md\n")
    ignore = root / ".gitignore"
    existing = ignore.read_text() if ignore.exists() else ""
    additions = [
        entry for entry in ("/coverage/", "/.codebase-memory/") if entry not in existing.splitlines()
    ]
    if additions:
        write_file(ignore, existing.rstrip() + "\n" + "\n".join(additions) + "\n")


def install(root: Path) -> None:
    config.load(root)
    runtime = root / ".hard-eng"
    if runtime.exists():
        raise GateError(".hard-eng already exists; use session to update an installed runtime")
    if git(root, "status", "--porcelain", "--", ".gitmodules"):
        raise GateError(".gitmodules has local changes; resolve them before installation")
    with tempfile.TemporaryDirectory(prefix="hard-eng-install-") as temporary:
        candidate = Path(temporary) / "source"
        git(root, "clone", "--no-checkout", "--filter=blob:none", "--", UPSTREAM, str(candidate))
        revision = latest_green(candidate)
    git(root, "submodule", "add", "--", UPSTREAM, ".hard-eng")
    git(runtime, "checkout", "--detach", revision)
    git(root, "add", "--", ".hard-eng")
    instructions(root)
    git_hooks.install(root, ".hard-eng/bin/hard-eng")
    print("Installed repository-local Hard Eng. Commit the installation with the project.")

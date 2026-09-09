"""Install shared files into a project; temporary Git clones supply verified updates."""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from hard_eng import git_hooks
from hard_eng.common import GateError, array, checked, git, object_value, relative_path, run, write_file

UPSTREAM = "https://github.com/sgaabdu4/hard-eng.git"
PROJECT = "sgaabdu4/hard-eng"
OWNED = {
    "bin": ".agents/hard-eng/bin",
    "hard_eng": ".agents/hard-eng/hard_eng",
    "security": ".agents/hard-eng/security",
    "skills/he": ".agents/skills/he",
    "skills/research": ".agents/skills/research",
}


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


@contextmanager
def verified_source(root: Path) -> Generator[Path, None, None]:
    with tempfile.TemporaryDirectory(prefix="hard-eng-source-") as directory:
        source = Path(directory) / "source"
        git(root, "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--", UPSTREAM, str(source))
        git(source, "checkout", "--quiet", "--detach", latest_green(source))
        yield source


def changed_files(root: Path, source: Path) -> list[tuple[Path, Path]]:
    changed: list[tuple[Path, Path]] = []
    for name, destination in OWNED.items():
        target = relative_path(root, destination)
        if target.is_symlink():
            raise GateError(f"Preserve and reconcile the existing symlink: {destination}")
        if target.exists():
            result = run(
                ["git", "diff", "--no-index", "--quiet", "--", str(source / name), str(target)], root
            )
            if result.returncode == 0:
                continue
            if result.returncode != 1:
                raise GateError(f"Cannot compare installed files: {destination}")
        changed.append((source / name, target))
    return changed


def copy_files(changed: list[tuple[Path, Path]]) -> None:
    for source, target in changed:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)


def update(root: Path) -> str:
    with verified_source(root) as source:
        changed = changed_files(root, source)
        if not changed:
            return "Hard Eng is current"
        paths = [str(target.relative_to(root)) for _, target in changed]
        if git(root, "status", "--porcelain", "--", *paths):
            raise GateError(
                "Local Hard Eng changes conflict with automatic update; preserve and resolve them first"
            )
        copy_files(changed)
        git(root, "add", "--", *paths)
        try:
            git(root, "commit", "--only", "-m", "Update Hard Eng shared files", "--", *paths)
        except GateError:
            git(root, "restore", "--source=HEAD", "--staged", "--worktree", "--", *paths)
            raise
    return "Updated Hard Eng shared files in a separate commit"


def instructions(root: Path) -> None:
    path = root / "AGENTS.md"
    reference = "Follow [.agents/skills/he/SKILL.md](.agents/skills/he/SKILL.md) for engineering work."
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
    with verified_source(root) as source:
        changed = changed_files(root, source)
        if any(target.exists() for _, target in changed):
            raise GateError(
                "Existing Hard Eng files differ; preserve them and use update or reconcile them first"
            )
        copy_files(changed)
    instructions(root)
    git_hooks.install(root, ".agents/hard-eng/bin/hard-eng")
    print(
        "Installed shared rules, skills and gates inside this project. Commit these files with the project."
    )
    if not (root / "hard-eng.gates.json").is_file():
        print(
            "Next: ask your agent to study this project and adapt .agents/skills/he/templates into hard-eng.gates.json before implementation."
        )

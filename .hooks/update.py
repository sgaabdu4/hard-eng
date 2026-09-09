"""Install a CI-verified upstream revision with an isolated local Git commit."""

import json
import re
import subprocess
import sys
import tempfile
from operator import itemgetter
from pathlib import Path

UPSTREAM = "sgaabdu4/hard-eng"
SOURCE_FILE = ".hooks/hard-eng-source.json"


def github_json(endpoint: str) -> object:
    result = subprocess.check_output(["gh", "api", endpoint], text=True, timeout=30)
    return json.loads(result)


def verified_revision(revision: str) -> bool:
    report = github_json(f"repos/{UPSTREAM}/commits/{revision}/check-runs?per_page=100")
    if not isinstance(report, dict):
        raise TypeError("GitHub check response must be an object")
    checks: list[dict[str, object]] = [
        check
        for check in report.get("check_runs", [])
        if isinstance(check, dict)
        and check.get("name") == "hard-eng"
        and isinstance(check.get("app"), dict)
        and check.get("app", {}).get("slug") == "github-actions"
    ]
    if not checks:
        return False
    latest = max(checks, key=itemgetter("id"))
    return (
        latest.get("status") == "completed"
        and latest.get("conclusion") == "success"
        and latest.get("head_sha") == revision
    )


def latest_verified(previous: str) -> str | None:
    page = 1
    while True:
        commits = github_json(
            f"repos/{UPSTREAM}/commits?sha=main&per_page=100&page={page}"
        )
        if not isinstance(commits, list):
            raise TypeError("GitHub commits response must be a list")
        if not commits:
            return None
        for commit in commits:
            if not isinstance(commit, dict):
                raise TypeError("GitHub commit must be an object")
            revision = commit["sha"]
            if revision == previous:
                return None
            if not isinstance(revision, str) or not re.fullmatch(
                r"[0-9a-f]{40}", revision
            ):
                raise ValueError("GitHub returned an invalid commit")
            if verified_revision(revision):
                return revision
        page += 1


def fetch_sources(temporary: Path, revision: str, previous: str) -> tuple[Path, Path]:
    source, old = temporary / "source", temporary / "previous"
    subprocess.run(
        [
            "git",
            "clone",
            "--quiet",
            "--filter=blob:none",
            f"https://github.com/{UPSTREAM}.git",
            str(source),
        ],
        check=True,
        timeout=120,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", "--detach", revision],
        cwd=source,
        check=True,
        timeout=60,
    )
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", previous, revision],
        cwd=source,
        check=True,
        timeout=30,
    )
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(old), previous],
        cwd=source,
        check=True,
        timeout=60,
    )
    for tree in (source, old):
        subprocess.run(
            ["git", "submodule", "update", "--init", "--recursive"],
            cwd=tree,
            check=True,
            timeout=120,
        )
    return source, old


def scaffold_files(source: Path) -> set[str]:
    skills = list((source / ".agents/skills").iterdir())
    if any(skill.is_symlink() and not skill.is_dir() for skill in skills):
        raise ValueError(
            "Unresolved skill link; run git submodule update --init --recursive"
        )
    return {
        str(path.relative_to(source)) for path in (source / ".hooks").glob("*.py")
    } | {
        str(path.relative_to(source))
        for skill in skills
        for path in skill.rglob("*")
        if path.is_file()
    }


def update_plan(
    root: Path, source: Path, previous: Path
) -> tuple[dict[str, str | None], dict[str, str | None]]:
    output = subprocess.check_output(
        [
            sys.executable,
            str(source / "setup.py"),
            str(root),
            "--plan",
            "--previous-source",
            str(previous),
        ],
        cwd=root,
        text=True,
        timeout=60,
    )
    plan = json.loads(output)
    changes: dict[str, str | None] = {
        name: content
        for name, content in plan["files"].items()
        if not (root / name).is_file() or (root / name).read_text() != content
    }
    for name in scaffold_files(previous) - scaffold_files(source):
        target = root / name
        if target.exists():
            if (
                target.is_symlink()
                or target.read_bytes() != (previous / name).read_bytes()
            ):
                raise ValueError(
                    f"Local scaffold edit in {name}; preserve it and ask before updating"
                )
            changes[name] = None
    links: dict[str, str | None] = {
        name: target
        for name, target in plan["links"].items()
        if not (root / name).is_symlink()
    }
    removed_skills = {path.name for path in (previous / ".agents/skills").iterdir()} - {
        path.name for path in (source / ".agents/skills").iterdir()
    }
    for skill in removed_skills:
        name = ".claude/skills/" + skill
        link = root / name
        if link.is_symlink() and link.resolve() == root / ".agents/skills" / skill:
            links[name] = None
        elif link.exists() or link.is_symlink():
            raise ValueError(f"Local skill link differs: {name}")
    return changes, links


def write_changes(root: Path, changes: dict[str, str | None]) -> None:
    for name, content in changes.items():
        target = root / name
        if content is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)


def write_links(root: Path, links: dict[str, str | None]) -> None:
    for name, target in links.items():
        link = root / name
        if target is None:
            link.unlink(missing_ok=True)
        else:
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(target, target_is_directory=True)


def verify_candidate(
    root: Path,
    source: Path,
    changes: dict[str, str | None],
    links: dict[str, str | None],
    candidate: Path,
) -> None:
    subprocess.run(
        [sys.executable, str(source / ".hooks/hard-eng.py"), "check"],
        cwd=source,
        stdout=sys.stderr,
        check=True,
        timeout=3500,
    )
    subprocess.run(
        ["git", "worktree", "add", "--quiet", "--detach", str(candidate), "HEAD"],
        cwd=root,
        check=True,
    )
    try:
        write_changes(candidate, changes)
        write_links(candidate, links)
        subprocess.run(["git", "diff", "--check"], cwd=candidate, check=True)
        only_scaffold = set(changes) <= scaffold_files(source) | scaffold_files(
            root
        ) | {"AGENTS.md", SOURCE_FILE}
        command = (
            [sys.executable, "-m", "compileall", "-q", str(candidate / ".hooks")]
            if only_scaffold
            else [sys.executable, str(candidate / ".hooks/hard-eng.py"), "check"]
        )
        subprocess.run(
            command, cwd=candidate, stdout=sys.stderr, check=True, timeout=3500
        )
    finally:
        subprocess.run(
            ["git", "worktree", "remove", "--force", str(candidate)],
            cwd=root,
            check=True,
        )


def commit_update(
    root: Path,
    changes: dict[str, str | None],
    links: dict[str, str | None],
    revision: str,
) -> None:
    names = sorted({*changes, *links})
    before = {
        name: (root / name).read_bytes() if (root / name).exists() else None
        for name in changes
    }
    before_links = {
        name: str((root / name).readlink()) if (root / name).is_symlink() else None
        for name in links
    }
    try:
        write_changes(root, changes)
        write_links(root, links)
        subprocess.run(["git", "add", "--", *names], cwd=root, check=True)
        subprocess.run(
            [
                "git",
                "commit",
                "--only",
                "-m",
                f"Update Hard Eng to {revision}",
                "--",
                *names,
            ],
            cwd=root,
            stdout=sys.stderr,
            check=True,
            timeout=3500,
        )
    except (OSError, subprocess.SubprocessError):
        for name, content in before.items():
            target = root / name
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content)
        for name, target in before_links.items():
            (root / name).unlink(missing_ok=True)
            if target is not None:
                (root / name).symlink_to(target, target_is_directory=True)
        subprocess.run(
            ["git", "reset", "--quiet", "HEAD", "--", *names], cwd=root, check=True
        )
        raise


def update(root: Path) -> str:
    marker = root / SOURCE_FILE
    if not marker.exists():
        return "Automatic update unavailable: this checkout has no installed source revision."
    metadata = json.loads(marker.read_text())
    if not isinstance(metadata, dict):
        raise TypeError("Installed source metadata must be an object")
    previous = metadata.get("revision")
    if not isinstance(previous, str) or not re.fullmatch(r"[0-9a-f]{40}", previous):
        return "Installed from an uncommitted working copy; publish a verified source revision before automatic updates."
    revision = latest_verified(previous)
    if revision is None:
        return "No newer CI-verified Hard Eng revision is available."
    with tempfile.TemporaryDirectory(prefix="hard-eng-update-") as temporary:
        source, old = fetch_sources(Path(temporary), revision, previous)
        changes, links = update_plan(root, source, old)
        if not changes and not links:
            return "Hard Eng already matches the verified source."
        names = sorted({*changes, *links})
        if subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *names],
            cwd=root,
            text=True,
        ):
            raise ValueError(
                "The update overlaps local edits; preserve them and ask before updating"
            )
        before = {
            name: (root / name).read_bytes() if (root / name).exists() else None
            for name in changes
        }
        verify_candidate(root, source, changes, links, Path(temporary) / "candidate")
        if any(
            ((root / name).read_bytes() if (root / name).exists() else None) != content
            for name, content in before.items()
        ):
            raise ValueError(
                "Files changed during verification; the update was not applied"
            )
        if subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=all", "--", *names],
            cwd=root,
            text=True,
        ):
            raise ValueError(
                "The update paths changed during verification; nothing was applied"
            )
        commit_update(root, changes, links, revision)
    return f"Updated Hard Eng to {revision}; created an isolated local commit without pushing."


def check_scaffold_update(root: Path, base: str) -> bool:
    marker = root / SOURCE_FILE
    if not marker.is_file():
        return False
    # Only a committed installation update can use this exemption. Local work
    # and uncertain impact retain the normal application checks.
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True):
        return False
    try:
        revision = json.loads(marker.read_text()).get("revision")
        previous = json.loads(
            subprocess.check_output(
                ["git", "show", f"{base}:{SOURCE_FILE}"],
                cwd=root,
                text=True,
                stderr=subprocess.DEVNULL,
            )
        ).get("revision")
        names = set(
            subprocess.check_output(
                ["git", "diff", "--name-only", "--no-renames", "-z", base, "--"],
                cwd=root,
                text=True,
            ).split("\0")
        ) - {""}
    except (subprocess.CalledProcessError, ValueError, AttributeError):
        return False
    if (
        SOURCE_FILE not in names
        or revision == previous
        or not all(
            isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value)
            for value in (previous, revision)
        )
    ):
        return False
    if not isinstance(previous, str) or not isinstance(revision, str):
        return False
    if not verified_revision(revision):
        raise ValueError(
            "Scaffold update does not identify a successful upstream hard-eng check"
        )
    with tempfile.TemporaryDirectory(prefix="hard-eng-scaffold-check-") as temporary:
        source, old = fetch_sources(Path(temporary), revision, previous)
        allowed = (
            scaffold_files(source) | scaffold_files(old) | {SOURCE_FILE, "AGENTS.md"}
        )
        allowed |= {
            ".claude/skills/" + path.name
            for tree in (source, old)
            for path in (tree / ".agents/skills").iterdir()
            if path.is_dir()
        }
        if not names <= allowed or update_plan(root, source, source) != ({}, {}):
            return False
        if any(
            (root / name).exists()
            for name in scaffold_files(old) - scaffold_files(source)
        ):
            return False
        end = "<!-- hard-eng:end -->"
        if "AGENTS.md" in names and (
            subprocess.check_output(
                ["git", "show", f"{base}:AGENTS.md"], cwd=root, text=True
            ).rsplit(end, 1)[-1]
            != (root / "AGENTS.md").read_text().rsplit(end, 1)[-1]
        ):
            return False
        print(
            "Scaffold-only update: checking the upstream scaffold and installed Python hooks.",
            flush=True,
        )
        verify_candidate(root, source, {}, {}, Path(temporary) / "candidate")
    return True

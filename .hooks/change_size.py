"""Decide whether a branch change is small enough to need no plan."""

import subprocess
from pathlib import Path, PurePosixPath

from dependency_graph import owner_language
from gate_config import SOURCE_FILE, Group, changed_files, parse_config
from plans import (
    _git_output,
    _is_test,
    default_branch_point,
    is_documentation,
    is_plan_path,
    release_references,
)

NO_CHANGE = "no change"
MAX_SMALL_LINES = 20
MAX_SMALL_FILES = 3
PROTECTED_NAMES = {
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "package.json",
    "pnpm-lock.yaml",
    "package-lock.json",
    "yarn.lock",
    "pubspec.yaml",
    "pubspec.lock",
    "hard-eng.gates.json",
    "AGENTS.md",
    "AGENTS.override.md",
    "schema.prisma",
    "appwrite.json",
    "appwrite.config.json",
}
PROTECTED_DIRECTORIES = {".github", ".hooks", ".agents", ".claude", "migrations"}


def _is_protected(path: PurePosixPath) -> bool:
    return (
        path.name in PROTECTED_NAMES
        or (path.name.startswith("requirements") and path.suffix == ".txt")
        or path.name.startswith("bun.lock")
        or path.suffix == ".sql"
        or bool(PROTECTED_DIRECTORIES.intersection(path.parts[:-1]))
    )


def _file_reason(name: str, added: str, removed: str) -> str | None:
    path = PurePosixPath(name)
    if added == "-":
        return f"it changes the binary file {name}"
    if _is_protected(path):
        return f"it changes {name}, which always needs a plan"
    if _is_test(path) and int(removed):
        return f"it removes lines from the test file {name}"
    return None


def _branch_change(root: Path, point: str) -> tuple[list[str], list[str], list[str]]:
    status = _git_output(
        root, "diff", "--name-status", "--no-renames", "-z", point, "--"
    ).split("\0")
    counts = _git_output(
        root, "diff", "--numstat", "--no-renames", "-z", point, "--"
    ).split("\0")
    # The Linux sandbox binds /dev/null over missing protected paths; Git lists them but cannot add them.
    untracked = [
        name
        for name in _git_output(
            root, "ls-files", "--others", "--exclude-standard", "-z"
        ).split("\0")
        if (root / name).is_file() or (root / name).is_symlink()
    ]
    return status, counts, untracked


def _counted_lines(counts: list[str], names: set[str]) -> int | str:
    """Changed lines in the counted files, or the first reason one of them needs a plan."""
    total = 0
    for entry in filter(None, counts):
        added, removed, name = entry.split("\t", 2)
        if name not in names:
            continue
        if reason := _file_reason(name, added, removed):
            return reason
        total += int(added) + int(removed)
    return total


def configured_packages(root: Path) -> dict[str, Group]:
    try:
        config = parse_config(
            (root / "hard-eng.gates.json").read_text(), require_impact_review=False
        )
    except (OSError, ValueError, TypeError):
        return {}
    return {group["path"]: group for group in config["packages"]}


def update_written(
    root: Path,
    point: str,
    names: set[str],
    found: tuple[str, str] | None = None,
) -> set[str]:
    """Paths a verified Hard Eng update in this branch wrote, scaffold and setup edits alike."""
    from ci_setup import setup_written
    from update import (
        maybe_installed,
        proven_installed,
        shared_sources,
        update_since,
    )

    if not any(maybe_installed(name) for name in names):
        return set()
    if (found := found or update_since(root, point)) is None:
        return set()
    installed = proven_installed(root, point, names, *found)
    if not installed:
        return set()
    sources = shared_sources(*found)
    return installed | setup_written(root, point, names - installed, sources)


def update_only(root: Path, base: str, changed: set[str]) -> bool:
    """Whether a clean tree holds only files a verified Hard Eng update wrote."""
    from update import maybe_installed, update_since

    if not any(maybe_installed(name) for name in changed):
        return False
    if (found := update_since(root, base)) is None:
        return False
    if _git_output(root, "status", "--porcelain"):
        return False
    return not changed - update_written(root, base, changed, found)


def _verdict(
    status: list[str],
    counts: list[str],
    untracked: list[str],
    names: set[str],
    packages: dict[str, Group],
) -> tuple[bool, str]:
    def documentation(name: str) -> bool:
        return is_documentation(Path(name), owner_language(packages, name))

    if all(documentation(name) for name in names):
        return True, "documentation only"

    names = {
        name
        for name in names
        if name != "hard-eng.debt.json"
        and (not documentation(name) or _is_protected(PurePosixPath(name)))
    }
    added = sorted(
        {
            name
            for kind, name in zip(status[0::2], status[1::2], strict=False)
            if kind[:1] in {"A", "D", "T"} and name in names
        }
        | names.intersection(untracked)
    )
    if SOURCE_FILE in added:
        return False, "this branch installs Hard Eng"
    if added:
        return False, f"it adds, deletes or renames the file {added[0]}"
    counted = _counted_lines(counts, names)
    if isinstance(counted, str):
        return False, counted
    total = counted
    if len(names) > MAX_SMALL_FILES:
        return False, f"it changes {len(names)} files, more than {MAX_SMALL_FILES}"
    if total > MAX_SMALL_LINES:
        return False, f"it changes {total} lines, more than {MAX_SMALL_LINES}"
    plural = "file" if len(names) == 1 else "files"
    return True, f"{len(names)} {plural}, {total} changed lines"


def merge_point(root: Path) -> str | None:
    """While a merge is in progress: the merge base of the release reference with both merge parents."""
    folder = root / ".git"
    try:
        if folder.is_file():
            folder = root / folder.read_text().split("gitdir:", 1)[1].strip()
        merging = (folder / "MERGE_HEAD").is_file()
    except (OSError, IndexError):
        return None
    for reference in release_references(root) if merging else ():
        try:
            return _git_output(
                root, "merge-base", reference, "HEAD", "MERGE_HEAD"
            ).strip()
        except (subprocess.CalledProcessError, OSError):
            continue
    return None


def size_verdict(root: Path) -> tuple[bool, str]:
    """Whether the whole branch change, not just this session's, is small, and the first reason."""
    point = merge_point(root) or default_branch_point(root)
    if point is None:
        return False, "the branch point with the default branch cannot be found"
    try:
        status, counts, untracked = _branch_change(root, point)
    except (subprocess.CalledProcessError, OSError):
        return False, "the change cannot be measured"
    names = {name for name in status[1::2] + untracked if name}
    if not names:
        return True, NO_CHANGE
    names -= update_written(root, point, names)
    if not names:
        return True, "only files the verified Hard Eng update wrote"
    return _verdict(status, counts, untracked, names, configured_packages(root))


def judged_point(root: Path) -> str | None:
    """The branch point that a check with no base judges from, once Hard Eng is on it; a first install keeps its own check."""
    point = default_branch_point(root)
    if point is None:
        return None
    try:
        _git_output(root, "cat-file", "-e", f"{point}:.hooks/hard-eng.py")
    except (subprocess.CalledProcessError, OSError):
        return None
    return point


def _revision(root: Path, reference: str) -> str | None:
    try:
        return _git_output(
            root, "rev-parse", "--verify", "-q", f"{reference}^{{commit}}"
        )
    except (subprocess.CalledProcessError, OSError):
        return None


def released_plans(root: Path, base: str | None) -> set[str]:
    """Plans changed since the release base, so a feature check sees what the release checks."""
    references = release_references(root)
    revisions = {name: _revision(root, name) for name in references}
    tips = set(revisions.values())
    remote = {tip for name, tip in revisions.items() if name.startswith("origin/")}
    if base is None and remote - {None}:
        # A caller's base names what is released; without one, origin does.
        tips = remote
    point = default_branch_point(root)
    if point is None or _revision(root, base or "HEAD") in tips:
        return set()
    return {
        name for name in changed_files(root, point) or () if is_plan_path(Path(name))
    }


def moved_plans(root: Path, base: str | None, changed: set[str]) -> set[str]:
    """Changed plan paths that only moved a plan the base holds."""
    gone = [
        name
        for name in changed
        if is_plan_path(Path(name)) and not (root / name).exists()
    ]
    if not gone:
        return set()
    references = [
        reference for reference in (base, default_branch_point(root)) if reference
    ]
    held: dict[str, str] = {}
    for name in gone:
        for reference in references:
            try:
                held[_git_output(root, "show", f"{reference}:{name}")] = name
                break
            except (subprocess.CalledProcessError, OSError):
                continue
    moved = {
        name
        for name in changed
        if held
        and is_plan_path(Path(name))
        and (root / name).is_file()
        and (root / name).read_text() in held
    }
    return moved


def plan_not_needed(root: Path) -> bool:
    small, reason = size_verdict(root)
    if reason == NO_CHANGE:
        return True
    if small:
        print(f"Size: small ({reason}); no plan needed.")
    else:
        print(f"Size: big, because {reason}; a plan is needed.")
    return small

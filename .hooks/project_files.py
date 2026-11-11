"""Read a project file that a person edits; a syntax error names the file."""

import json
import subprocess
import sys
from collections.abc import Callable, Container, Iterable
from pathlib import Path

LOCK_NAMES = ("uv.lock", "poetry.lock", "bun.lock", "pubspec.lock", "Package.resolved")
KINDS = {".toml": "TOML", ".yaml": "YAML", ".yml": "YAML"}


def syntax_errors() -> tuple[type[Exception], ...]:
    """PyYAML's error is no ValueError, and PyYAML is loaded only when a caller parses YAML."""
    yaml = sys.modules.get("yaml")
    return (ValueError, yaml.YAMLError) if yaml else (ValueError,)


def syntax_error(name: str, error: Exception) -> ValueError:
    mark = getattr(error, "problem_mark", None)
    where = f": line {mark.line + 1} column {mark.column + 1}" if mark else ""
    reason = getattr(error, "problem", None) or (str(error).splitlines() or [""])[0]
    kind = KINDS.get(Path(name).suffix, "JSON")
    return ValueError(f"{name} is not valid {kind}: {reason}{where}")


def parse_project_text[T](
    text: str, name: str, parse: Callable[[str], T] = json.loads
) -> T:
    try:
        return parse(text)
    except syntax_errors() as error:
        raise syntax_error(name, error) from error


def repository_name(path: Path, root: Path | None) -> str:
    if root is None:
        root = next(
            (
                parent
                for parent in path.parents
                if (parent / "hard-eng.gates.json").exists()
                or (parent / ".git").exists()
            ),
            path.parent,
        )
    return path.relative_to(root).as_posix()


def read_project_file[T](
    path: Path, root: Path | None = None, parse: Callable[[str], T] = json.loads
) -> T:
    try:
        return parse(path.read_text())
    except syntax_errors() as error:
        raise syntax_error(repository_name(path, root), error) from error


def refuse_ignored_locks(
    root: Path,
    directories: Iterable[Path],
    listed: Container[str],
    *,
    ask_git: bool,
    names: Iterable[str] = LOCK_NAMES,
) -> None:
    """A lock file that Git ignores is missing from a fresh clone; ask Git when the file is not on disk yet."""
    for lockfile in (directory / name for directory in directories for name in names):
        relative = lockfile.relative_to(root)
        if lockfile.is_file():
            ignored = str(relative) not in listed
        else:
            ignored = (
                ask_git
                and not subprocess.run(
                    ["git", "check-ignore", "-q", str(relative)], cwd=root, check=False
                ).returncode
            )
        if ignored:
            raise ValueError(
                f"{relative} is ignored by Git, so the install fails in a fresh clone. "
                f"`git check-ignore -v {relative}` names the rule, often in .gitignore; "
                f"remove that rule, then commit {relative}"
            )

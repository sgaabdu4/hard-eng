"""Read a project file that a person edits; a syntax error names the file."""

import json
import subprocess
import sys
from collections.abc import Callable, Container, Generator, Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import cast

LOCK_NAMES = ("uv.lock", "poetry.lock", "bun.lock", "pubspec.lock", "Package.resolved")
KINDS = {".toml": "TOML", ".yaml": "YAML", ".yml": "YAML"}
KEPT: dict[str, dict[tuple[str, ...], object]] = {}


@contextmanager
def keeping(*scopes: str) -> Generator[None]:
    """Keep what keep() answers in each named scope until the block ends, also on an error."""
    opened = [name for name in scopes if name not in KEPT]
    for name in opened:
        KEPT[name] = {}
    try:
        yield
    finally:
        for name in opened:
            KEPT.pop(name, None)


def stop_keeping(scope: str) -> None:
    """End a scope before its block ends."""
    KEPT.pop(scope, None)


def keep[T](scope: str, key: tuple[str, ...], make: Callable[[], T]) -> T:
    """The answer of make() for this key, asked one time while the scope is open; asked each time when it is not."""
    store = KEPT.get(scope)
    if store is None:
        return make()
    if key not in store:
        store[key] = make()
    return cast(T, store[key])


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


def expanded(value: object) -> bool:
    if isinstance(value, dict):
        return bool(value)
    return isinstance(value, list) and any(expanded(item) for item in value)


def json_text(
    value: object, layout: tuple[str, int, int], indent: str = "", used: int = 0
) -> str:
    unit, tab, width = layout
    if isinstance(value, list) and not expanded(value):
        flat = json.dumps(value, separators=(", ", ": "))
        if used + len(flat) <= width:
            return flat
    if not isinstance(value, (dict, list)) or not value:
        return json.dumps(value)
    inner = indent + unit
    entries = (
        [(f"{json.dumps(key)}: ", item) for key, item in value.items()]
        if isinstance(value, dict)
        else [("", item) for item in value]
    )
    last = len(entries) - 1
    body = ",\n".join(
        inner
        + head
        + json_text(
            item,
            layout,
            inner,
            len((inner + head).expandtabs(tab)) + (index < last),
        )
        for index, (head, item) in enumerate(entries)
    )
    opening, closing = "{}" if isinstance(value, dict) else "[]"
    return f"{opening}\n{body}\n{indent}{closing}"

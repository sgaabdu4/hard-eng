"""Read a project file that a person edits; a syntax error names the file."""

import json
import sys
from collections.abc import Callable
from pathlib import Path

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

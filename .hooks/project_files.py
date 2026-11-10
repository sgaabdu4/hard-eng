"""Read a project file that a person edits; a syntax error names the file."""

import json
from pathlib import Path
from typing import Any


def parse_text(text: str, kind: str) -> Any:
    if kind == "yaml":
        import yaml

        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            where = f": line {mark.line + 1} column {mark.column + 1}" if mark else ""
            reason = getattr(error, "problem", None) or str(error)
            raise ValueError(reason + where) from error
    if kind == "toml":
        import tomllib

        return tomllib.loads(text)
    return json.loads(text)


def syntax_error(name: str, kind: str, error: ValueError) -> ValueError:
    reason = (str(error).splitlines() or [""])[0]
    return ValueError(f"{name} is not valid {kind.upper()}: {reason}")


def parse_project_text(text: str, name: str, kind: str = "json") -> Any:
    try:
        return parse_text(text, kind)
    except ValueError as error:
        raise syntax_error(name, kind, error) from error


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


def read_project_file(path: Path, root: Path | None = None, kind: str = "json") -> Any:
    try:
        return parse_text(path.read_text(), kind)
    except ValueError as error:
        raise syntax_error(repository_name(path, root), kind, error) from error

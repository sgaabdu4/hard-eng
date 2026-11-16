"""Refuse ruff settings, extended settings files and gate flags that ignore lint rules."""

import re
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from command_words import segments
from project_files import GIT_LISTING

SETTINGS_FILES = {"pyproject.toml", "ruff.toml", ".ruff.toml"}
IGNORE_KEYS = ("ignore", "extend-ignore", "per-file-ignores", "extend-per-file-ignores")
IGNORE_FLAGS = {f"--{key}" for key in IGNORE_KEYS}
HIDING_FLAGS = {"--exit-zero", "--isolated"}
EXCLUDE_FLAGS = {"--exclude", "--extend-exclude"}
RUFF_SKIPS = frozenset(
    {
        ".bzr",
        ".direnv",
        ".eggs",
        ".git",
        ".git-rewrite",
        ".hg",
        ".ipynb_checkpoints",
        ".mypy_cache",
        ".nox",
        ".pants.d",
        ".pyenv",
        ".pytest_cache",
        ".pytype",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        ".vscode",
        "__pypackages__",
        "_build",
        "buck-out",
        "dist",
        "node_modules",
        "site-packages",
        "venv",
    }
)
HEADER = re.compile(r"\s*\[+\s*([^\]]+?)\s*\]+")
OUTSIDE = "extends a file outside the repository"


def ruff_tables(name: str, text: str) -> tuple[dict[str, object], str] | None:
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    if PurePosixPath(name).name != "pyproject.toml":
        return config, ""
    tool = config.get("tool")
    ruff = tool.get("ruff") if isinstance(tool, dict) else None
    return (ruff, "tool.ruff") if isinstance(ruff, dict) else None


def relative_table(table: str, prefix: str) -> str | None:
    """The table path below the ruff settings root, or None outside it."""
    if not prefix:
        return table
    if table == prefix:
        return ""
    return table.removeprefix(prefix + ".") if table.startswith(prefix + ".") else None


def present_keys(config: dict[str, object], keys: tuple[str, ...]) -> set[str]:
    lint = config.get("lint")
    return {
        key for key in keys if key in config or (isinstance(lint, dict) and key in lint)
    }


def key_lines(text: str, prefix: str, present: set[str]) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    table = ""
    for number, line in enumerate(text.splitlines(), 1):
        header = HEADER.match(line)
        if header:
            table = header[1].strip()
        below = relative_table(table, prefix)
        if below is None:
            continue
        key = below if header else line.split("=", 1)[0].strip().strip('"')
        if below in ("", "lint") and not header and "=" in line:
            key = key.removeprefix("lint.")
        elif not header or below.removeprefix("lint.") not in present:
            continue
        key = key.removeprefix("lint.")
        if key in present:
            hits.append((number, key))
    return hits


def file_hits(root: Path, name: str, text: str, seen: frozenset[Path]) -> list[str]:
    """Ignore keys of one settings file, then of each file its `extend` chain reaches."""
    found = ruff_tables(name, text)
    if found is None:
        return []
    config, prefix = found
    present = present_keys(config, IGNORE_KEYS)
    lines = key_lines(text, prefix, present)
    hits = [f"{name}:{n} sets the ruff setting {key}" for n, key in lines]
    hits = hits or [f"{name}:1 sets the ruff setting {key}" for key in sorted(present)]
    extend = config.get("extend")
    if isinstance(extend, str):
        hits += extended_hits(root, name, extend, seen)
    return hits


def extended_hits(
    root: Path, name: str, extend: str, seen: frozenset[Path]
) -> list[str]:
    target = ((root / name).parent / extend).resolve()
    if not target.is_relative_to(root.resolve()):
        return [f"{name}:1 {OUTSIDE}"]
    if target in seen or not target.is_file():
        return []
    relative = target.relative_to(root.resolve()).as_posix()
    return file_hits(
        root, relative, target.read_text(errors="replace"), seen | {target}
    )


def settings_switch_offs(root: Path, name: str, text: str) -> list[str]:
    return file_hits(root, name, text, frozenset({(root / name).resolve()}))


def ruff_invocations(
    command: list[str], directory: Path
) -> list[tuple[list[str], list[str]]]:
    """Each ruff run of a command as its launcher words and its arguments, one for each chained command."""
    return [
        (segment[: len(segment) - len(found)], found)
        for segment in segments(command, directory)
        if (found := ruff_command(segment))
    ]


def ruff_commands(command: list[str], directory: Path) -> list[list[str]]:
    return [arguments for _, arguments in ruff_invocations(command, directory)]


def ruff_command(command: list[str]) -> list[str]:
    """The arguments after a ruff executable, or none when the command runs another tool."""
    for index, argument in enumerate(command):
        if argument.rsplit("/", 1)[-1].split("@", 1)[0] == "ruff":
            return command[index + 1 :]
    return []


def config_ignores(directory: Path, value: str) -> bool:
    """A `--config` value is a file or TOML text; it ignores rules when what it holds does."""
    path = directory / value
    if path.is_file():
        return bool(
            settings_switch_offs(directory, value, path.read_text(errors="replace"))
        )
    try:
        config = tomllib.loads(value)
    except tomllib.TOMLDecodeError:
        return False
    return bool(present_keys(config, IGNORE_KEYS))


def config_selects(directory: Path, value: str) -> bool:
    """A `--config` value that sets `select` without ALL replaces the project's rules."""
    path = directory / value
    try:
        config = tomllib.loads(path.read_text() if path.is_file() else value)
    except (tomllib.TOMLDecodeError, OSError):
        return False
    lint = config.get("lint")
    chosen = [
        config.get("select"),
        lint.get("select") if isinstance(lint, dict) else None,
    ]
    return any(isinstance(item, list) and "ALL" not in item for item in chosen)


def narrowing_selects(arguments: list[str]) -> list[str]:
    """Each `--select` that does not name ALL, since it replaces the project's rule set."""
    found = []
    for index, argument in enumerate(arguments):
        flag, equals, value = argument.partition("=")
        if flag == "--select":
            chosen = value if equals else "".join(arguments[index + 1 : index + 2])
            if "ALL" not in chosen.split(","):
                found.append(argument)
    return found


def config_values(arguments: list[str]) -> list[str]:
    values = []
    for index, argument in enumerate(arguments):
        flag, equals, value = argument.partition("=")
        if flag == "--config":
            values.append(
                value if equals else "".join(arguments[index + 1 : index + 2])
            )
    return values


def offending_flags(arguments: list[str], directory: Path, role: object) -> list[str]:
    found = [
        argument
        for argument in arguments
        if argument.partition("=")[0] in IGNORE_FLAGS | HIDING_FLAGS
    ]
    found += [
        f"--config {value}"
        for value in config_values(arguments)
        if config_ignores(directory, value)
    ]
    if arguments[:1] == ["check"]:
        found += [a for a in arguments if a.partition("=")[0] in EXCLUDE_FLAGS]
    if role == "lint":
        found += narrowing_selects(arguments)
        found += [
            f"--config {value}"
            for value in config_values(arguments)
            if config_selects(directory, value)
        ]
    return found


def uncovered(arguments: list[str], directory: Path) -> list[str]:
    """Tracked Python files outside the folders that start with a dot that the paths of a ruff check leave out."""
    paths = [
        (directory / word).resolve()
        for word in arguments[1:]
        if not word.startswith("-") and (directory / word).exists()
    ]
    if not paths or directory.resolve() in paths:
        return []
    listed = subprocess.run(
        [
            *GIT_LISTING,
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "*.py",
            "*.pyi",
        ],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.split("\0")
    return [
        name
        for name in listed
        if name
        and not RUFF_SKIPS & set(PurePosixPath(name).parts)
        and not any(part.startswith(".") for part in PurePosixPath(name).parts)
        and not any((directory / name).resolve().is_relative_to(path) for path in paths)
    ]


def validate_ruff_command(command: list[str], directory: Path, role: object) -> None:
    found: list[str] = []
    for arguments in ruff_commands(command, directory):
        found += offending_flags(arguments, directory, role)
        if role == "lint" and arguments[:1] == ["check"]:
            found += [
                f"no path covers {name}" for name in uncovered(arguments, directory)
            ]
    if found:
        raise ValueError(
            "HE-NO-SWITCH-OFF: A ruff gate must not ignore or narrow rules: fix each finding at its cause "
            f"instead; the gate holds {', '.join(found)}"
        )

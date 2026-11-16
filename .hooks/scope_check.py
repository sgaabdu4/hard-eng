"""Ask a tool which files it checks and compare that with the files git tracks."""

import re
import subprocess
import tomllib
from pathlib import Path, PurePosixPath

from gate_config import generated_sources
from project_files import GIT_LISTING

SOURCE_FOLDERS = frozenset(
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
MARKER = ".hooks/hard-eng-source.json"


def glob_regex(pattern: str) -> re.Pattern[str]:
    """A glob as Fallow reads it; `*` is taken to cross folders, so a pattern never drops fewer files than it names."""
    pattern = pattern + "**" if pattern.endswith("/") else pattern
    out = "" if "/" in pattern else "(?:.*/)?"
    index = 0
    while index < len(pattern):
        if pattern.startswith("**/", index):
            out += "(?:.*/)?"
            index += 3
        elif pattern[index] == "*":
            out += ".*"
            index += 2 if pattern.startswith("**", index) else 1
        elif pattern[index] == "?":
            out += "[^/]"
            index += 1
        else:
            out += re.escape(pattern[index])
            index += 1
    return re.compile(out)


def tracked(directory: Path, suffixes: tuple[str, ...]) -> list[str]:
    """Tracked and new files below a folder, relative to it, with one of the suffixes."""
    listed = subprocess.run(
        [*GIT_LISTING, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return [
        name
        for name in listed.split("\0")
        if name.endswith(suffixes) and (directory / name).is_file()
    ]


def installed_files(directory: Path) -> set[str]:
    """The files Hard Eng writes into a project, which the project does not check; Hard Eng's own source has no such files."""
    if not (directory / MARKER).is_file():
        return set()
    from update import scaffold_files

    names = {
        path.relative_to(directory).as_posix()
        for path in (directory / ".hooks").rglob("*")
        if path.is_file()
    }
    if (directory / ".agents/skills").is_dir():
        names |= scaffold_files(directory)
    return names


def left_out(
    directory: Path,
    suffixes: tuple[str, ...],
    checked: set[str],
    children: frozenset[str],
    skipped: frozenset[str] = SOURCE_FOLDERS,
) -> list[str]:
    """Tracked files that the tool does not check, less the installed files, the linguist-generated files, the files of a child group and the tool's own default folders."""
    names = [
        name
        for name in tracked(directory, suffixes)
        if name not in checked and not skipped & set(PurePosixPath(name).parts)
    ]
    if not names:
        return []
    own = installed_files(directory) | generated_sources(
        directory, names, generated_only=True
    )
    nested = [glob_regex(child) for child in children]
    return [
        name
        for name in names
        if name not in own and not any(child.fullmatch(name) for child in nested)
    ]


def refusal(left: list[str]) -> list[str]:
    if not left:
        return []
    more = f" and {len(left) - 1} more" if len(left) > 1 else ""
    return [
        f"the tool does not check {left[0]}{more}, which git tracks; every tracked source file must be checked, or be linguist-generated or belong to a child gate group"
    ]


RUFF_CONFIGS = {"ruff.toml", ".ruff.toml", "pyproject.toml"}
FALLOW_CONFIGS = {".fallowrc.json", ".fallowrc.jsonc", "fallow.toml", ".fallow.toml"}
FREE_RUFF_KEYS = {"target-version"}


def only_free_keys(name: str, directory: Path) -> bool:
    """A ruff config that sets nothing but keys that cannot change what is reported."""
    try:
        config = tomllib.loads((directory / name).read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    if PurePosixPath(name).name == "pyproject.toml":
        tool = config.get("tool")
        config = tool.get("ruff") if isinstance(tool, dict) else None
        if config is None:
            return True
    return isinstance(config, dict) and set(config) <= FREE_RUFF_KEYS


def nested_configs(directory: Path, tool: str, roots: frozenset[Path]) -> list[str]:
    """A tool config below a gate root that is not a gate root itself: the tool would read it for some files and the gate would not judge it."""
    wanted = RUFF_CONFIGS if tool == "ruff" else FALLOW_CONFIGS
    own = installed_files(directory)
    found = []
    for name in tracked(directory, tuple(wanted)):
        path = PurePosixPath(name)
        if path.name not in wanted or not path.parent.parts or name in own:
            continue
        if (directory / path.parent).resolve() in roots:
            continue
        if tool == "ruff" and only_free_keys(name, directory):
            continue
        found.append(name)
    return [
        f"{name} configures {tool} below the gate root {directory.name or '.'}; give it its own gate group"
        for name in found
    ]

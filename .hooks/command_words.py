"""The words a gate command really runs: a package script or an `sh -c` string is expanded, and chained commands are split."""

import shlex
from pathlib import Path, PurePosixPath

ASSIGNING_SUFFIXES = (".yml", ".yaml", ".sh", ".bash", ".toml", ".json", ".mk")
ASSIGNING_NAMES = {
    "Makefile",
    "makefile",
    "GNUmakefile",
    "Dockerfile",
    "justfile",
    ".envrc",
    ".env",
}


def assigns_variables(name: str) -> bool:
    """A workflow, script or config file; prose and notes can name a variable without setting it."""
    return (
        name.endswith(ASSIGNING_SUFFIXES) or PurePosixPath(name).name in ASSIGNING_NAMES
    )


SEPARATORS = {"&&", "||", ";", "|"}
SHELLS = {"sh", "bash", "zsh"}


def unwrapped(command: list[str], directory: Path) -> list[str]:
    """Expand a package script or an `sh -c` string, as `check:fallow` is expanded."""
    arguments = list(command)
    if Path(arguments[0]).name in {"npm", "pnpm", "yarn", "bun"}:
        from project_setup import package_script_invocation

        try:
            arguments = package_script_invocation(arguments, directory)[0]
        except (ValueError, TypeError, OSError):
            return arguments
    if Path(arguments[0]).name in SHELLS and "-c" in arguments[1:-1]:
        return shlex.split(arguments[arguments.index("-c") + 1])
    return arguments


def segments(command: list[str], directory: Path) -> list[list[str]]:
    """One word list for each chained command."""
    found: list[list[str]] = [[]]
    for word in unwrapped(command, directory):
        if word in SEPARATORS:
            found.append([])
        else:
            found[-1].append(word)
    return [segment for segment in found if segment]

"""The words a gate command really runs: a package script or an `sh -c` string is expanded, and chained commands are split."""

import re
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
SHELL_FLAGS = re.compile(r"-[A-Za-z]*c[A-Za-z]*")
HIDDEN_COMMAND = ("$(", "`", "<(", ">(")
UNREDUCIBLE = (
    "HE-NO-SWITCH-OFF: A gate command must reduce to words that the checks can read: "
    "write the tool and its arguments as plain words, without eval, a variable as the command "
    "or a command substitution; the gate holds "
)


JUDGED_TOOLS = ("ruff", "cargo", "clippy", "fallow", "gitleaks")


def hidden(words: list[str]) -> list[str]:
    """Words that run something the checks cannot read: eval or a variable as the command, and a substitution beside a judged tool."""
    judged = any(tool in word for word in words for tool in JUDGED_TOOLS)
    found = [
        word
        for word in words
        if judged and any(mark in word for mark in HIDDEN_COMMAND)
    ]
    starts = [words[:1]] + [
        words[index + 1 : index + 2]
        for index, word in enumerate(words)
        if word in SEPARATORS
    ]
    for number, start in enumerate(starts):
        if not start:
            continue
        named_eval = Path(start[0]).name == "eval"
        if named_eval or (start[0].startswith("$") and (number == 0 or judged)):
            found.append(start[0])
    return found


def shell_string(arguments: list[str]) -> str | None:
    """The string after the first flag group that holds `c`, as in `-c`, `-ec` or `-lc`."""
    for index, word in enumerate(arguments[1:-1], 1):
        if SHELL_FLAGS.fullmatch(word):
            return arguments[index + 1]
    return None


def unwrapped(command: list[str], directory: Path) -> list[str]:
    """Expand a package script or a shell string, as `check:fallow` is expanded; a command that cannot be read fails."""
    arguments = list(command)
    for _ in range(4):
        if Path(arguments[0]).name in {"npm", "pnpm", "yarn", "bun"}:
            from project_setup import package_script_invocation

            try:
                arguments = package_script_invocation(arguments, directory)[0]
            except (ValueError, TypeError, OSError):
                return arguments
        string = shell_string(arguments) if Path(arguments[0]).name in SHELLS else None
        if string is None:
            break
        try:
            arguments = shlex.split(string)
        except ValueError as error:
            raise ValueError(UNREDUCIBLE + repr(string)) from error
        if not arguments:
            break
    if found := hidden(arguments):
        raise ValueError(UNREDUCIBLE + ", ".join(found))
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

"""A gate that runs a judged tool runs it directly: a launcher, the tool, then arguments; every other form is refused."""

import re
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


JUDGED_TOOLS = {"ruff", "fallow", "gitleaks", "clippy", "cargo-clippy"}
OPERATORS = {"&&", "||", ";", "|", "&", "!", ">", ">>", "<", "2>", "(", ")"}
MANAGERS = {"npm", "pnpm", "yarn", "bun"}
TOOL_WORD = re.compile(r"(ruff|fallow|gitleaks)(@[\w.=<>~+-]+)?")
UV_FLAGS = {"--no-sync", "--frozen", "--locked"}
DIRECT_FORMS = (
    "write `uvx ruff@<pin> check <paths>`, `ruff check <paths>`, `bun x fallow@<pin> <arguments>`, "
    "`cargo clippy <arguments>` or `gitleaks <arguments>`, or `bun run <script>` where the script is exactly one such command"
)


def refusal(reason: str) -> ValueError:
    return ValueError(
        "HE-NO-SWITCH-OFF: A gate that runs ruff, cargo, clippy, fallow or gitleaks must run it directly, "
        f"so the checks can read its arguments: {DIRECT_FORMS}; {reason}"
    )


def tool_name(word: str) -> str:
    return PurePosixPath(word).name.split("@", 1)[0]


def mentions(words: list[str]) -> bool:
    """A word that is a judged tool, or a string that holds one, as in `sh -c 'ruff check'`; `cargo` alone is not judged, only its `clippy`."""
    for word in words:
        if tool_name(word) in JUDGED_TOOLS:
            return True
        if re.search(r"[\s;&|$`]", word) and any(
            tool_name(part) in JUDGED_TOOLS for part in re.findall(r"[\w@./+-]+", word)
        ):
            return True
    return False


def expanded(command: list[str], directory: Path) -> list[str]:
    """A package script run as its words; a script with a `pre` or `post` script runs two commands, so it is refused."""
    if tool_name(command[0]) not in MANAGERS:
        return command
    from project_setup import package_script_invocation, read_project_file

    try:
        words, where = package_script_invocation(command, directory)
    except (ValueError, TypeError, OSError):
        return command
    if words == command:
        return command
    named = [word for word in command[1:] if not word.startswith("-")]
    scripts = read_project_file(where / "package.json").get("scripts", {})
    if mentions(words) and (
        {f"pre{named[1]}", f"post{named[1]}"} & set(scripts)
        if len(named) > 1
        else False
    ):
        raise refusal(
            f"the script {named[1]} has a pre or post script, so two commands run"
        )
    return words


def launched(words: list[str]) -> list[str] | None:
    """The words from the tool on, when a template launcher starts them."""
    if not words:
        return None
    if words[0] in {"ruff", "fallow", "gitleaks"}:
        return words
    if words[0] == "cargo":
        return words if "clippy" in words[:3] else None
    rest: list[str] | None = None
    if words[0] == "uvx":
        rest = words[1:]
    elif words[:2] == ["bun", "x"]:
        rest = words[2:]
    elif words[0] == "bunx":
        rest = words[1:]
    elif words[:2] == ["uv", "run"]:
        rest = words[2:]
        while rest and rest[0] in UV_FLAGS:
            rest = rest[1:]
    if rest and (found := TOOL_WORD.fullmatch(rest[0])):
        return [found[1], *rest[1:]]
    return None


def direct(command: list[str], directory: Path) -> list[str] | None:
    """The words from the judged tool on, or none when no judged tool runs; any other form of a judged tool is refused."""
    words = expanded(command, directory)
    if not mentions(words) and not mentions(command):
        return None
    found = launched(words)
    if found is None:
        raise refusal(f"the gate holds {' '.join(command)}")
    shell = len(words) != len(command)
    metas = re.compile(r"[;&|<>$`]")
    bad = [
        word
        for word in found
        if word in OPERATORS
        or "$(" in word
        or "`" in word
        or (shell and metas.search(word))
    ]
    if bad:
        raise refusal(f"the gate holds {', '.join(bad)}")
    return found

"""Refuse ruff settings and gate flags that ignore lint rules."""

import re
import tomllib

SETTINGS_FILES = {"pyproject.toml", "ruff.toml", ".ruff.toml"}
IGNORE_KEYS = ("ignore", "extend-ignore", "per-file-ignores", "extend-per-file-ignores")
IGNORE_FLAGS = {f"--{key}" for key in IGNORE_KEYS}
IGNORE_CONFIG = re.compile(
    r"\s*(?:lint\.)?(?:extend-)?(?:ignore|per-file-ignores)(?![\w-])"
)
HEADER = re.compile(r"\s*\[+\s*([^\]]+?)\s*\]+")


def ruff_tables(name: str, text: str) -> tuple[dict[str, object], str] | None:
    try:
        config = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return None
    if name != "pyproject.toml":
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


def settings_switch_offs(name: str, text: str) -> list[str]:
    """One hit for each ignore key of a ruff settings file, at the top level and under lint."""
    found = ruff_tables(name, text)
    if found is None:
        return []
    config, prefix = found
    lint = config.get("lint")
    present = {
        key
        for key in IGNORE_KEYS
        if key in config or (isinstance(lint, dict) and key in lint)
    }
    hits: list[str] = []
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
        elif not header or below.removeprefix("lint.") not in IGNORE_KEYS:
            continue
        key = key.removeprefix("lint.")
        if key in present:
            hits.append(f"{name}:{number} sets the ruff setting {key}")
    return hits or [f"{name}:1 sets the ruff setting {key}" for key in sorted(present)]


def ruff_command(command: list[str]) -> list[str]:
    """The arguments after a ruff executable, or none when the command runs another tool."""
    for index, argument in enumerate(command):
        if argument.rsplit("/", 1)[-1].split("@", 1)[0] == "ruff":
            return command[index + 1 :]
    return []


def ignoring_flags(command: list[str]) -> list[str]:
    arguments = ruff_command(command)
    found = []
    for index, argument in enumerate(arguments):
        flag, equals, value = argument.partition("=")
        if flag in IGNORE_FLAGS:
            found.append(argument)
        elif flag == "--config":
            text = value if equals else "".join(arguments[index + 1 : index + 2])
            if IGNORE_CONFIG.match(text.split("=", 1)[0] + "="):
                found.append(f"--config {text}")
    return found


def validate_ruff_command(command: list[str]) -> None:
    if found := ignoring_flags(command):
        raise ValueError(
            "HE-NO-SWITCH-OFF: A ruff gate must not ignore rules: fix each finding at its cause "
            f"instead; the gate holds {', '.join(found)}"
        )

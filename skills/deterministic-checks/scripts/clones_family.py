#!/usr/bin/env python3
"""Clones family contract: jscpd stays read-only, baselined, and fails only on new clone pairs."""

from __future__ import annotations

from pathlib import Path

CLONE_WRITE_FLAGS = ("--update-baseline", "--output", "-o")
CLONE_CONSOLE_REPORTERS = frozenset({"console", "console-full"})


def validate_clones(repo: Path, family: str, command: list[str]) -> None:
    if family != "clones":
        return
    names = {argument.split("=", 1)[0] for argument in command}
    if names & set(CLONE_WRITE_FLAGS):
        raise ClonesFamilyError("clones must be read-only: --update-baseline and file reporters are forbidden")
    if "--fail-on-new-clones" not in names:
        raise ClonesFamilyError("clones requires --fail-on-new-clones")
    reporters = _option_value(command, "--reporters") or _option_value(command, "-r")
    if reporters not in CLONE_CONSOLE_REPORTERS:
        raise ClonesFamilyError("clones requires --reporters console so new pairs print and no report file is written")
    baseline = _option_value(command, "--baseline")
    if baseline is None and "--baseline-from-ref" not in names:
        raise ClonesFamilyError("clones requires --baseline <file> or --baseline-from-ref <ref>")
    if baseline is not None and not (repo / baseline).is_file():
        raise ClonesFamilyError(f"clones baseline file is missing: {baseline}")


class ClonesFamilyError(ValueError):
    """The clones family command breaks the read-only baseline contract."""


def _option_value(command: list[str], option: str) -> str | None:
    for index, argument in enumerate(command):
        if argument == option and index + 1 < len(command):
            return command[index + 1]
        if argument.startswith(option + "="):
            return argument.split("=", 1)[1]
    return None

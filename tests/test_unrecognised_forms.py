"""Anything the judge does not recognise is refused: each row is an input a review found passing."""

from pathlib import Path

import pytest
from gate_config import Gate, Group, validate_gate

LINT = ["uvx", "ruff@latest", "check", "."]
DEAD = ["fallow", "--only", "dead-code,dupes,health", "--fail-on-issues"]
LINT_ROLE = "lint"


def gate(command: list[str], role: str = "lint") -> Gate:
    return {"name": role, "role": role, "command": command}


def lint_groups(*paths: tuple[str, list[str]]) -> list[Group]:
    return [
        {"path": path, "language": "python", "checks": [gate(command)]}
        for path, command in paths
    ]


def fallow_groups() -> list[Group]:
    return [
        {
            "path": ".",
            "language": "javascript",
            "checks": [gate(DEAD, "dead-code-duplicates")],
        }
    ]


WRAPPED = [
    ["bash", "-ec", "ruff check . --exit-zero"],
    ["sh", "-ec", "ruff check . --extend-ignore F401"],
    ["bash", "-lc", "ruff check . --select E501"],
    ["bash", "-ec", "cargo clippy -- -A warnings"],
    ["bash", "-c", "eval 'ruff check . --exit-zero'"],
    ["sh", "-c", "$LINT --exit-zero"],
    ["sh", "-c", "ruff check $(echo . --exit-zero)"],
    ["eval", "ruff check . --exit-zero"],
    ["ruff", "check", ".", "--statistics"],
    ["ruff", "check", ".", "--stdin-filename", "x.py"],
    ["ruff", "check", ".", "--unknown-flag"],
    ["ruff", "check", ".", "--dupes-min-tokens"],
]


@pytest.mark.parametrize("command", WRAPPED)
def test_a_gate_that_cannot_be_reduced_to_a_judged_command_is_refused(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: joined shell flags, eval, variables and flags the judge does not list fail at load, never as a traceback."""
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate(command), tmp_path, set())


@pytest.mark.parametrize(
    "command",
    [
        ["ruff", "check", "."],
        ["ruff", "check", ".", "--extend-select", "C901,PLR0912,PLR0915"],
        ["ruff", "check", ".", "--select", "ALL"],
        ["ruff", "check", ".", "--output-format", "concise", "--no-cache"],
        ["bash", "-ec", "ruff check ."],
        ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
    ],
)
def test_the_listed_forms_still_pass(tmp_path: Path, command: list[str]) -> None:
    validate_gate(gate(command), tmp_path, set())


def test_the_ruff_format_gate_may_extend_exclude(tmp_path: Path) -> None:
    command = ["ruff", "format", "--check", ".", "--extend-exclude", ".agents/skills"]
    validate_gate(gate(command, "format"), tmp_path, set())


@pytest.mark.parametrize(
    "flags", [["--dupes-min-tokens", "100000"], ["--dupes-min-lines", "10000"]]
)
def test_a_fallow_gate_flag_that_loosens_the_duplicate_scan_is_refused(
    tmp_path: Path, flags: list[str]
) -> None:
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate([*DEAD, *flags], "dead-code-duplicates"), tmp_path, set())

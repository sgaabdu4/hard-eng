"""A ruff gate cannot be narrowed by a flag, a path or a wrapper around the command."""

import json
from pathlib import Path

import pytest
from gate_config import Gate, validate_gate


def lint(command: list[str], role: str = "lint") -> Gate:
    return {"name": role, "role": role, "command": command}


FLAG_FORMS = [
    ["ruff", "check", ".", "--exit-zero"],
    ["ruff", "check", ".", "--isolated"],
    ["sh", "-c", "ruff check . --ignore F401"],
    ["sh", "-c", "ruff check . --exit-zero"],
    ["bash", "-c", "ruff check . --isolated"],
]


@pytest.mark.parametrize("command", FLAG_FORMS)
def test_a_ruff_lint_gate_with_a_narrowing_flag_or_wrapper_fails(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: a flag that hides findings or skips files fails the lint gate, also inside `sh -c`."""
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(lint(command), tmp_path, set())


def test_a_package_script_that_holds_a_narrowing_flag_fails(tmp_path: Path) -> None:
    scripts = {"scripts": {"lint": "ruff check . --exit-zero"}}
    (tmp_path / "package.json").write_text(json.dumps(scripts))
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(lint(["bun", "run", "lint"]), tmp_path, set())
    scripts["scripts"]["lint"] = "ruff check ."
    (tmp_path / "package.json").write_text(json.dumps(scripts))
    with pytest.raises(ValueError, match="ruff in a package script"):
        validate_gate(lint(["bun", "run", "lint"]), tmp_path, set())


def test_a_format_gate_may_exclude_generated_folders(tmp_path: Path) -> None:
    command = ["ruff", "format", "--check", ".", "--extend-exclude", ".agents/skills"]
    validate_gate(lint(command, "format"), tmp_path, set())

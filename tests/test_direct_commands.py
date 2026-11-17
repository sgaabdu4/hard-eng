"""A gate that runs a judged tool runs it directly: a launcher, the tool, then arguments the judge reads."""

import json
from pathlib import Path

import pytest
from command_words import direct
from gate_config import Gate, validate_gate
from tool_setup import managed_command

DIRECT = "must run it directly"

WRAPPED = [
    ["sh", "-c", "ruff check ."],
    ["bash", "-c", "ruff check ."],
    ["zsh", "-c", "ruff check ."],
    ["dash", "-c", "ruff check ."],
    ["ksh", "-c", "ruff check ."],
    ["bash", "-ec", "ruff check ."],
    ["env", "ruff", "check", "."],
    ["/usr/bin/env", "ruff", "check", "."],
    ["nice", "ruff", "check", "."],
    ["python3", "-c", "import subprocess; subprocess.run(['ruff', 'check'])"],
    ["ruff", "check", ".", "||", "true"],
    ["ruff", "check", ".", "|", "cat"],
    ["ruff", "check", ".", ";", "true"],
    ["ruff", "check", ".", "&"],
    ["ruff", "check", ".", "&&", "true"],
    ["!", "ruff", "check", "."],
    ["./ruff", "check", "."],
    ["bin/fallow", "--fail-on-issues"],
    ["VAR=x", "ruff", "check", "."],
    ["uvx", "--from", "x", "ruff", "check", "."],
    ["uvx", "--with", "x", "ruff@latest", "check", "."],
    ["bash", "-c", "exec fallow --fail-on-issues"],
    ["sh", "-c", "gitleaks dir ."],
    ["sh", "-c", "cargo clippy"],
    ["bun", "x", "--package=fallow@latest", "fallow", "audit"],
    ["node", "check.mjs", "fallow", "audit"],
    ["env", "X=-Awarnings", "cargo", "clippy"],
]


@pytest.mark.parametrize("command", WRAPPED)
def test_a_judged_tool_behind_a_wrapper_is_refused_with_the_direct_form(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: shells, env, nice, python -c, paths, variables, operators and uvx options hide what the tool runs."""
    gate: Gate = {"name": "g", "command": command}
    with pytest.raises(ValueError, match=DIRECT):
        validate_gate(gate, tmp_path, set())


def scripted(tmp_path: Path, scripts: dict[str, str]) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"scripts": scripts}))


SCRIPTS = [
    {"lint": "ruff check . && echo done"},
    {"lint": "ruff check . ; true"},
    {"lint": "ruff check . || true"},
    {"lint": "sh -c 'ruff check .'"},
    {"lint": "ruff check .", "prelint": "echo hi"},
    {"lint": "ruff check .", "postlint": "echo hi"},
    {"lint": "echo hi && ruff check ."},
]


@pytest.mark.parametrize("scripts", SCRIPTS)
def test_a_script_that_is_not_one_direct_command_is_refused(
    tmp_path: Path, scripts: dict[str, str]
) -> None:
    scripted(tmp_path, scripts)
    gate: Gate = {"name": "g", "command": ["bun", "run", "lint"]}
    with pytest.raises(ValueError, match=DIRECT):
        validate_gate(gate, tmp_path, set())


ACCEPTED = [
    ["ruff", "check", "."],
    ["uvx", "ruff@latest", "check", "."],
    ["uvx", "ruff@0.9.0", "check", "."],
    ["uv", "run", "--no-sync", "ruff", "check", "."],
    ["bun", "x", "fallow@latest", "--fail-on-issues", "--only", "dead-code,health"],
    ["fallow", "--fail-on-issues"],
    ["cargo", "clippy", "--all-targets", "--", "-D", "warnings"],
    ["cargo", "+nightly", "clippy"],
    ["gitleaks", "dir", "."],
    ["uvx", "pyrefly@latest", "check", "."],
    ["bash", "scripts/not-judged.sh"],
    ["cargo", "build", "--release"],
    ["sh", "-c", "cargo build --locked && bun test"],
]


@pytest.mark.parametrize("command", ACCEPTED)
def test_a_direct_form_passes(tmp_path: Path, command: list[str]) -> None:
    validate_gate({"name": "g", "command": command}, tmp_path, set())


def test_a_script_that_is_exactly_one_direct_command_passes(tmp_path: Path) -> None:
    scripted(tmp_path, {"lint": "ruff check ."})
    gate: Gate = {"name": "g", "command": ["bun", "run", "lint"]}
    validate_gate(gate, tmp_path, set())
    assert direct(gate["command"], tmp_path) == ["ruff", "check", "."]


@pytest.mark.parametrize(
    "command",
    [
        ["ruff", "check", "src"],
        ["uvx", "ruff@latest", "check", "src"],
        ["uv", "run", "--no-sync", "ruff", "check", "src"],
    ],
)
def test_the_runner_executes_the_arguments_the_judge_reads(
    tmp_path: Path, command: list[str]
) -> None:
    """What `managed_command` hands the runner ends with the judged arguments, with nothing added in between."""
    judged = direct(command, tmp_path)
    assert judged is not None
    assert managed_command(command, tmp_path)[-len(judged) + 1 :] == judged[1:]

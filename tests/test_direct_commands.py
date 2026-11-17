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
    ["ruff", "check", ".;true"],
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
    {"lint": "ruff check --cache-dir=.ruff_cache;true"},
    {"lint": "ruff check --cache-dir=.ruff_cache&&true"},
    {"lint": "bun run lint2", "lint2": "ruff check .", "prelint2": "echo hi"},
    {"lint": "bun run lint2", "lint2": "ruff check ."},
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


def test_fix_in_a_ruff_gate_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `--fix` rewrites the files, so the findings it fixes never fail the gate."""
    gate: Gate = {
        "name": "lint",
        "role": "lint",
        "command": ["ruff", "check", ".", "--fix"],
    }
    with pytest.raises(ValueError, match="--fix"):
        validate_gate(gate, tmp_path, set())


def test_bun_without_run_checks_the_pre_script_too(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `bun lint` runs `prelint` as `bun run lint` does."""
    scripted(tmp_path, {"lint": "ruff check .", "prelint": "echo hi"})
    gate: Gate = {"name": "g", "command": ["bun", "lint"]}
    with pytest.raises(ValueError, match=DIRECT):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    "command", [["bun", "check:fallow"], ["bun", "run", "check:fallow"]]
)
def test_bun_runs_a_package_script_with_or_without_run(
    tmp_path: Path, command: list[str]
) -> None:
    """HE-NO-SWITCH-OFF: `bun <script>` runs the script as `bun run <script>` does, so Fallow's checks judge it too."""
    scripted(
        tmp_path, {"check:fallow": "fallow --only dead-code,dupes --fail-on-issues"}
    )
    gate: Gate = {"name": "g", "role": "dead-code-duplicates", "command": command}
    with pytest.raises(ValueError, match="Fallow scans must check health"):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize("command", [["true"], ["bun", "run", "lint"]])
def test_a_report_key_does_not_excuse_a_gate_from_naming_its_tool(
    command: list[str],
) -> None:
    """HE-NO-SWITCH-OFF: a `report` on a lint gate cannot stand in for the tool the role must run."""
    from tool_setup import require_role_tool

    gate: Gate = {
        "name": "lint",
        "role": "lint",
        "command": command,
        "report": {"type": "fallow", "path": "r.json"},
    }
    with pytest.raises(ValueError, match="must run `ruff check`"):
        require_role_tool("python", gate, command)


def test_a_flag_after_run_is_refused_by_name(tmp_path: Path) -> None:
    """A flag after `run` is taken for the script name; the refusal names the flag."""
    scripted(tmp_path, {"lint": "ruff check ."})
    gate: Gate = {"name": "g", "command": ["bun", "run", "--silent", "lint"]}
    with pytest.raises(ValueError, match=r"flag --silent after `run`"):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    "form",
    ["uv run --no-sync", "uv run --frozen", "bunx", "bun x", "uvx", "cargo clippy"],
)
def test_the_refusal_lists_every_allowed_form(tmp_path: Path, form: str) -> None:
    gate: Gate = {"name": "g", "command": ["sh", "-c", "ruff check ."]}
    with pytest.raises(ValueError, match=DIRECT) as raised:
        validate_gate(gate, tmp_path, set())
    assert form in str(raised.value)


def test_the_fallow_role_must_run_fallow() -> None:
    """HE-NO-SWITCH-OFF: a node script that copies a saved report is not the Fallow check."""
    from tool_setup import require_role_tool

    gate: Gate = {
        "name": "dead-code-duplicates",
        "role": "dead-code-duplicates",
        "command": ["node", "fake.mjs"],
        "report": {"type": "fallow", "path": "coverage/fallow.json"},
    }
    with pytest.raises(ValueError, match="must run `fallow`"):
        require_role_tool("javascript", gate, gate["command"])


@pytest.mark.parametrize(
    "flag", ["--silent", "--bun", "-b", "--no-install", "--elide-lines=1"]
)
def test_a_manager_flag_before_a_script_name_is_refused(
    tmp_path: Path, flag: str
) -> None:
    """HE-NO-SWITCH-OFF: a flag before the script name hides the script from every judge."""
    scripted(tmp_path, {"check:fallow": "fallow --fail-on-issues"})
    gate: Gate = {"name": "g", "command": ["bun", flag, "check:fallow"]}
    with pytest.raises(ValueError, match=rf"flag {flag.split('=')[0]} before"):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize(
    "command",
    [
        ["bunx", "fallow", "--fail-on-issues"],
        ["bun", "x", "fallow", "--fail-on-issues"],
        ["bunx", "ruff@latest", "check", "."],
        ["bun", "x", "ruff", "check", "."],
        ["bunx", "gitleaks@latest", "dir", "."],
        ["bun", "x", "gitleaks", "dir", "."],
    ],
)
def test_bunx_runs_only_a_pinned_fallow(tmp_path: Path, command: list[str]) -> None:
    """HE-NO-SWITCH-OFF: an unpinned bunx resolves a local `.bin` file, and ruff and gitleaks have their own launchers."""
    with pytest.raises(ValueError, match=DIRECT):
        validate_gate({"name": "g", "command": command}, tmp_path, set())


@pytest.mark.parametrize(
    "script", ["ruff check src\necho", "ruff check src\techo", "ruff check\rsrc"]
)
def test_a_script_with_a_line_break_or_tab_is_refused(
    tmp_path: Path, script: str
) -> None:
    """HE-NO-SWITCH-OFF: a line break or tab ends a shell command like `;` does, and the words the judge reads stop at it."""
    scripted(tmp_path, {"lint": script})
    gate: Gate = {"name": "g", "command": ["bun", "run", "lint"]}
    with pytest.raises(ValueError, match=DIRECT):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize("manager", ["npm", "pnpm", "yarn"])
def test_only_bun_runs_a_script_that_holds_a_judged_tool(
    tmp_path: Path, manager: str
) -> None:
    """HE-NO-SWITCH-OFF: npm, pnpm and yarn run a script through a shell that a project file (`script-shell`, `scriptShell`) can change."""
    scripted(tmp_path, {"lint": "ruff check ."})
    gate: Gate = {"name": "g", "command": [manager, "run", "lint"]}
    with pytest.raises(ValueError, match="write `bun run <script>`"):
        validate_gate(gate, tmp_path, set())


def put_bin(root: Path, tool: str, owner: str | None) -> None:
    binary = root / "node_modules/.bin" / tool
    binary.parent.mkdir(parents=True)
    if owner is None:
        binary.write_text("#!/bin/sh\nexit 0\n")
        return
    real = root / "node_modules" / owner / "bin" / tool
    real.parent.mkdir(parents=True)
    real.write_text("#!/bin/sh\nexit 0\n")
    binary.symlink_to(real)


def test_a_local_bin_file_named_like_the_tool_is_refused(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `bun run` puts node_modules/.bin first on the path, so a file there named `ruff` runs in place of Ruff."""
    scripted(tmp_path, {"lint": "ruff check ."})
    put_bin(tmp_path, "ruff", None)
    gate: Gate = {"name": "g", "command": ["bun", "run", "lint"]}
    with pytest.raises(ValueError, match=r"node_modules/\.bin/ruff"):
        validate_gate(gate, tmp_path, set())


def test_a_local_bin_link_into_the_tool_package_passes(tmp_path: Path) -> None:
    scripted(tmp_path, {"scan": "fallow --fail-on-issues"})
    put_bin(tmp_path, "fallow", "fallow")
    validate_gate({"name": "g", "command": ["bun", "run", "scan"]}, tmp_path, set())
    other = tmp_path / "other"
    other.mkdir()
    scripted(other, {"scan": "fallow --fail-on-issues"})
    put_bin(other, "fallow", None)
    with pytest.raises(ValueError, match=r"node_modules/\.bin/fallow"):
        validate_gate({"name": "g", "command": ["bun", "run", "scan"]}, other, set())

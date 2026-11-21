"""The Fallow variables that change what it reports cannot be set by a project or reach a gate."""

from pathlib import Path

import pytest
from gate_config import Gate, validate_gate
from gitleaks_scan import scan_environment
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

NAMES = [
    "FALLOW_COVERAGE",
    "FALLOW_COVERAGE_ROOT",
    "FALLOW_MAX_FILE_SIZE",
    "FALLOW_PRODUCTION",
    "FALLOW_AUDIT_BASE",
    "FALLOW_TYPE_AWARE",
    "FALLOW_MADE_UP_BY_A_NEWER_RELEASE",
    "CARGO_ALIAS_CLIPPY",
    "CARGO_HOME",
    "CLIPPY_CONF_DIR",
    "SHELLCHECK_OPTS",
    "RUFF_OUTPUT_FILE",
    "RUFF_MADE_UP_BY_A_NEWER_RELEASE",
]


@pytest.mark.parametrize("name", NAMES)
def test_a_gate_runs_without_the_variable(name: str) -> None:
    """HE-NO-SWITCH-OFF: a made-up coverage map or a production mode changes what Fallow reports, so gates run without them."""
    assert name not in scan_environment({name: "x", "PATH": "/bin"})


@pytest.mark.parametrize("name", NAMES)
@pytest.mark.parametrize(
    ("file", "text"),
    [
        (".github/workflows/ci.yml", "env:\n  @N@: x\n"),
        ("scripts/check.sh", "export @N@=x\n"),
        (".env", "@N@=x\n"),
    ],
)
def test_a_workflow_or_script_that_sets_the_variable_is_refused(
    tmp_path: Path, name: str, file: str, text: str
) -> None:
    message = refusal(project(tmp_path, {file: text.replace("@N@", name)}))
    assert f"{file}:" in message
    assert name in message


def test_prose_that_names_a_fallow_variable_passes(tmp_path: Path) -> None:
    """Only a file that sets a variable is refused; a note that names it is not."""
    validate_whole_project(
        project(tmp_path, {"README.md": "Set FALLOW_COVERAGE=x on your machine.\n"})
    )


@pytest.mark.parametrize(
    "command",
    [
        ["@N@=x.json", "fallow", "--fail-on-issues"],
        ["env", "@N@=x.json", "fallow", "--fail-on-issues"],
    ],
)
@pytest.mark.parametrize("name", NAMES)
def test_a_gate_command_that_sets_the_variable_fails(
    tmp_path: Path, name: str, command: list[str]
) -> None:
    gate: Gate = {
        "name": "fallow",
        "role": "dead-code-duplicates",
        "command": [word.replace("@N@", name) for word in command],
    }
    with pytest.raises(ValueError, match="HE-NO-SWITCH-OFF"):
        validate_gate(gate, tmp_path, set())


@pytest.mark.parametrize("name", ["RUFF_CACHE_DIR", "RUFF_NO_CACHE"])
def test_a_ruff_variable_that_changes_no_finding_may_be_set(
    tmp_path: Path, name: str
) -> None:
    """Only the cache variables of Ruff change no result, so they stay."""
    validate_whole_project(project(tmp_path, {".env": f"{name}=x\n"}))
    assert name in scan_environment({name: "x"})


def test_a_gate_runs_without_a_config_home_that_shellcheck_reads() -> None:
    """HE-NO-SWITCH-OFF: ShellCheck reads a `shellcheckrc` from `XDG_CONFIG_HOME`, so gates run without it."""
    assert "XDG_CONFIG_HOME" not in scan_environment(
        {"XDG_CONFIG_HOME": "x", "PATH": "/bin"}
    )

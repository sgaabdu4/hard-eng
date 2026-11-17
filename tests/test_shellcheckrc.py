"""A ShellCheck settings file may not turn a rule off, and the generated shell gate ignores settings files."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project


@pytest.mark.parametrize(
    "name", [".shellcheckrc", "scripts/.shellcheckrc", "shellcheckrc"]
)
def test_a_shellcheck_settings_file_that_disables_a_rule_is_refused(
    tmp_path: Path, name: str
) -> None:
    """HE-NO-SWITCH-OFF: `disable=all` in a settings file hides every finding that the shell gate would report."""
    message = refusal(project(tmp_path, {name: "disable=all\n"}))
    assert f"{name}:1 sets 'disable=all'" in message


@pytest.mark.parametrize(
    "text", ["external-sources=true\n", "source-path=SCRIPTDIR\n", "# disable=all\n"]
)
def test_a_shellcheck_settings_file_that_disables_nothing_passes(
    tmp_path: Path, text: str
) -> None:
    validate_whole_project(project(tmp_path, {".shellcheckrc": text}))

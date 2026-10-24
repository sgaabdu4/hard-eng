"""Every CI job that launches mise sets the package it launches."""

import pytest
from ci_setup import migrate_launcher
from conftest import SOURCE

TEMPLATE = (SOURCE / ".github/workflows/hard-eng.yml").read_text()
ECHO = next(line for line in TEMPLATE.splitlines() if "MISE_PACKAGE=" in line)
JOB = """  {name}:
    runs-on: {runner}
    steps:
      - run: |
          {{
{echo}            echo "BUN_INSTALL_CACHE_DIR=$RUNNER_TEMP/bun"
          }} >> "$GITHUB_ENV"
      - run: bun x --package="$MISE_PACKAGE" mise --version
"""


def _job(name: str, runner: str, echo: bool) -> str:
    line = ECHO + "\n" if echo else ""
    return JOB.format(name=name, runner=runner, echo=line)


def test_each_job_that_launches_mise_gets_the_package_line() -> None:
    hosted = _job("hosted", "ubuntu-latest", echo=False)
    workflow = "jobs:\n" + _job("local", "self-hosted", echo=True) + hosted
    migrated = migrate_launcher(SOURCE, workflow)
    assert migrated.count('echo "MISE_PACKAGE=') == 2
    assert migrated.split("  hosted:\n")[1].count('echo "MISE_PACKAGE=') == 1
    assert migrate_launcher(SOURCE, migrated) == migrated


def test_a_job_without_the_anchor_is_named(capsys: pytest.CaptureFixture[str]) -> None:
    bare = '  bare:\n    steps:\n      - run: bun x --package="$MISE_PACKAGE" mise\n'
    workflow = "jobs:\n" + _job("local", "self-hosted", echo=True) + bare
    assert migrate_launcher(SOURCE, workflow) == workflow
    assert "CI launcher not updated in job bare" in capsys.readouterr().err


def test_template_is_unchanged() -> None:
    assert migrate_launcher(SOURCE, TEMPLATE) == TEMPLATE

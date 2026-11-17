"""A shellcheck directive that hides a finding is a switch-off; one that adds checks or follows a real file is not."""

from pathlib import Path

import pytest
from test_strict_refusals import project, refusal
from whole_project import validate_whole_project

FIX = "read the file without a dynamic `source`"


@pytest.mark.parametrize(
    "directive",
    ["source=/dev/null", "source=nowhere.sh", "shell=ksh"],
)
def test_a_shellcheck_directive_that_hides_a_finding_names_the_fix(
    tmp_path: Path, directive: str
) -> None:
    """HE-NO-SWITCH-OFF: `source=` at a missing path or /dev/null hides SC1090 as `disable=` does, and `shell=` changes the dialect."""
    root = project(tmp_path, {"build.sh": f"#!/bin/bash\n# shellcheck {directive}\n"})
    assert FIX in refusal(root)


@pytest.mark.parametrize(
    "directive",
    [
        "enable=require-variable-braces",
        "source=lib.sh",
        "source-path=SCRIPTDIR",
        "external-sources=true",
    ],
)
def test_a_shellcheck_directive_that_hides_nothing_passes(
    tmp_path: Path, directive: str
) -> None:
    files = {"build.sh": f"#!/bin/bash\n# shellcheck {directive}\n", "lib.sh": "x=1\n"}
    validate_whole_project(project(tmp_path, files))

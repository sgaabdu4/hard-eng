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


GRADLEW = "#!/bin/sh\n# shellcheck " + "disable=SC2039,SC3045\nx=1\n"


def test_a_generated_gradle_wrapper_is_exempt_through_gitattributes(
    tmp_path: Path,
) -> None:
    """The wrapper's directives come from Gradle: the existing `linguist-generated` route exempts it, with no path list."""
    files = {
        "app/gradlew": GRADLEW,
        ".gitattributes": "app/gradlew linguist-generated=true\n",
    }
    validate_whole_project(project(tmp_path, files))


def test_a_gradle_wrapper_that_is_not_marked_generated_names_the_route(
    tmp_path: Path,
) -> None:
    message = refusal(project(tmp_path, {"app/gradlew": GRADLEW}))
    assert "app/gradlew:2" in message
    assert "linguist-generated=true" in message
    assert ".gitattributes" in message


@pytest.mark.parametrize(
    "directive",
    [
        "disable=SC2086 source=lib.sh",
        "source=lib.sh disable=SC2086",
        "shell=ksh source=lib.sh",
        "enable=require-variable-braces disable=SC2086 source=lib.sh",
    ],
)
def test_a_disable_or_shell_key_fails_whatever_else_the_directive_holds(
    tmp_path: Path, directive: str
) -> None:
    """HE-NO-SWITCH-OFF: a `source=` that names a real file does not excuse a `disable=` or `shell=` key beside it."""
    files = {"build.sh": f"#!/bin/bash\n# shellcheck {directive}\n", "lib.sh": "x=1\n"}
    assert "build.sh:2" in refusal(project(tmp_path, files))

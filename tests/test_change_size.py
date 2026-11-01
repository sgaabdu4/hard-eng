import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path

import pytest
from conftest import SOURCE
from test_plans import edit, new_file, sized_branch

SANDBOX_SIZE = """
import json, subprocess
from pathlib import Path
from change_size import size_verdict
listed = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard"], text=True)
print(json.dumps([listed.splitlines(), *size_verdict(Path.cwd())]))
"""


@pytest.mark.skipif(
    shutil.which("bwrap") is None, reason="the Claude Code Linux sandbox uses bwrap"
)
@pytest.mark.parametrize(
    ("change", "verdict"),
    [
        (partial(edit, name="a.py", count=2), [True, "1 file, 4 changed lines"]),
        (new_file, [False, "it adds, deletes or renames the file new.py"]),
    ],
    ids=["small", "new"],
)
def test_sandbox_placeholder_does_not_add_a_file(
    repository: Path, change: Callable[[Path], object], verdict: list[object]
) -> None:
    sized_branch(repository)
    change(repository)
    placeholder = ["--ro-bind", "/dev/null", str(repository / ".bashrc")]
    sandbox = ["bwrap", "--dev-bind", "/", "/", *placeholder]
    found = subprocess.run(
        [*sandbox, sys.executable, "-c", SANDBOX_SIZE],
        cwd=repository,
        env={**os.environ, "PYTHONPATH": str(SOURCE / ".hooks")},
        capture_output=True,
        text=True,
        check=True,
    )
    listed, *measured = json.loads(found.stdout)
    assert ".bashrc" in listed
    assert measured == verdict

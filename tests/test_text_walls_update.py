"""HE-NO-TEXT-WALLS: an update brings the rule and its pinned reader to an old project with no change to its gates file."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
import update
from conftest import SEAL, commit
from test_updates import select_release

RULE_FILES = (
    "text_walls.py",
    "text_readers.py",
    "text_reader_programs.py",
    "text_walls.bun.lock",
)
WALL = "export const A = () => <p>" + " ".join(["word"] * 40) + "</p>;\n"


def test_an_updated_old_project_refuses_a_new_wall_with_its_gates_file_unchanged(
    release: tuple[Path, Path, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-NO-TEXT-WALLS: after an update of a project from before the rule, a new wall is refused and the gates file is the same."""
    source, target, _ = release
    for name in RULE_FILES:
        (target / ".hooks" / name).unlink(missing_ok=True)
    commit(target, "project from a release before the screen text rule")
    gates = (target / "hard-eng.gates.json").read_bytes()
    select_release(source, monkeypatch)
    update.update(target)
    for name in RULE_FILES:
        assert (target / ".hooks" / name).is_file(), name
    assert (target / "hard-eng.gates.json").read_bytes() == gates
    (target / "src").mkdir()
    (target / "src/Card.tsx").write_text(WALL)
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(target / '.hooks')!r})\n"
        "from pathlib import Path\n"
        "from comments import validate_suppressions\n"
        f"validate_suppressions(Path({str(target)!r}), 'HEAD')\n"
    )
    sealed = {**os.environ, "RUNNER_TEMP": str(SEAL / "runner")}
    done = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=sealed,
    )
    assert done.returncode == 1
    assert "HE-NO-TEXT-WALLS" in done.stderr
    assert "src/Card.tsx:1:" in done.stderr

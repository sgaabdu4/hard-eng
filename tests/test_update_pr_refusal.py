import subprocess
import sys
from pathlib import Path

import pytest
import update_pr
import update_runner
from conftest import add_origin
from test_update_runner import refused_release


def test_update_pr_fails_after_a_remembered_refusal(
    release: tuple[Path, Path, str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    target, _ = refused_release(release, monkeypatch)
    assert update_runner.apply_update(target) == 0
    capsys.readouterr()
    assert update_pr.publish(target) == 1
    printed = capsys.readouterr().out
    assert "Hard Eng update failed" in printed
    assert "secrets-files requires native" in printed
    assert "Nothing to publish" not in printed


NO_NEWER_RELEASE = """
import runpy, sys
sys.path.insert(0, ".hooks")
import update
update.latest_verified = lambda previous: None
sys.argv = [".hooks/hard-eng.py", *sys.argv[1:]]
runpy.run_path(".hooks/hard-eng.py", run_name="__main__")
"""


@pytest.mark.parametrize("command", [["update-pr"], ["update", "--apply"]])
def test_update_pr_with_no_update_branch_prints_no_git_error(
    release: tuple[Path, Path, str], command: list[str]
) -> None:
    _, target, _ = release
    add_origin(target)
    done = subprocess.run(
        [sys.executable, "-c", NO_NEWER_RELEASE, *command],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout
    assert "fatal:" not in done.stderr

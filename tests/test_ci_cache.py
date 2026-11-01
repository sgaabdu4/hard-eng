"""Setup reports workflow cache steps that cannot work on a self-hosted runner."""

from pathlib import Path

import pytest
from ci_setup import configure_ci
from conftest import SOURCE

SELF_HOSTABLE = "${{ vars.CI_RUNS_ON && fromJSON(vars.CI_RUNS_ON) || 'ubuntu-latest' }}"
PLAYWRIGHT_CACHE = """      - uses: actions/cache@v6
        with:
          path: ~/.cache/ms-playwright
          key: browsers
"""


def workflow(runs_on: str, steps: str, job_env: str = "") -> str:
    return (
        f"on: push\njobs:\n  check:\n    runs-on: {runs_on}\n{job_env}"
        f"    steps:\n{steps}"
    )


def setup_messages(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str
) -> tuple[str, dict[str, str]]:
    path = tmp_path / ".github/workflows/ci.yml"
    path.parent.mkdir(parents=True)
    path.write_text(text)
    changes: dict[str, str] = {}
    configure_ci(tmp_path, SOURCE, {"packages": [], "shared": []}, changes)
    return capsys.readouterr().err, changes


@pytest.mark.parametrize(
    "line",
    [
        "          MISE_DATA_DIR: ${{ runner.temp }}/hard-eng-tools/mise/data",
        '          echo "MISE_DATA_DIR=${RUNNER_TEMP}/hard-eng-tools/mise/data" >> "$GITHUB_ENV"',
    ],
    ids=["mapping", "braces"],
)
def test_a_tool_directory_the_move_cannot_rewrite_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: str
) -> None:
    errors, _ = setup_messages(
        tmp_path,
        capsys,
        workflow("ubuntu-latest", f"      - run: |\n{line}\n"),
    )
    assert "CI tool directories: .github/workflows/ci.yml" in errors
    assert "MISE_DATA_DIR" in errors
    assert "${MISE_DATA_DIR:-$RUNNER_TEMP/" in errors


def test_a_moved_tool_directory_is_not_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = '          echo "MISE_DATA_DIR=$RUNNER_TEMP/hard-eng-tools/mise/data"'
    errors, changes = setup_messages(
        tmp_path, capsys, workflow("ubuntu-latest", f"      - run: |\n{line}\n")
    )
    assert changes
    assert "CI tool directories" not in errors


def test_a_playwright_cache_on_a_self_hostable_job_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    errors, _ = setup_messages(
        tmp_path, capsys, workflow(SELF_HOSTABLE, PLAYWRIGHT_CACHE)
    )
    assert "CI browser cache: .github/workflows/ci.yml job check" in errors
    assert "~/.cache/ms-playwright" in errors
    assert "PLAYWRIGHT_BROWSERS_PATH" in errors


@pytest.mark.parametrize(
    ("runs_on", "job_env"),
    [
        ("ubuntu-latest", ""),
        (SELF_HOSTABLE, "    env:\n      PLAYWRIGHT_BROWSERS_PATH: /opt/browsers\n"),
    ],
    ids=["hosted-only", "path-set"],
)
def test_a_playwright_cache_that_can_exist_is_not_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], runs_on: str, job_env: str
) -> None:
    errors, _ = setup_messages(
        tmp_path, capsys, workflow(runs_on, PLAYWRIGHT_CACHE, job_env)
    )
    assert "CI browser cache" not in errors

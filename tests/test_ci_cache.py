"""Setup reports workflow cache steps that cannot work on a self-hosted runner."""

from pathlib import Path

import pytest
import yaml
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


def test_several_tool_directories_get_one_message_with_one_grouped_step(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    job_env = (
        "    env:\n"
        "      MISE_DATA_DIR: ${{ runner.temp }}/hard-eng-tools/mise/data\n"
        "      MISE_CACHE_DIR: ${{ runner.temp }}/hard-eng-tools/mise/cache\n"
    )
    errors, _ = setup_messages(
        tmp_path, capsys, workflow("ubuntu-latest", "      - run: true\n", job_env)
    )
    assert errors.count("CI tool directories") == 1
    assert "ci.yml:6,7 set MISE_DATA_DIR, MISE_CACHE_DIR from" in errors
    step = (
        '{ echo "MISE_DATA_DIR=${MISE_DATA_DIR:-$RUNNER_TEMP/hard-eng-tools/...}"; '
        'echo "MISE_CACHE_DIR=${MISE_CACHE_DIR:-$RUNNER_TEMP/hard-eng-tools/...}"; '
        '} >> "$GITHUB_ENV"'
    )
    assert f"those lines with a step whose `run: |` block holds {step};" in errors
    assert yaml.safe_load(f"run: |\n  {step}\n") == {"run": f"{step}\n"}
    with pytest.raises(yaml.YAMLError):
        yaml.safe_load(f"run: {step}\n")


def test_the_tool_directory_step_done_as_printed_leaves_no_note_and_no_pending_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    line = "      MISE_DATA_DIR: ${{ runner.temp }}/hard-eng-tools/mise/data\n"
    before = workflow("ubuntu-latest", "      - run: true\n", "    env:\n" + line)
    errors, _ = setup_messages(tmp_path / "before", capsys, before)
    assert "ci.yml:6 sets MISE_DATA_DIR from" in errors
    step = 'echo "MISE_DATA_DIR=${MISE_DATA_DIR:-$RUNNER_TEMP/hard-eng-tools/...}"'
    assert f'whose `run: |` block holds {step} >> "$GITHUB_ENV";' in errors
    done = step.replace("...", "mise/data") + ' >> "$GITHUB_ENV"'
    block = f"      - run: |\n          {done}\n"
    after = workflow("ubuntu-latest", f"{block}      - run: true\n")
    errors, changes = setup_messages(tmp_path / "after", capsys, after)
    assert "CI tool directories" not in errors
    assert changes == {}


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

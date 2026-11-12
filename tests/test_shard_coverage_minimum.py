"""A project's own coverage minimum: where the shard merge reads it and how it judges the total."""

from pathlib import Path

import pytest
from coverage.results import should_fail_under
from shards import below_minimum, coverage_minimum, merged_total

PYTEST = ["uv", "run", "pytest", "--cov"]
COVERAGERC = "[report]\nfail_under = 71\nprecision = 1\n"
SETUP_CFG = "[coverage:report]\nfail_under = 72\n"
PYPROJECT = "[tool.coverage.report]\nfail_under = 73\n"
ADDOPTS = '[tool.pytest.ini_options]\naddopts = "-q --cov-fail-under=65"\n'


@pytest.mark.parametrize(
    ("command", "files", "expected"),
    [
        (
            [*PYTEST, "--cov-fail-under=80"],
            {},
            (80.0, "--cov-fail-under in the tests command", 0),
        ),
        (
            [*PYTEST, "--cov-fail-under", "75.5"],
            {},
            (75.5, "--cov-fail-under in the tests command", 0),
        ),
        (
            PYTEST,
            {"pyproject.toml": ADDOPTS},
            (65.0, "--cov-fail-under in pyproject.toml", 0),
        ),
        (
            PYTEST,
            {"pytest.ini": "[pytest]\naddopts = --cov-fail-under 66\n"},
            (66.0, "--cov-fail-under in pytest.ini", 0),
        ),
        (PYTEST, {".coveragerc": COVERAGERC}, (71.0, "fail_under in .coveragerc", 1)),
        (PYTEST, {"setup.cfg": SETUP_CFG}, (72.0, "fail_under in setup.cfg", 0)),
        (PYTEST, {"tox.ini": SETUP_CFG}, (72.0, "fail_under in tox.ini", 0)),
        (
            PYTEST,
            {"pyproject.toml": PYPROJECT},
            (73.0, "fail_under in pyproject.toml", 0),
        ),
        (
            PYTEST,
            {".coveragerc.toml": "[report]\nfail_under = 74\n"},
            (74.0, "fail_under in .coveragerc.toml", 0),
        ),
        (
            [*PYTEST, "--cov-fail-under=80"],
            {"pyproject.toml": ADDOPTS, ".coveragerc": COVERAGERC},
            (80.0, "--cov-fail-under in the tests command", 1),
        ),
        (
            PYTEST,
            {"pyproject.toml": ADDOPTS + PYPROJECT, ".coveragerc": COVERAGERC},
            (65.0, "--cov-fail-under in pyproject.toml", 1),
        ),
        (
            PYTEST,
            {
                ".coveragerc": COVERAGERC,
                "setup.cfg": SETUP_CFG,
                "pyproject.toml": PYPROJECT,
            },
            (71.0, "fail_under in .coveragerc", 1),
        ),
        (
            PYTEST,
            {
                "setup.cfg": SETUP_CFG,
                "tox.ini": "[coverage:report]\nfail_under = 90\n",
                "pyproject.toml": PYPROJECT,
            },
            (72.0, "fail_under in setup.cfg", 0),
        ),
        (
            PYTEST,
            {
                "setup.cfg": "[tool:pytest]\nxfail_strict = true\n[report]\nfail_under = 90\n",
                "pyproject.toml": PYPROJECT,
            },
            (73.0, "fail_under in pyproject.toml", 0),
        ),
        (
            PYTEST,
            {
                "pyproject.toml": "[tool.other.report]\nfail_under = 90\n[tool.coverage.run]\nbranch = true\n"
            },
            (0.0, "", 0),
        ),
        (PYTEST, {"setup.cfg": "[metadata]\nname = x\n"}, (0.0, "", 0)),
        (PYTEST, {}, (0.0, "", 0)),
    ],
)
def test_the_minimum_comes_from_the_command_then_the_pytest_settings_then_the_first_coverage_file(
    tmp_path: Path,
    command: list[str],
    files: dict[str, str],
    expected: tuple[float, str, int],
) -> None:
    for name, text in files.items():
        (tmp_path / name).write_text(text)
    assert coverage_minimum(tmp_path, command) == expected


def test_the_total_counts_branches_when_the_report_has_them() -> None:
    lines = {"summary": {"covered_lines": 8, "num_statements": 10}}
    branches = {
        "summary": {
            "covered_lines": 8,
            "num_statements": 10,
            "covered_branches": 2,
            "num_branches": 6,
        }
    }
    assert merged_total({"files": {"a.py": lines}}) == 80.0
    assert merged_total({"files": {"a.py": branches}}) == 100.0 * 10 / 16
    assert merged_total({"files": {"a.py": lines, "b.py": lines}}) == 80.0


@pytest.mark.parametrize("precision", [0, 1, 2])
@pytest.mark.parametrize("minimum", [0.0, 50.0, 69.5, 70.0, 99.5, 100.0])
@pytest.mark.parametrize(
    "total",
    [0.0, 49.99, 50.0, 69.49, 69.5, 69.51, 69.96, 70.0, 99.49, 99.5, 99.99, 100.0],
)
def test_the_verdict_is_the_one_of_the_coverage_tool(
    total: float, minimum: float, precision: int
) -> None:
    assert below_minimum(total, minimum, precision) is should_fail_under(
        total, minimum, precision
    )

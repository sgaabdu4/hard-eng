"""A project's own coverage minimum: where the shard merge reads it and how it judges the total."""

from pathlib import Path

import pytest
from coverage.results import display_covered, should_fail_under
from shards import below_minimum, coverage_minimum, merged_total, shown

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


TOX_ENV = (
    "[testenv:integration]\ncommands = pytest tests/integration --cov-fail-under=0\n"
)
HATCH = '[tool.hatch.envs.default.scripts]\ncov = "pytest --cov-fail-under=0"\n'
FROM_COVERAGE = (73.0, "fail_under in pyproject.toml", 0)


@pytest.mark.parametrize(
    ("files", "expected"),
    [
        (
            {
                "pyproject.toml": '[tool.pytest.ini_options]\naddopts = ["--cov-fail-under", "80"]\n'
            },
            (80.0, "--cov-fail-under in pyproject.toml", 0),
        ),
        (
            {
                "pytest.toml": '[pytest]\naddopts = ["--cov-fail-under=81"]\n',
                "pyproject.toml": ADDOPTS,
            },
            (81.0, "--cov-fail-under in pytest.toml", 0),
        ),
        (
            {"pyproject.toml": '[tool.pytest]\naddopts = ["--cov-fail-under=82"]\n'},
            (82.0, "--cov-fail-under in pyproject.toml", 0),
        ),
        (
            {"setup.cfg": "[tool:pytest]\naddopts = -q\n    --cov-fail-under=83\n"},
            (83.0, "--cov-fail-under in setup.cfg", 0),
        ),
        (
            {
                "tox.ini": "[pytest]\naddopts = --cov-fail-under=84 --cov-fail-under 85\n"
            },
            (85.0, "--cov-fail-under in tox.ini", 0),
        ),
        ({"tox.ini": TOX_ENV, "pyproject.toml": PYPROJECT}, FROM_COVERAGE),
        ({"pyproject.toml": HATCH + PYPROJECT}, FROM_COVERAGE),
        (
            {
                "pyproject.toml": '[tool.pytest.ini_options]\n# addopts = "--cov-fail-under=50"\n'
                + PYPROJECT
            },
            FROM_COVERAGE,
        ),
        ({"pytest.ini": "", "pyproject.toml": ADDOPTS}, (0.0, "", 0)),
        (
            {
                "tox.ini": "[pytest]\naddopts = -q\n",
                "setup.cfg": "[tool:pytest]\naddopts = --cov-fail-under=90\n",
            },
            (0.0, "", 0),
        ),
        (
            {
                "pyproject.toml": "[project]\nname = 'x'\n",
                "tox.ini": "[pytest]\naddopts = --cov-fail-under=86\n",
            },
            (86.0, "--cov-fail-under in tox.ini", 0),
        ),
    ],
    ids=[
        "a list of two items",
        "pytest.toml comes first",
        "the native table",
        "setup.cfg on two lines",
        "the last value wins",
        "a tox environment is not pytest settings",
        "a script of another tool is not pytest settings",
        "a comment is not a setting",
        "an empty pytest.ini ends the search",
        "the first file with a pytest section ends the search",
        "a pyproject.toml with no pytest table does not end it",
    ],
)
def test_the_minimum_of_the_pytest_settings_is_in_the_addopts_of_the_file_that_pytest_reads(
    tmp_path: Path, files: dict[str, str], expected: tuple[float, str, int]
) -> None:
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    assert coverage_minimum(tmp_path, PYTEST) == expected


def test_the_pytest_settings_of_a_parent_folder_apply_to_the_package(
    tmp_path: Path,
) -> None:
    package = tmp_path / "packages/a"
    package.mkdir(parents=True)
    (package / "pyproject.toml").write_text("[project]\nname = 'a'\n")
    (tmp_path / "pyproject.toml").write_text(ADDOPTS)
    place = "--cov-fail-under in ../../pyproject.toml"
    assert coverage_minimum(package, PYTEST) == (65.0, place, 0)


def test_a_settings_file_that_cannot_be_read_is_named(tmp_path: Path) -> None:
    (tmp_path / "tox.ini").write_text("addopts = -q\n[pytest]\n")
    with pytest.raises(ValueError, match=r"^tox\.ini cannot be read: "):
        coverage_minimum(tmp_path, PYTEST)


@pytest.mark.parametrize("precision", [0, 1, 2])
@pytest.mark.parametrize(
    "total", [0.0, 0.004, 0.04, 0.4, 69.96, 99.6, 99.96, 99.996, 100.0]
)
def test_the_printed_total_is_the_one_of_the_coverage_tool(
    total: float, precision: int
) -> None:
    assert shown(total, precision) == display_covered(total, precision)


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

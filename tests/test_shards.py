"""CI test shards: the field, the split, the shard run and the report merge."""

import sys
from argparse import ArgumentParser
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from ci_jobs import add_shard_option
from conftest import configure, gate
from gate_config import Gate, Group, validate_group
from shards import shard_groups, split


def shard_group(path: str, role: str | None, value: object) -> Group:
    options = {"role": role} if role else {}
    return cast(
        Group,
        {"path": path, "checks": [gate("suite", "pass", shards=value, **options)]},
    )


@pytest.mark.parametrize(
    ("path", "role", "value", "accepted"),
    [
        (".", "tests", 6, True),
        ("api", "tests", 2, True),
        (".", "tests", 16, True),
        (".", "tests", "6", False),
        (".", "tests", 1, False),
        (".", "tests", 17, False),
        (".", "tests", True, False),
        ("api", "tests", 0, False),
        (".", "lint", 6, False),
        (".", None, 6, False),
    ],
)
def test_shards_is_a_whole_number_from_2_to_16_on_a_tests_gate(
    tmp_path: Path, path: str, role: str | None, value: object, accepted: bool
) -> None:
    (tmp_path / "api").mkdir()
    group = shard_group(path, role, value)
    if accepted:
        assert validate_group(tmp_path, group, set()) == 1
        return
    with pytest.raises(ValueError, match="shards must be 2 to 16 on a tests gate"):
        validate_group(tmp_path, group, set())


def suite(shards: int | None = None, command: str = "pytest") -> Gate:
    check: Gate = {
        "name": "tests",
        "role": "tests",
        "command": ["uv", "run", command],
        "report": {"type": "python-tests", "tests": "j.xml", "coverage": "c.json"},
    }
    if shards:
        check["shards"] = shards
    return check


def package(path: str, shards: int | None = None) -> Group:
    steps: list[Gate] = [
        {"name": "install", "role": "lockfiles", "command": ["uv", "sync"]},
        {"name": "lint", "role": "lint", "command": ["ruff", "check"]},
        suite(shards),
    ]
    return {"path": path, "checks": steps}


def names(groups: list[Group]) -> list[str]:
    return [
        f"{group['path']}/{check['name']}"
        for group in groups
        for check in group["checks"]
    ]


def test_split_gives_each_file_to_the_lightest_shard_largest_first() -> None:
    sizes = {"a.py": 5, "b.py": 4, "d.py": 3, "c.py": 3, "e.py": 1}
    assert split(sizes, 2) == [["a.py", "d.py"], ["b.py", "c.py", "e.py"]]
    assert split({"x.py": 2, "y.py": 2, "z.py": 2}, 3) == [["x.py"], ["y.py"], ["z.py"]]


def test_more_shards_than_files_leaves_a_shard_empty() -> None:
    assert split({"a.py": 1, "b.py": 2}, 4) == [["b.py"], ["a.py"], [], []]


def test_rest_drops_only_the_tests_gates_that_have_shards() -> None:
    groups = [package(".", 6), package("api", 3), package("web")]
    assert names(shard_groups(groups, "rest")) == [
        "./install",
        "./lint",
        "api/install",
        "api/lint",
        "web/install",
        "web/lint",
        "web/tests",
    ]
    assert names(shard_groups(groups, "merge")) == ["./tests", "api/tests"]


def test_a_shard_keeps_its_tests_gate_and_the_installs_above_it() -> None:
    groups = [
        package(".", None),
        package("pkg"),
        package("pkg/sub", 4),
        package("other"),
    ]
    chosen = shard_groups(groups, "2")
    assert names(chosen) == [
        "./install",
        "pkg/install",
        "pkg/sub/install",
        "pkg/sub/tests",
    ]
    assert [check.get("part") for check in chosen[-1]["checks"]] == [None, "2"]
    assert "part" not in groups[2]["checks"][2]


def test_a_gate_with_fewer_shards_runs_nothing_in_a_higher_shard() -> None:
    groups = [package(".", 6), package("api", 3)]
    assert names(shard_groups(groups, "5")) == ["./install", "./tests"]
    assert shard_groups(groups, "7") == []


def test_without_shards_rest_runs_every_gate_and_a_shard_runs_none(
    runner: ModuleType, tmp_path: Path
) -> None:
    groups = [package(".", None), package("api")]
    assert shard_groups(groups, "rest") == groups
    assert shard_groups(groups, "1") == [] == shard_groups(groups, "merge")
    ran = tmp_path / "ran"
    configure(tmp_path, [gate("suite", f"open({str(ran)!r}, 'w')")])
    assert runner.check(shard="1") == 0
    assert not ran.exists()
    assert runner.check(shard="rest") == 0
    assert ran.exists()


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        ("1", "1"),
        ("12", "12"),
        ("rest", "rest"),
        ("merge", "merge"),
        ("0", None),
        ("two", None),
        ("2/6", None),
        ("-1", None),
        ("", None),
    ],
)
def test_the_shard_flag_takes_a_number_rest_or_merge(
    capsys: pytest.CaptureFixture[str], value: str, accepted: str | None
) -> None:
    parser = add_shard_option(ArgumentParser())
    if accepted:
        assert parser.parse_args(["--shard", value]).shard == accepted
        return
    with pytest.raises(SystemExit):
        parser.parse_args(["--shard", value])
    assert "--shard takes a shard number, rest or merge" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("command", "report", "refused"),
    [
        (["sh", "-c", "pytest -q"], "python-tests", True),
        (["bun", "test"], "lcov-tests", True),
        (["flutter", "test"], "dart-tests", True),
        (["xcodebuild", "test"], "xcode-tests", True),
        (["uv", "run", "--no-sync", "pytest", "-n", "auto"], "python-tests", False),
        ([sys.executable, "-m", "pytest"], "python-tests", False),
    ],
)
def test_shards_need_a_direct_pytest_command(
    command: list[str], report: str, refused: bool
) -> None:
    check = {
        **suite(3),
        "command": command,
        "report": {"type": report, "tests": "j", "coverage": "c"},
    }
    groups = [package("."), cast(Group, {"path": "api", "checks": [cast(Gate, check)]})]
    if not refused:
        assert names(shard_groups(groups, "rest")) == ["./install", "./lint", "./tests"]
        return
    with pytest.raises(
        ValueError,
        match=r'^api/tests: shards split pytest suites only, and the command must run pytest directly\. Remove "shards" from this gate in hard-eng.gates.json\.$',
    ):
        shard_groups(groups, "rest")

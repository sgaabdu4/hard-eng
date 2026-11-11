"""CI test shards: the field, the split, the shard run and the report merge."""

import json
import os
import sys
import threading
from argparse import ArgumentParser
from pathlib import Path
from types import ModuleType
from typing import cast

import pytest
from ci_jobs import add_shard_option
from conftest import configure, gate
from gate_config import Gate, Group, validate_group
from gate_times import gate_limit
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


LOG_HOOKS = """
def pytest_sessionstart(session):
    with open({log!r}, "a") as log:
        log.write("collect\\n" if session.config.option.collectonly else "run\\n")


def pytest_runtest_logstart(nodeid, location):
    with open({log!r}, "a") as log:
        log.write("ran " + location[0] + "\\n")


def pytest_sessionfinish(session):
    if not session.config.option.collectonly:
        with open("c.json", "w") as report:
            report.write({low!r})
"""
LOW_COVERAGE = json.dumps(
    {"files": {"lib.py": {"summary": {"covered_lines": 1, "num_statements": 10}}}}
)
PACKAGE = {"language": "python", "sources": ["lib.py"]}


@pytest.fixture
def shard_project(runner: ModuleType, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in [*os.environ]:
        if name.startswith(("COV_CORE_", "COVERAGE_")):
            monkeypatch.delenv(name)
    root = runner.ROOT
    log = root / "log.txt"
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n'
        'python_files = ["test_*.py", "check_*.py"]\n'
    )
    (root / "lib.py").write_text("value = 1\n")
    (root / "conftest.py").write_text(LOG_HOOKS.format(log=str(log), low=LOW_COVERAGE))
    for name, padding in {
        "tests/test_a.py": 3000,
        "tests/test_b.py": 2000,
        "tests/check_c.py": 1000,
        "extra/tests/test_outside.py": 10,
        "tests/child/test_child.py": 10,
    }.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(
            f"def test_it() -> None:\n    pass\n# {'x' * padding}\n"
        )
    (root / "tests/child/lib.py").write_text("value = 2\n")
    return root


def shard_gate(count: int | None, name: str = "tests") -> Gate:
    check = suite(count)
    check["name"] = name
    check["command"] = [sys.executable, "-m", "pytest", "--junitxml=j.xml"]
    return check


def shard_package(path: str, count: int | None) -> Group:
    return cast(Group, {"path": path, **PACKAGE, "checks": [shard_gate(count)]})


def project_groups(count: int | None) -> list[Group]:
    return [shard_package(".", count), shard_package("tests/child", None)]


def run_part(runner: ModuleType, part: str, count: int | None = 2) -> bool:
    (runner.ROOT / "hard-eng.gates.json").write_text(
        json.dumps({"packages": project_groups(count), "shared": []})
    )
    groups = project_groups(count)
    chosen = shard_groups(groups, part)[0]
    return runner.run_gate(chosen, chosen["checks"][0], 300, threading.Lock(), groups)


def log_lines(root: Path) -> list[str]:
    log = root / "log.txt"
    lines = log.read_text().splitlines() if log.exists() else []
    log.unlink(missing_ok=True)
    return lines


def test_a_shard_runs_only_the_files_pytest_collects_for_it(
    runner: ModuleType, shard_project: Path
) -> None:
    assert run_part(runner, "1") is False
    assert {line for line in log_lines(shard_project) if line.startswith("ran ")} == {
        "ran tests/test_a.py"
    }
    assert run_part(runner, "2") is False
    assert {line for line in log_lines(shard_project) if line.startswith("ran ")} == {
        "ran tests/test_b.py",
        "ran tests/check_c.py",
    }


def test_a_shard_keeps_its_reports_apart_and_skips_the_coverage_minimum(
    runner: ModuleType, shard_project: Path
) -> None:
    assert run_part(runner, "1") is False
    kept = shard_project / "coverage/shards/1"
    assert sorted(path.name for path in kept.iterdir()) == [
        "c.json",
        "j.xml",
        "shard-files.txt",
    ]
    assert (kept / "shard-files.txt").read_text() == "tests/test_a.py\n"
    assert not (shard_project / "j.xml").exists()
    assert not (shard_project / "c.json").exists()
    assert runner.run_gate(
        {"path": ".", **PACKAGE, "checks": [shard_gate(None)]},
        shard_gate(None),
        300,
        threading.Lock(),
    )


def test_an_empty_shard_starts_no_pytest(
    runner: ModuleType, shard_project: Path
) -> None:
    assert run_part(runner, "4", 4) is False
    assert log_lines(shard_project) == ["collect"]
    kept = shard_project / "coverage/shards/4"
    assert [path.name for path in kept.iterdir()] == ["shard-files.txt"]
    assert (kept / "shard-files.txt").read_text() == ""
    assert not (shard_project / "j.xml").exists()


def test_shard_time_does_not_shorten_the_full_gate_limit(
    runner: ModuleType, shard_project: Path
) -> None:
    assert run_part(runner, "2") is False
    times = json.loads((shard_project / ".git/hard-eng-gate-times.json").read_text())
    assert list(times) == ["./tests@shard"]
    assert gate_limit(shard_project, "./tests", 900) == 900

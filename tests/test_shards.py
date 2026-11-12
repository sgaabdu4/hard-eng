"""CI test shards: the field, the split, the shard run and the report merge."""

import json
import os
import shutil
import subprocess
import sys
import threading
from argparse import ArgumentParser
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import cast

import gate_config
import pytest
from ci_jobs import add_shard_option
from conftest import SOURCE, commit, configure, gate, git
from coverage_sources import python_coverage
from gate_config import Gate, Group, affected_groups, validate_group
from gate_times import gate_limit
from process_group import passed_minutes
from reports import completed_tests, junit_root, reported_skips
from shards import (
    merge_coverage,
    merge_junit,
    part_command,
    require_no_path,
    shard_groups,
    split,
)
from test_plan_acceptance import UNPROVED, VALUE_ID


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


def provisioned_nothing(*_arguments: object) -> None:
    return None


def test_a_local_shard_run_records_no_full_pass(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr(runner, "provision_tools", provisioned_nothing)
    (tmp_path / ".gitignore").write_text(".hard-eng/\ncoverage/\n")
    configure(tmp_path, [gate("lint", "pass")])
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    git(tmp_path, "config", "user.name", "Fixture")
    base = commit(tmp_path, "base")
    (tmp_path / "app.py").write_text("value = 1\n")
    head = commit(tmp_path, "change")
    assert runner.check(base=base, shard="rest") == 0
    assert passed_minutes(tmp_path, head, base) is None


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
    groups = [package("."), pytest_group("api", [cast(Gate, check)])]
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


def pytest_group(path: str, checks: list[Gate]) -> Group:
    return {"path": path, "language": "python", "sources": ["lib.py"], "checks": checks}


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


def project_groups(count: int | None) -> list[Group]:
    child = pytest_group("tests/child", [shard_gate(None)])
    return [pytest_group(".", [shard_gate(count)]), child]


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
        pytest_group(".", [shard_gate(None)]),
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


def cov_json(executed: set[int], total: int = 10) -> str:
    rest = sorted(set(range(1, total + 1)) - executed)
    summary = {"covered_lines": len(executed), "num_statements": total}
    entry = {"executed_lines": sorted(executed), "missing_lines": rest}
    return json.dumps({"files": {"lib.py": {**entry, "summary": summary}}})


def junit_text(*cases: str, skipped: tuple[str, ...] = ()) -> str:
    body = "".join(
        f'<testcase name="{name}">{"<skipped/>" if name in skipped else ""}</testcase>'
        for name in cases
    )
    return f"<testsuite>{body}</testsuite>"


def keep_shard(
    root: Path,
    number: int,
    path: str,
    files: list[str],
    reports: tuple[str, str] | None,
) -> None:
    folder = root / "coverage/shards" / str(number) / path
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "shard-files.txt").write_text("".join(f"{name}\n" for name in files))
    if reports:
        (folder / "j.xml").write_text(reports[0])
        (folder / "c.json").write_text(reports[1])


def merge_group(path: str, count: int) -> list[Group]:
    check = suite(count)
    check["command"] = [sys.executable, "-m", "pytest"]
    return [pytest_group(path, [check])]


def serve(groups: list[Group]) -> Callable[..., list[Group]]:
    def load_groups(*_arguments: object, **_options: object) -> list[Group]:
        return groups

    return load_groups


def run_merge(runner: ModuleType, groups: list[Group]) -> bool:
    chosen = shard_groups(groups, "merge")[0]
    return runner.run_gate(chosen, chosen["checks"][0], 60, threading.Lock(), groups)


@pytest.fixture
def merge_project(runner: ModuleType) -> Path:
    (runner.ROOT / "lib.py").write_text("value = 1\n")
    (runner.ROOT / "api").mkdir()
    (runner.ROOT / "api/lib.py").write_text("value = 1\n")
    return runner.ROOT


@pytest.mark.parametrize(
    ("first", "second", "failed"),
    [({1, 2, 3, 4}, {4, 5, 6, 7, 8}, False), ({1, 2, 3}, {2, 3, 4, 5}, True)],
)
def test_the_gate_job_applies_the_coverage_minimum_to_the_merged_report(
    runner: ModuleType,
    merge_project: Path,
    capsys: pytest.CaptureFixture[str],
    first: set[int],
    second: set[int],
    failed: bool,
) -> None:
    keep_shard(merge_project, 1, ".", ["a"], (junit_text("one"), cov_json(first)))
    keep_shard(merge_project, 2, ".", ["b"], (junit_text("two"), cov_json(second)))
    assert run_merge(runner, merge_group(".", 2)) is failed
    assert ("HE-COVERAGE-MIN" in capsys.readouterr().out) is failed


@pytest.mark.parametrize("path", [".", "api"])
@pytest.mark.parametrize("lost", ["folder", "junit"])
def test_the_gate_job_refuses_missing_shard_reports(
    runner: ModuleType,
    merge_project: Path,
    capsys: pytest.CaptureFixture[str],
    path: str,
    lost: str,
) -> None:
    reports = (junit_text("one"), cov_json({1, 2, 3, 4, 5, 6, 7, 8}))
    keep_shard(merge_project, 1, path, ["a"], reports)
    if lost == "junit":
        keep_shard(merge_project, 2, path, ["b"], reports)
        (merge_project / "coverage/shards/2" / path / "j.xml").unlink()
    count = 2 if lost == "junit" else 3
    assert run_merge(runner, merge_group(path, count)) is True
    assert (
        f"Shard 2 of {count} for {path}/tests sent no reports. List shards 1 to "
        f"{count} in the tests job of .github/workflows/hard-eng.yml (setup writes it), "
        "then rerun all jobs of the workflow." in capsys.readouterr().out
    )


def test_the_gate_job_accepts_a_shard_that_had_no_files(
    runner: ModuleType, merge_project: Path
) -> None:
    reports = (junit_text("one"), cov_json({1, 2, 3, 4, 5, 6, 7, 8}))
    keep_shard(merge_project, 1, ".", ["a"], reports)
    keep_shard(merge_project, 2, ".", [], None)
    keep_shard(merge_project, 4, ".", ["z"], None)
    assert run_merge(runner, merge_group(".", 2)) is False


def test_merged_junit_holds_every_shard_case_and_skip(tmp_path: Path) -> None:
    first, second, merged = tmp_path / "1.xml", tmp_path / "2.xml", tmp_path / "m.xml"
    first.write_text(junit_text("test_a[x]", "test_b", skipped=("test_b",)))
    second.write_text(
        f"<testsuites>{junit_text('test_c', 'test_d', skipped=('test_d',))}</testsuites>"
    )
    merge_junit([first, second], merged)
    root = junit_root(merged)
    assert [suite.tag for suite in root] == ["testsuite", "testsuite"]
    assert len(list(root.iter("testcase"))) == 4
    assert completed_tests(merged, "python-tests") == 2
    assert reported_skips(merged, "python-tests") == {"test_b", "test_d"}


def test_the_gate_job_fails_skipped_plan_acceptance_tests(
    runner: ModuleType,
    merge_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (merge_project / "lib.py").write_text(f"value = {VALUE_ID!r}\n")
    (merge_project / "tests").mkdir()
    (merge_project / "tests/test_main.py").write_text(
        f'def test_value() -> None:\n    """{VALUE_ID}: value kept."""\n'
    )
    (merge_project / "docs").mkdir()
    (merge_project / "docs/requirements.md").write_text(
        f"## {VALUE_ID} \u2014 Value\n\nThe value is kept.\n\nProof: check\n"
    )
    plan = merge_project / "PLAN.md"
    plan.write_text(
        plan.read_text().replace(UNPROVED, f"- [x] Value kept \u2192 {VALUE_ID}.")
    )
    keep_shard(
        merge_project,
        1,
        ".",
        ["a"],
        (junit_text("test_other"), cov_json({1, 2, 3, 4, 5, 6, 7, 8})),
    )
    reports = (
        junit_text("test_value", skipped=("test_value",)),
        cov_json({1, 2, 3, 4, 5, 6, 7, 8}),
    )
    keep_shard(merge_project, 2, ".", ["tests/test_main.py"], reports)
    configure(merge_project, [])
    groups = merge_group(".", 2)
    monkeypatch.setattr(gate_config, "load_groups", serve(groups))
    assert runner.check(base="0" * 40, plan_stage="Complete", shard="merge") == 1
    assert "skipped: test_value" in capsys.readouterr().out


def test_the_gate_job_without_a_shard_proof_still_needs_each_report(
    runner: ModuleType,
    merge_project: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    reports = (junit_text("one"), cov_json({1, 2, 3, 4, 5, 6, 7, 8}))
    keep_shard(merge_project, 1, ".", ["a"], reports)
    (merge_project / "coverage/shards/1/ran.txt").write_text("ok\n")
    configure(merge_project, [])
    monkeypatch.setattr(gate_config, "load_groups", serve(merge_group(".", 2)))
    assert runner.check(base="0" * 40, plan_stage="Complete", shard="merge") == 1
    assert "Shard 2 of 2 for ./tests sent no reports" in capsys.readouterr().out


PICK = "def pick(flag):\n    if flag:\n        return 1\n    return 2\n"


def run_pytest(root: Path, report: str, *files: str) -> None:
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("COV_CORE_", "COVERAGE_"))
    }
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "no:cacheprovider",
            "--cov",
            "--cov-branch",
            f"--cov-report=json:{report}",
            *files,
        ],
        cwd=root,
        env=environment,
        check=True,
        capture_output=True,
    )


def test_merged_shard_coverage_equals_one_full_run(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\npythonpath = ["."]\n'
    )
    (tmp_path / "pkg/lib.py").write_text(PICK)
    (tmp_path / "pkg/extra.py").write_text("def extra():\n    return 3\n")
    (tmp_path / "tests/test_a.py").write_text(
        "from pkg.lib import pick\n\n\ndef test_a():\n    assert pick(True) == 1\n"
    )
    (tmp_path / "tests/test_b.py").write_text(
        "from pkg import extra\nfrom pkg.lib import pick\n\n\n"
        "def test_b():\n    assert pick(False) == 2\n    assert extra.extra() == 3\n"
    )
    run_pytest(tmp_path, "one.json", "tests/test_a.py")
    run_pytest(tmp_path, "two.json", "tests/test_b.py")
    run_pytest(tmp_path, "full.json", "tests/test_a.py", "tests/test_b.py")
    parts = [
        json.loads((tmp_path / name).read_text()) for name in ("one.json", "two.json")
    ]
    (tmp_path / "merged.json").write_text(json.dumps(merge_coverage(parts)))
    merged = json.loads((tmp_path / "merged.json").read_text())
    full = json.loads((tmp_path / "full.json").read_text())
    assert set(merged["files"]) == set(full["files"])
    assert "pkg/extra.py" not in parts[0]["files"]
    keys = ("executed_lines", "missing_lines", "executed_branches", "missing_branches")
    counts = (
        "covered_lines",
        "num_statements",
        "num_branches",
        "covered_branches",
        "missing_branches",
    )
    for name, entry in full["files"].items():
        assert {key: merged["files"][name][key] for key in keys} == {
            key: entry[key] for key in keys
        }
        assert {key: merged["files"][name]["summary"][key] for key in counts} == {
            key: entry["summary"][key] for key in counts
        }
    assert python_coverage(tmp_path / "merged.json", tmp_path) == python_coverage(
        tmp_path / "full.json", tmp_path
    )
    assert merged["files"]["pkg/lib.py"]["summary"]["num_branches"] == 2


BARE_MERGE = """
import importlib.util, json, sys
from pathlib import Path
hooks, root, base, groups = sys.argv[1:5]
sys.modules["yaml"] = None
sys.path.insert(0, hooks)
import gate_config
gate_config.load_groups = lambda *_, **__: json.loads(Path(groups).read_text())
spec = importlib.util.spec_from_file_location("runner", hooks + "/hard-eng.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
runner.ROOT = Path(root)
sys.argv = ["hard-eng.py", "check", "--base", base, "--shard", "merge"]
raise SystemExit(runner.main())
"""


def test_the_gate_job_runs_with_bare_python(
    runner: ModuleType, merge_project: Path, tmp_path: Path
) -> None:
    reports = (junit_text("one"), cov_json({1, 2, 3, 4, 5, 6, 7, 8, 9}))
    keep_shard(merge_project, 1, ".", ["a"], reports)
    keep_shard(merge_project, 2, ".", [], None)
    configure(merge_project, [])
    groups = tmp_path / "groups.json"
    groups.write_text(json.dumps(merge_group(".", 2)))
    tools = tmp_path / "tools"
    tools.mkdir()
    (tools / "git").symlink_to(shutil.which("git") or "git")
    done = subprocess.run(
        [
            sys.executable,
            "-c",
            BARE_MERGE,
            str(SOURCE / ".hooks"),
            str(merge_project),
            "0" * 40,
            str(groups),
        ],
        cwd=merge_project,
        env={"PATH": str(tools), "HOME": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr


def test_the_gate_job_needs_nothing_when_the_tests_package_is_unaffected(
    runner: ModuleType, repository: Path
) -> None:
    (repository / "api").mkdir()
    (repository / "web").mkdir()
    (repository / "web/page.py").write_text("value = 1\n")
    packages: list[Group] = [
        {**merge_group("api", 3)[0], "depends_on": []},
        {"path": "web", "checks": [], "depends_on": []},
    ]
    chosen = affected_groups(
        repository, [*packages, {"path": ".", "checks": []}], "HEAD"
    )
    assert [group["path"] for group in chosen] == ["web", "."]
    assert shard_groups(chosen, "merge") == []


@pytest.mark.parametrize(("shard", "provisioned"), [("merge", False), ("rest", True)])
def test_only_the_gate_job_skips_tool_setup(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    shard: str,
    provisioned: bool,
) -> None:
    started: list[str] = []
    configure(runner.ROOT, [])

    def provision(*_arguments: object) -> None:
        started.append(shard)

    monkeypatch.setattr(gate_config, "load_groups", serve([]))
    monkeypatch.setattr(runner, "provision_tools", provision)
    assert runner.check(base="0" * 40, plan_stage="Complete", shard=shard) == 0
    assert bool(started) is provisioned


def test_two_sharded_gates_in_one_package_are_refused(
    runner: ModuleType, shard_project: Path
) -> None:
    group = pytest_group(".", [shard_gate(2), shard_gate(3, "more")])
    with pytest.raises(
        ValueError,
        match=r'^\.: only one gate of a package can hold "shards"\. Remove "shards" from all but one tests gate in hard-eng\.gates\.json\.$',
    ):
        shard_groups([group], "rest")


def run_command(runner: ModuleType, command: list[str]) -> bool:
    check = {**shard_gate(2), "command": command}
    group = pytest_group(".", [cast(Gate, check)])
    chosen = shard_groups([group], "1")[0]
    return runner.run_gate(chosen, chosen["checks"][0], 300, threading.Lock(), [group])


def test_a_path_in_the_gate_command_is_refused_because_every_shard_would_run_it_whole(
    runner: ModuleType, shard_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_command(runner, [sys.executable, "-m", "pytest", "tests"]) is True
    assert (
        './tests: the command names the path "tests", so every shard would run it '
        "whole. Remove the path from the command and list it in testpaths in the "
        "pytest settings. If it is the value of an option, write it as "
        "--option=value (for example --cov=src)." in capsys.readouterr().out
    )
    assert log_lines(shard_project) == []


def test_an_option_value_that_names_a_folder_gets_the_equals_form_in_the_refusal(
    shard_project: Path,
) -> None:
    (shard_project / "src").mkdir()
    group = pytest_group(".", [shard_gate(2)])
    command = [sys.executable, "-m", "pytest"]
    require_no_path(shard_project, group, group["checks"][0], [*command, "--cov=src"])
    with pytest.raises(
        ValueError,
        match=r"If it is the value of an option, write it as --option=value \(for example --cov=src\)\.$",
    ):
        require_no_path(
            shard_project, group, group["checks"][0], [*command, "--cov", "src"]
        )


def test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact(
    runner: ModuleType, shard_project: Path
) -> None:
    settings = shard_project / "pyproject.toml"
    settings.write_text(settings.read_text() + 'addopts = "-n 2"\n')
    assert run_part(runner, "1") is False
    assert {line for line in log_lines(shard_project) if line.startswith("ran ")} == {
        "ran tests/test_a.py"
    }
    kept = shard_project / "coverage/shards/1/shard-files.txt"
    assert kept.read_text() == "tests/test_a.py\n"


@pytest.mark.parametrize("verbose", ["-v", "-vv"])
def test_a_verbose_setting_in_the_pytest_settings_leaves_the_shard_files_exact(
    runner: ModuleType, shard_project: Path, verbose: str
) -> None:
    settings = shard_project / "pyproject.toml"
    settings.write_text(settings.read_text() + f'addopts = "{verbose}"\n')
    assert run_part(runner, "1") is False
    assert {line for line in log_lines(shard_project) if line.startswith("ran ")} == {
        "ran tests/test_a.py"
    }


def test_a_listing_that_names_no_file_is_refused(
    runner: ModuleType, shard_project: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run_command(runner, [sys.executable, "-c", "pass", "pytest"]) is True
    assert "pytest could not list the tests of this shard" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("extra", "setting", "held"),
    [
        (["--cov"], "", True),
        (["--cov=lib", "--cov-branch"], "", True),
        ([], "", False),
        ([], 'addopts = "--cov=lib"\n', True),
        ([], '# addopts = "--cov=lib"\n', False),
    ],
)
def test_a_shard_does_not_apply_the_coverage_minimum_of_the_project(
    runner: ModuleType, shard_project: Path, extra: list[str], setting: str, held: bool
) -> None:
    with (shard_project / "pyproject.toml").open("a") as settings:
        settings.write(setting)
    command = [sys.executable, "-m", "pytest", "--junitxml=j.xml", *extra]
    check = {**shard_gate(2), "command": command}
    group = pytest_group(".", [cast(Gate, check)])
    chosen = shard_groups([group], "1")[0]
    gate_1 = chosen["checks"][0]
    run, _ = part_command(shard_project, chosen, gate_1, command, None, 300)
    assert ("--cov-fail-under=0" in run) is held
    assert run[-1] == str(shard_project / "tests/test_a.py")


@pytest.mark.parametrize(
    ("name", "text", "refused"),
    [
        ("pyproject.toml", "[tool.coverage.report]\nfail_under = 80\n", False),
        ("pyproject.toml", "[tool.coverage.report]\nfail_under = 81\n", True),
        (".coveragerc", "[report]\nfail_under = 85\n", True),
        ("pytest.ini", "[pytest]\naddopts = --cov-fail-under=90\n", True),
    ],
)
def test_the_gate_job_applies_the_coverage_minimum_of_the_project_to_the_merged_total(
    runner: ModuleType,
    merge_project: Path,
    capsys: pytest.CaptureFixture[str],
    name: str,
    text: str,
    refused: bool,
) -> None:
    (merge_project / name).write_text(text)
    keep_shard(
        merge_project, 1, ".", ["a"], (junit_text("one"), cov_json({1, 2, 3, 4}))
    )
    keep_shard(
        merge_project, 2, ".", ["b"], (junit_text("two"), cov_json({4, 5, 6, 7, 8}))
    )
    assert run_merge(runner, merge_group(".", 2)) is refused
    output = capsys.readouterr().out
    if not refused:
        assert "below the minimum" not in output
        return
    minimum = text.split("=")[-1].strip()
    assert (
        f"./tests: the merged coverage total is 80%, below the minimum of {minimum}% "
        in output
    )
    assert " sets. Add tests, or lower that minimum." in output
    assert name in output

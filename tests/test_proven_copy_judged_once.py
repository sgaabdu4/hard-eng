"""A folder that Hard Eng proves to be a byte copy of a package that another gate group judges in full is judged once, at its source."""

import copy
import json
import shutil
import subprocess
from contextlib import nullcontext
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import TextIO

import decimate_resolved
import pytest
import yaml
from conftest import commit
from dart_boundaries import DART_TYPING
from gate_config import Gate, Group
from test_reports import REPORTS
from test_strict_refusals import project

OPTIONS = yaml.safe_dump(DART_TYPING)
SOURCE_FILES = {
    "pubspec.yaml": "name: lib_a\nversion: 1.0.0\n",
    "analysis_options.yaml": OPTIONS,
    "lib/a.dart": "int a() => 1;\n",
    "lib/src/b.dart": "int b() => 2;\n",
}
MARK = "functions/*/shared_copy/** linguist-generated\n"
NESTED = "A nested Dart settings file must include the package settings"
TYPES: Gate = {"name": "types", "role": "types", "command": ["dart", "analyze", "."]}
TESTS: Gate = {
    "name": "tests",
    "role": "tests",
    "command": ["dart", "test"],
    "report": {
        "type": "dart-tests",
        "tests": "coverage/tests.json",
        "coverage": "coverage/lcov.info",
    },
}
SCAN: Gate = {
    "name": "dead-code",
    "role": "dead-code-duplicates",
    "command": [
        "dart-decimate",
        "check",
        ".",
        "--threshold",
        "0",
        "--format",
        "json",
        "--strict",
    ],
    "report": {
        "type": "dart-decimate",
        "path": "coverage/decimate.json",
        "stdout": True,
    },
}
FINDING = {
    "rule_id": "dart-decimate/high-crap-score",
    "message": "a has CRAP score 56 with 0% line coverage",
    "line": 1,
}


def source_group(*gates: Gate) -> Group:
    return {
        "path": "packages/lib_a",
        "language": "dart",
        "sources": ["lib"],
        "checks": [copy.deepcopy(gate) for gate in gates],
    }


def function_group() -> Group:
    return {
        "path": "functions/f",
        "language": "dart",
        "sources": ["lib", "shared_copy"],
        "checks": [copy.deepcopy(TYPES), copy.deepcopy(SCAN)],
    }


def full_source() -> Group:
    return source_group(TYPES, TESTS, SCAN)


def packages_of(cwd: Path, command: list[str]) -> str:
    """The tool's package listing: each folder with a pubspec, narrowed by the `--workspace` roots."""
    chosen = [command[i + 1] for i, word in enumerate(command) if word == "--workspace"]
    roots = sorted(
        pubspec.parent.relative_to(cwd).as_posix()
        for pubspec in cwd.rglob("pubspec.yaml")
        if ".dart_tool" not in pubspec.parts
    )
    return json.dumps(
        {
            "workspaces": [
                {"root": "" if root == "." else root}
                for root in roots
                if not chosen or root in chosen or (root == "." and "." in chosen)
            ]
        }
    )


def decimate_settings(monkeypatch: pytest.MonkeyPatch, max_crap: int = 30) -> None:
    real = subprocess.check_output

    def settings(
        command: list[str],
        cwd: Path,
        text: bool,
        timeout: float | None = None,
        stderr: int | None = None,
    ) -> str:
        if "dart-decimate" not in " ".join(command):
            return str(real(command, cwd=cwd, text=text))
        if "workspaces" in command:
            return packages_of(cwd, command)
        own = cwd.name == "f"
        rules = [
            {"from": "lib/main.dart", "disallow": "shared_copy"}
            if own
            else {"from": "lib/a.dart", "disallow": "lib/src"}
        ]
        health = {"max_crap": max_crap}
        return json.dumps({"config": {"boundaries": rules, "health": health}})

    def printed(
        directory: Path, _config: str | None, _timeout: float
    ) -> dict[str, object]:
        fresh = directory.name.startswith("hard-eng-decimate-")
        return {"health": {"max_crap": 30 if fresh else max_crap}}

    monkeypatch.setattr(subprocess, "check_output", settings)
    monkeypatch.setattr(decimate_resolved, "printed_config", printed)


def build(
    tmp_path: Path,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    mark: str = MARK,
    changed: dict[str, str] | None = None,
    source_options: str = OPTIONS,
    shared_name: str = "lib_a",
) -> Path:
    source = {
        **SOURCE_FILES,
        "pubspec.yaml": f"name: {shared_name}\nversion: 1.0.0\n",
        "analysis_options.yaml": source_options,
    }
    files = {f"packages/lib_a/{name}": text for name, text in source.items()}
    files |= {
        f"functions/f/shared_copy/{name}": text
        for name, text in {**source, **(changed or {})}.items()
    }
    files |= {
        "functions/f/pubspec.yaml": "name: f\nversion: 1.0.0\n",
        "functions/f/analysis_options.yaml": OPTIONS,
        "functions/f/lib/main.dart": "void main() {}\n",
        ".gitattributes": mark,
    }
    root = project(tmp_path, files)
    runner.__dict__["ROOT"] = root
    decimate_settings(monkeypatch)
    return root


def refused(runner: ModuleType, group: Group, groups: list[Group]) -> str | None:
    try:
        runner.prepare_command(group, group["checks"][0], 60, groups)
    except ValueError as error:
        return str(error)
    return None


def test_a_proven_copy_with_a_source_group_skips_the_nested_settings_rule(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    assert refused(runner, group, [group, full_source()]) is None


@pytest.mark.parametrize(
    "gates",
    [
        pytest.param((TESTS, SCAN), id="no types gate"),
        pytest.param((TYPES, SCAN), id="no tests with coverage"),
        pytest.param((TYPES, TESTS), id="no Dart Decimate gate"),
        pytest.param(
            (
                TYPES,
                TESTS,
                {
                    **SCAN,
                    "command": [*SCAN["command"][:-1], "--no-boundary-violations"],
                },
            ),
            id="a Dart Decimate gate that is not the strict form",
        ),
        pytest.param(
            (
                TYPES,
                {**TESTS, "report": {"type": "dart-tests", "tests": "coverage/t.json"}},
                SCAN,
            ),
            id="tests without a coverage report",
        ),
    ],
)
def test_a_copy_is_judged_in_place_unless_every_condition_holds(
    tmp_path: Path,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    gates: tuple[Gate, ...],
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    assert NESTED in (refused(runner, group, [group, source_group(*gates)]) or "")
    assert NESTED in (refused(runner, group, [group]) or "")


def test_a_copy_with_one_changed_file_or_no_mark_is_judged_in_place(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    group = function_group()
    groups = [group, full_source()]
    build(tmp_path, runner, monkeypatch, changed={"lib/a.dart": "int a() => 9;\n"})
    assert NESTED in (refused(runner, group, groups) or "")
    build(tmp_path / "other", runner, monkeypatch, mark="")
    assert NESTED in (refused(runner, group, groups) or "")


def test_an_unmarked_nested_settings_file_without_the_include_is_still_refused(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build(tmp_path, runner, monkeypatch)
    (root / "functions/f/lib/tool").mkdir()
    (root / "functions/f/lib/tool/analysis_options.yaml").write_text(OPTIONS)
    commit(root, "a nested file that is no copy")
    group = function_group()
    message = refused(runner, group, [group, full_source()]) or ""
    assert NESTED in message
    assert "functions/f/lib/tool/analysis_options.yaml" in message


@pytest.mark.parametrize(
    ("source_options", "max_crap"),
    [
        pytest.param("analyzer: {}\n", 30, id="strict typing settings fail"),
        pytest.param(OPTIONS, 31, id="the CRAP limit is above 30"),
    ],
)
def test_a_source_that_fails_its_own_settings_does_not_excuse_its_copy(
    tmp_path: Path,
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    source_options: str,
    max_crap: int,
) -> None:
    build(tmp_path, runner, monkeypatch, source_options=source_options)
    decimate_settings(monkeypatch, max_crap)
    group = function_group()
    assert NESTED in (refused(runner, group, [group, full_source()]) or "")


def test_a_source_with_a_raised_limit_in_its_settings_does_not_excuse_its_copy(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """HE-NO-SWITCH-OFF: the settings judge of the source group runs before its copy is left out."""
    build(tmp_path, runner, monkeypatch)

    def printed(
        directory: Path, _config: str | None, _timeout: float
    ) -> dict[str, object]:
        return {"health": {"max_cognitive": 99 if directory.name == "lib_a" else 15}}

    monkeypatch.setattr(decimate_resolved, "printed_config", printed)
    group = function_group()
    assert NESTED in (refused(runner, group, [group, full_source()]) or "")


def test_a_run_with_only_the_function_group_still_finds_the_source(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    runner.CONFIGURED[:] = [group, full_source()]
    try:
        assert refused(runner, group, [group]) is None
    finally:
        runner.CONFIGURED.clear()


def scan_run(
    runner: ModuleType,
    monkeypatch: pytest.MonkeyPatch,
    groups: list[Group],
    outside: bool = False,
) -> tuple[bool, list[str], str]:
    """The tool is faked as it behaves: `--workspace` leaves the other packages out of its report."""
    commands: list[list[str]] = []

    def decimate(
        _group: Group,
        _gate: Gate,
        command: list[str],
        _directory: Path,
        _timeout: float,
        stdout: TextIO,
        _stderr: TextIO,
    ) -> SimpleNamespace:
        commands.append(command)
        report = json.loads(REPORTS["dart-decimate"])
        found = [{**FINDING, "path": "lib/main.dart"}] if outside else []
        if "--workspace" not in command:
            found.append({**FINDING, "path": "shared_copy/lib/a.dart"})
        report["findings"] = found
        report["verdict"] = "fail" if found else "pass"
        stdout.write(json.dumps(report))
        return SimpleNamespace(returncode=1 if found else 0)

    monkeypatch.setattr(runner, "run_projects", decimate)

    def unjudged(*_arguments: object) -> None:
        return None

    monkeypatch.setattr("resolved_settings.judge_before_run", unjudged)
    group = groups[0]
    failed = runner.run_limited_gate(
        group, group["checks"][1], 60, nullcontext(), groups
    )
    scoped = [
        command[index + 1]
        for command in commands
        for index, word in enumerate(command)
        if word == "--workspace"
    ]
    return failed, scoped, " ".join(commands[0])


def test_the_decimate_gate_leaves_out_a_proven_copy(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = build(tmp_path, runner, monkeypatch)
    (root / "functions/f/other").mkdir()
    (root / "functions/f/other/pubspec.yaml").write_text("name: other\n")
    commit(root, "another package in the function")
    group = function_group()
    failed, scoped, _ = scan_run(runner, monkeypatch, [group, full_source()])
    assert (failed, scoped) == (False, [".", "other"])


def test_findings_outside_a_copy_still_fail_the_gate(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    failed, scoped, _ = scan_run(runner, monkeypatch, [group, full_source()], True)
    assert (failed, scoped) == (True, ["."])


def test_a_copy_that_is_not_proven_keeps_the_whole_scan(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch, changed={"lib/a.dart": "int a() => 9;\n"})
    group = function_group()
    failed, scoped, _ = scan_run(runner, monkeypatch, [group, full_source()])
    assert (failed, scoped) == (True, [])


def test_a_copy_without_a_source_group_keeps_the_whole_scan(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    failed, scoped, _ = scan_run(runner, monkeypatch, [group])
    assert (failed, scoped) == (True, [])


def need_decimate() -> None:
    if shutil.which("dart-decimate") is None:
        from tool_setup import PACKAGES, provision_batch

        provision_batch([PACKAGES["dart-decimate"] + "@latest"], 900)


BRANCHY = """int branchy(int a) {
  if (a > 1) { return 1; } else if (a > 2) { return 2; } else if (a > 3) { return 3; }
  else if (a > 4) { return 4; } else if (a > 5) { return 5; } else if (a > 6) { return 6; }
  return 0;
}
"""


@pytest.mark.parametrize(
    ("function_name", "other_name", "other_folder", "inner"),
    [
        pytest.param("'f'", "other # helper", "other", "", id="quoted and commented"),
        pytest.param("f", "example", "example", "example", id="same name in the copy"),
    ],
)
def test_the_real_tool_still_reports_the_code_of_the_function_and_its_other_packages(
    tmp_path: Path,
    runner: ModuleType,
    function_name: str,
    other_name: str,
    other_folder: str,
    inner: str,
) -> None:
    """A package name read from its text is no selector, and a copied package that shares a name with a kept one must not fail the scan: the scan is scoped by package folder."""
    need_decimate()
    source = {
        **SOURCE_FILES,
        "lib/a.dart": BRANCHY,
        ".dart-decimaterc.json": json.dumps(
            {
                "boundaries": [{"from": "lib/a.dart", "disallow": "lib/src"}],
                "health": {"max_crap": 30},
            }
        ),
    }
    if inner:
        source[f"{inner}/pubspec.yaml"] = f"name: {inner}\nversion: 1.0.0\n"
    files = {f"packages/lib_a/{name}": text for name, text in source.items()}
    files |= {f"functions/f/shared_copy/{name}": text for name, text in source.items()}
    sdk = "environment:\n  sdk: ^3.0.0\n"
    files |= {
        "functions/f/pubspec.yaml": f"name: {function_name}\nversion: 1.0.0\n{sdk}",
        "functions/f/analysis_options.yaml": OPTIONS,
        "functions/f/lib/main.dart": "void main() {}\n",
        "functions/f/lib/dead.dart": BRANCHY,
        f"functions/f/{other_folder}/pubspec.yaml": f"name: {other_name}\nversion: 1.0.0\n{sdk}",
        f"functions/f/{other_folder}/lib/src/unused.dart": "int o() => 1;\n",
        "functions/f/.dart-decimaterc.json": json.dumps(
            {
                "boundaries": [{"from": "lib/main.dart", "disallow": "shared_copy"}],
                "health": {"max_crap": 30},
            }
        ),
        ".gitattributes": MARK,
    }
    root = project(tmp_path, files)
    runner.__dict__["ROOT"] = root
    (root / "functions/f/coverage").mkdir()
    (root / "functions/f/coverage/lcov.info").write_text(
        "SF:lib/main.dart\nDA:1,1\nend_of_record\n"
    )
    group = function_group()
    groups = [group, full_source()]
    assert runner.run_limited_gate(
        group, group["checks"][1], 600, nullcontext(), groups
    )
    report = json.loads((root / "functions/f/coverage/decimate.json").read_text())
    paths = {finding["path"] for finding in report["findings"]}
    assert {"lib/dead.dart", f"{other_folder}/lib/src/unused.dart"} <= paths
    assert not any(path.startswith("shared_copy/") for path in paths)


def test_a_project_with_no_mark_under_the_group_never_asks_git_about_copies(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every Dart types gate runs this, the quick checks of the hooks too: with no folder mark below the group it must read nothing."""
    import generated_marks
    from dart_boundaries import typing_scope

    def asked(*_arguments: object) -> object:
        raise AssertionError("the proof of a copy was asked for")

    group = function_group()
    for mark in (
        "",
        "other/*/elsewhere/** linguist-generated\n",
        "*.g.dart linguist-generated\n",
    ):
        build(tmp_path / str(len(mark)), runner, monkeypatch, mark=mark)
        monkeypatch.setattr(generated_marks, "claims", asked)
        monkeypatch.setattr(generated_marks, "proven_copy", asked)
        assert typing_scope(runner.ROOT, group, [group], 60)[1] == frozenset()


def test_the_settings_of_a_source_are_judged_once_for_all_its_copies(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    import dart_boundaries

    build(tmp_path, runner, monkeypatch)
    calls: list[Path] = []
    real = dart_boundaries.validate_dart_boundaries

    def counted(command: list[str], directory: Path, timeout: float) -> None:
        calls.append(directory)
        real(command, directory, timeout)

    monkeypatch.setattr(dart_boundaries, "validate_dart_boundaries", counted)
    group = function_group()
    groups = [group, full_source()]
    for _ in range(3):
        assert dart_boundaries.judged_copies(runner.ROOT, group, groups, 60)
    assert calls == [runner.ROOT / "packages/lib_a"]


def test_a_quick_check_does_not_start_the_tool_to_judge_a_source(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hooks add no time: the quick check skips the copy on the gates of the source group, and the full check starts the tool."""
    import dart_boundaries

    build(tmp_path, runner, monkeypatch)

    def started(*_arguments: object) -> None:
        raise AssertionError("the quick check started Dart Decimate")

    monkeypatch.setattr(dart_boundaries, "validate_dart_boundaries", started)
    monkeypatch.setattr("sys.argv", ["hard-eng.py", "check", "--quick"])
    group = function_group()
    assert dart_boundaries.judged_copies(
        runner.ROOT, group, [group, full_source()], 60
    ) == frozenset({"shared_copy"})


def test_a_package_inside_a_proven_copy_is_left_out_with_it(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A copy of a package that holds an example package keeps it out of the function's scan."""
    root = build(
        tmp_path,
        runner,
        monkeypatch,
        changed=None,
    )
    for folder in ("packages/lib_a", "functions/f/shared_copy"):
        (root / folder / "example").mkdir()
        (root / folder / "example/pubspec.yaml").write_text("name: example\n")
    commit(root, "an example package in the source and its copy")
    group = function_group()
    failed, scoped, _ = scan_run(runner, monkeypatch, [group, full_source()])
    assert (failed, scoped) == (False, ["."])


def test_a_scan_of_dot_slash_leaves_out_a_proven_copy(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    build(tmp_path, runner, monkeypatch)
    group = function_group()
    group["checks"][1]["command"][2] = "./"
    failed, scoped, _ = scan_run(runner, monkeypatch, [group, full_source()])
    assert (failed, scoped) == (False, ["."])


def test_an_attributes_file_without_a_double_star_is_not_parsed_for_copies(
    tmp_path: Path, runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A folder mark ends in `/**`, so a file without `**` needs no parse, and no import of the parser, on a cold hook."""
    import generated_marks
    from dart_boundaries import typing_scope

    def parsed(*_arguments: object) -> list[str]:
        raise AssertionError("the attributes file was parsed")

    build(tmp_path, runner, monkeypatch, mark="*.g.dart linguist-generated\n")
    monkeypatch.setattr(generated_marks, "marks", parsed)
    group = function_group()
    assert typing_scope(runner.ROOT, group, [group], 60)[1] == frozenset()

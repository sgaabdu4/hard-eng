"""A quick check first analyses only the changed Dart files; findings there leave the verdict to the package run."""

import json
import os
import sys
import threading
from pathlib import Path
from types import ModuleType

import agent_hooks
import pytest
from conftest import commit, configure, git
from gate_config import Gate, Group
from gate_schedule import changed_dart
from test_push_check import git_starts

DART = ["dart", "analyze", "--fatal-infos"]
OLD = "error - lib/old.dart:3:1 - old finding\n"
# Stands in for the analyzer: a named file is analysed even when the package run leaves it out.
TOOL = """#!/bin/sh
printf '%s\\n' "$*" >> trace
shift 2
code=0
if [ "$#" -eq 0 ] || [ "$1" = . ]; then
  if [ -e old.txt ]; then cat old.txt; code=3; fi
  set -- $(grep -rl SEEDED lib --include='*.dart' --exclude='*.g.dart')
elif [ -e slow ]; then
  sleep 2
fi
for file in "$@"; do
  if [ -f "$file" ] && grep -q SEEDED "$file"; then
    echo "error - $file:1:1 - seeded"
    code=3
  fi
done
exit "$code"
"""


def analysis(path: str, command: list[str]) -> Group:
    return {
        "path": path,
        "checks": [{"name": "types-lint", "role": "types", "command": command}],
    }


def touch(root: Path, names: list[str]) -> None:
    for name in names:
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text("// fixture\n")


@pytest.mark.parametrize(
    ("path", "tail", "changed", "files"),
    [
        (
            ".",
            [],
            ["lib/a.dart", "test/a_test.dart", "README.md"],
            ["lib/a.dart", "test/a_test.dart"],
        ),
        (".", ["."], ["lib/a.dart"], ["lib/a.dart"]),
        ("app", ["."], ["app/lib/a.dart", "docs/note.md"], ["lib/a.dart"]),
        (".", ["."], ["README.md", "ios/Podfile"], []),
    ],
)
def test_the_first_run_of_a_dart_analysis_gets_the_changed_dart_files_of_its_package(
    tmp_path: Path, path: str, tail: list[str], changed: list[str], files: list[str]
) -> None:
    touch(tmp_path, changed)
    group = analysis(path, [*DART, *tail])
    assert changed_dart(tmp_path, [group], set(changed)) == {
        f"{path}/types-lint": files
    }


@pytest.mark.parametrize(
    ("path", "command", "changed", "absent"),
    [
        (".", DART, None, ""),
        (".", DART, ["lib/a.dart", "lib/gone.dart"], "lib/gone.dart"),
        (".", DART, ["lib/a.dart", "pubspec.yaml"], ""),
        (".", DART, ["lib/a.dart", "pubspec.lock"], ""),
        (".", DART, ["lib/a.dart", "analysis_options.yaml"], ""),
        (".", DART, ["lib/a.dart", "build.yaml"], ""),
        (".", DART, ["lib/a.dart", "lib/l10n/app_en.arb"], ""),
        ("app", DART, ["app/lib/a.dart", "shared/lib/b.dart"], ""),
        ("app", DART, ["application/lib/a.dart"], ""),
        (".", [*DART, "lib"], ["lib/a.dart"], ""),
        (".", ["dart", "analyze", "."], ["lib/a.dart"], ""),
        (".", ["flutter", "analyze", "--fatal-infos"], ["lib/a.dart"], ""),
    ],
)
def test_a_dart_analysis_gets_no_first_run_when_the_changed_files_cannot_stand_for_it(
    tmp_path: Path,
    path: str,
    command: list[str],
    changed: list[str] | None,
    absent: str,
) -> None:
    touch(tmp_path, [name for name in changed or [] if name != absent])
    names = None if changed is None else set(changed)
    assert changed_dart(tmp_path, [analysis(path, command)], names) == {}


def project(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch, *more: dict[str, object]
) -> str:
    """A package with a stand-in analyzer on the path; gives the base commit."""
    root = Path(runner.ROOT)
    monkeypatch.delenv("CI", raising=False)
    (root / "tools").mkdir()
    (root / "tools/dart").write_text(TOOL)
    (root / "tools/dart").chmod(0o755)
    monkeypatch.setenv("PATH", str(root / "tools") + os.pathsep + os.environ["PATH"])
    (root / ".gitignore").write_text("__pycache__/\ntools/\ntrace\nold.txt\nslow\n")
    touch(root, ["lib/a.dart", "lib/b.dart", "lib/made.g.dart"])
    configure(
        root,
        [{"name": "types-lint", "role": "types", "command": [*DART, "."]}, *more],
    )
    git(root, "config", "user.name", "Dart Fixture")
    git(root, "config", "user.email", "dart@example.invalid")
    return commit(root, "start")


def trace(root: Path) -> list[str]:
    lines = (root / "trace").read_text().splitlines()
    (root / "trace").unlink()
    return lines


def test_a_quick_check_passes_the_dart_analysis_on_its_changed_files_alone(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = project(runner, monkeypatch)
    (tmp_path / "lib/a.dart").write_text("// changed\n")

    def starts(command: list[str], *, quick: bool) -> int:
        configure(
            tmp_path, [{"name": "types-lint", "role": "types", "command": command}]
        )
        check = {"base": base, "verify_plan": False, "quick": quick}
        return len(git_starts(lambda: runner.check(**check)))

    starts([*DART, "lib"], quick=True)
    plain = starts([*DART, "lib"], quick=True)
    assert trace(tmp_path) == ["analyze --fatal-infos lib"] * 2
    capsys.readouterr()
    assert starts([*DART, "."], quick=True) == plain
    assert trace(tmp_path) == ["analyze --fatal-infos lib/a.dart"]
    shown = capsys.readouterr().out
    assert "PASS types-lint (changed Dart files only: 1;" in shown
    assert "the full check analyses the package" in shown
    starts([*DART, "."], quick=False)
    assert trace(tmp_path) == ["analyze --fatal-infos ."]
    (tmp_path / "lib/a.dart").write_text("// fixture\n")
    (tmp_path / "notes.md").write_text("A note.\n")
    starts([*DART, "."], quick=True)
    assert not (tmp_path / "trace").exists()
    assert "(changed Dart files only: 0;" in capsys.readouterr().out


def test_a_finding_in_a_changed_file_leaves_the_verdict_to_the_package_run(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    failing: dict[str, object] = {
        "name": "lint",
        "role": "lint",
        "command": ["sh", "-c", "echo lint finding; exit 1"],
    }
    base = project(runner, monkeypatch, failing)
    (tmp_path / "lib/made.g.dart").write_text("// SEEDED\n")
    assert runner.check(base=base, verify_plan=False, quick=True) == 1
    assert trace(tmp_path) == [
        "analyze --fatal-infos lib/made.g.dart",
        "analyze --fatal-infos .",
    ]
    shown = capsys.readouterr().out
    assert "the package analysis decides" in shown
    assert "PASS types-lint (exit 0;" in shown
    assert agent_hooks.FAILED_COMMAND_LINE.findall(shown) == [("lint", ".")]
    assert agent_hooks.failure_summary(shown).startswith("Failed gates: lint\n")
    assert runner.FAILED_GATES == ["./lint"]

    (tmp_path / "lib/a.dart").write_text("// SEEDED\n")
    assert runner.check(base=base, verify_plan=False, quick=True) == 1
    assert trace(tmp_path) == [
        "analyze --fatal-infos lib/a.dart lib/made.g.dart",
        "analyze --fatal-infos .",
    ]
    shown = capsys.readouterr().out
    assert shown.count("error - lib/a.dart:1:1 - seeded") == 1
    assert "lib/made.g.dart:1:1" not in shown
    assert sorted(runner.FAILED_GATES) == ["./lint", "./types-lint"]


def test_the_time_of_the_package_run_leaves_out_the_first_run(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = project(runner, monkeypatch)
    (tmp_path / "lib/made.g.dart").write_text("// SEEDED\n")
    (tmp_path / "slow").touch()
    assert runner.check(base=base, verify_plan=False, quick=True) == 0
    assert len(trace(tmp_path)) == 2
    times = json.loads((tmp_path / ".git/hard-eng-gate-times.json").read_text())
    assert times["./types-lint"] < 2


def test_the_first_run_reads_the_changed_files_as_git_lists_them(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = project(runner, monkeypatch)
    touch(tmp_path, ["lib/d.dart"])
    (tmp_path / "lib/new").mkdir()
    (tmp_path / "lib/new/c.dart").write_text("// SEEDED\n")
    assert runner.check(base=base, verify_plan=False, quick=True) == 1
    assert trace(tmp_path) == [
        "analyze --fatal-infos lib/d.dart lib/new/c.dart",
        "analyze --fatal-infos .",
    ]
    (tmp_path / "lib/new/c.dart").write_text("// fixture\n")
    git(tmp_path, "mv", "lib/a.dart", "lib/moved.dart")
    assert runner.check(base=base, verify_plan=False, quick=True) == 0
    assert trace(tmp_path) == ["analyze --fatal-infos ."]
    git(tmp_path, "mv", "lib/moved.dart", "lib/a.dart")
    git(tmp_path, "init", "-q", "lib/other")
    (tmp_path / "lib/other/e.dart").write_text("// SEEDED\n")
    assert runner.check(base=base, verify_plan=False, quick=True) == 1
    assert trace(tmp_path) == ["analyze --fatal-infos ."]
    assert changed_dart(tmp_path, [analysis(".", DART)], {"lib/other"}) == {}


def test_a_gate_of_another_tool_with_the_name_of_the_dart_gate_runs_its_own_command(
    runner: ModuleType, tmp_path: Path
) -> None:
    other: Gate = {
        "name": "types-lint",
        "role": "lint",
        "command": [sys.executable, "-c", "open('ran', 'w').close()"],
    }
    group: Group = {"path": ".", "checks": [other]}
    runner.CHANGED_DART["./types-lint"] = []
    assert runner.run_gate(group, other, 30, threading.Lock()) is False
    assert (tmp_path / "ran").is_file()


def test_a_pass_on_the_changed_files_leaves_the_gate_time_and_the_old_findings_alone(
    runner: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    recorded = {"./types-lint": {"error - lib/old.dart:N:N - old finding": 1}}
    (tmp_path / "hard-eng.debt.json").write_text(
        json.dumps({"version": 1, "gates": recorded})
    )
    base = project(runner, monkeypatch)
    (tmp_path / "old.txt").write_text(OLD)
    times = tmp_path / ".git/hard-eng-gate-times.json"
    assert runner.check(base=base, verify_plan=False) == 0
    assert "DEBT types-lint @ .: the failure above holds only the 1 lines" in (
        capsys.readouterr().out
    )
    times.write_text(json.dumps({"./types-lint": 900.0}))
    (tmp_path / "lib/a.dart").write_text("// changed\n")
    trace(tmp_path)
    assert runner.check(base=base, verify_plan=False, quick=True) == 0
    assert trace(tmp_path) == ["analyze --fatal-infos lib/a.dart"]
    assert "recorded lines are fixed" not in capsys.readouterr().out
    assert json.loads(times.read_text()) == {"./types-lint": 900.0}

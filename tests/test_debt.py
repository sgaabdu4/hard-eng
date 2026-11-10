"""Shrink-only adoption debt for findings that existing code had at install."""

import json
import re
import sys
import threading
from pathlib import Path
from types import ModuleType

import debt
import pytest
from conftest import commit, git
from gate_config import Gate, Group
from test_basic_mode import no_provisioning

FINDINGS = "import pathlib, sys; text = pathlib.Path('findings.txt').read_text(); print(text, end=''); sys.exit(bool(text))"


def run(runner: ModuleType, group: Group, check: Gate, findings: str) -> bool:
    (Path(runner.ROOT) / "findings.txt").write_text(findings)
    return runner.run_gate(group, check, 30, threading.Lock())


def test_old_findings_pass_new_ones_fail_and_fixed_ones_must_be_dropped(
    runner: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint: Gate = {
        "name": "lint",
        "role": "lint",
        "command": [sys.executable, "-c", FINDINGS],
    }
    group: Group = {"path": ".", "checks": [lint]}
    runner.RECORDING.set()
    try:
        assert (
            run(runner, group, lint, "\x1b[1ma.py:3:1: F841 unused x\x1b[0m\n") is True
        )
    finally:
        runner.RECORDING.clear()
    assert debt.record(tmp_path, [group], set(runner.FAILED_GATES), debt.OUTPUTS) == 0
    recorded = json.loads((tmp_path / debt.DEBT_FILE).read_text())
    assert recorded == {"version": 1, "gates": {"./lint": {"a.py:N:N: FN unused x": 1}}}
    capsys.readouterr()

    assert run(runner, group, lint, "a.py:9:1: F841 unused x\n") is False
    assert (
        "DEBT lint @ .: the failure above holds only the 1 lines"
        in capsys.readouterr().out
    )
    assert (
        run(runner, group, lint, "a.py:9:1: F841 unused x\nb.py:2:1: F841 unused y\n")
        is True
    )
    assert "  b.py:2:1: F841 unused y" in capsys.readouterr().out
    assert run(runner, group, lint, "") is True
    assert "1 recorded lines are fixed" in capsys.readouterr().out

    assert debt.record(tmp_path, [group], set(), {}) == 0
    assert json.loads((tmp_path / debt.DEBT_FILE).read_text())["gates"] == {}


def test_a_new_finding_beyond_the_debt_prints_its_real_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["biome"]}
    group: Group = {"path": ".", "checks": [lint]}
    kind = "lint/suspicious/noDebugger"
    recorded = {f"src/fN.ts:N:N {kind}": 25}
    (tmp_path / debt.DEBT_FILE).write_text(
        json.dumps({"version": 1, "gates": {"./lint": recorded}})
    )
    old = "".join(
        f"src/f{number:02d}.ts:{number}:5 {kind}\n" for number in range(1, 26)
    )
    assert debt.judge(tmp_path, group, lint, True, old) is False
    capsys.readouterr()
    new = f"{tmp_path}/app/price-list.tsx:41:9 lint/style/useConst\n"
    assert debt.judge(tmp_path, group, lint, True, old + new) is True
    shown = capsys.readouterr().out
    assert "  ./app/price-list.tsx:41:9 lint/style/useConst" in shown
    assert (
        debt.judge(tmp_path, group, lint, True, old + old.splitlines(keepends=True)[0])
        is True
    )
    mixed = capsys.readouterr().out
    assert "  src/f07.ts:7:5 " + kind in mixed
    assert "New lines among these: 1." in mixed


def test_a_later_adoption_only_drops_lines(tmp_path: Path) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["ruff"]}
    group: Group = {"path": ".", "checks": [lint]}
    assert debt.record(tmp_path, [group], {"./lint"}, {"./lint": "a.py:1 x\n"}) == 0
    more = {"./lint": "a.py:1 x\nb.py:1 y\n"}
    assert debt.record(tmp_path, [group], {"./lint"}, more) == 0
    assert debt.load(tmp_path) == {"./lint": {"a.py:N x": 1}}


NEVER_DEBT = ["tests", "lockfiles", "secrets-files", "secrets-history"]


@pytest.mark.parametrize("role", NEVER_DEBT)
def test_tests_lockfiles_and_secrets_never_become_debt(
    tmp_path: Path, role: str, capsys: pytest.CaptureFixture[str]
) -> None:
    check: Gate = {"name": role, "role": role, "command": ["tool"]}
    group: Group = {"path": ".", "checks": [check]}
    assert debt.record(tmp_path, [group], {f"./{role}"}, {f"./{role}": "failed\n"}) == 1
    assert not (tmp_path / debt.DEBT_FILE).exists()
    assert "must pass before adoption" in capsys.readouterr().out


@pytest.mark.parametrize("role", NEVER_DEBT)
def test_hand_written_debt_never_passes_tests_lockfiles_or_secrets(
    tmp_path: Path, role: str
) -> None:
    """HE-DEBT-SHRINK-ONLY: an entry written by hand for one of these gates changes nothing."""
    check: Gate = {"name": role, "role": role, "command": ["tool"]}
    group: Group = {"path": ".", "checks": [check]}
    written = {"version": 1, "gates": {f"./{role}": {"failed": 1}}}
    (tmp_path / debt.DEBT_FILE).write_text(json.dumps(written))
    assert debt.judge(tmp_path, group, check, True, "failed\n") is True


def test_a_gate_that_cannot_run_is_never_passed_as_debt(
    runner: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": [str(tmp_path / "gone")]}
    group: Group = {"path": ".", "checks": [lint]}
    runner.RECORDING.set()
    try:
        assert runner.run_gate(group, lint, 30, threading.Lock()) is True
    finally:
        runner.RECORDING.clear()
    adopted = debt.record(tmp_path, [group], set(runner.FAILED_GATES), debt.OUTPUTS)
    assert runner.run_gate(group, lint, 30, threading.Lock()) is True
    assert adopted == 1
    assert "must pass before adoption" in capsys.readouterr().out


def test_report_findings_count_beside_the_output(tmp_path: Path) -> None:
    report = tmp_path / "coverage/semgrep.json"
    report.parent.mkdir()
    result = {"check_id": "rule", "path": "a.py", "extra": {"lines": "eval(x)"}}
    report.write_text(json.dumps({"results": [result, result]}))
    security: Gate = {
        "name": "security",
        "role": "security",
        "command": ["semgrep"],
        "report": {"type": "semgrep", "path": "coverage/semgrep.json"},
    }
    group: Group = {"path": ".", "checks": [security]}
    found = debt.fingerprints(tmp_path, group, security, f"Ran 3 rules in {tmp_path}\n")
    assert found == {"rule a.py eval(x)": 2, "Ran N rules in .": 1}


@pytest.mark.parametrize(
    ("kind", "report", "expected"),
    [
        (
            "osv",
            {
                "results": [
                    {
                        "packages": [
                            {
                                "package": {"name": "lib", "version": "1.0.2"},
                                "vulnerabilities": [{"id": "GHSA-b"}, {"id": "GHSA-a"}],
                            },
                            {"package": {"name": "safe", "version": "2.0.0"}},
                        ]
                    }
                ]
            },
            "lib 1.0.2 GHSA-a,GHSA-b",
        ),
        (
            "jscpd",
            {
                "duplicates": [
                    {
                        "firstFile": {"name": "a.ts"},
                        "secondFile": {"name": "b.ts"},
                        "fragment": "const x = 1;",
                    }
                ]
            },
            "a.ts b.ts const x = 1;",
        ),
        (
            "deptry",
            [
                {
                    "error": {"code": "DEP001", "message": "missing"},
                    "module": "requests",
                    "location": {"file": "app.py", "line": 1, "column": 0},
                }
            ],
            "DEP001 requests app.py",
        ),
    ],
)
def test_osv_jscpd_and_deptry_reports_become_debt_lines(
    tmp_path: Path, kind: str, report: object, expected: str
) -> None:
    (tmp_path / "report.json").write_text(json.dumps(report))
    check: Gate = {
        "name": kind,
        "role": "dependencies",
        "command": [kind],
        "report": {"type": kind, "path": "report.json"},
    }
    group: Group = {"path": ".", "checks": [check]}
    assert debt.fingerprints(tmp_path, group, check, "") == {expected: 1}


def test_an_unreadable_report_is_never_recorded_as_debt(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "coverage/semgrep.json"
    report.parent.mkdir()
    report.write_text("{")
    security: Gate = {
        "name": "security",
        "role": "security",
        "command": ["semgrep"],
        "report": {"type": "semgrep", "path": "coverage/semgrep.json"},
    }
    group: Group = {"path": ".", "checks": [security]}
    output = {"./security": "Ran 3 rules\n"}
    assert debt.record(tmp_path, [group], {"./security"}, output) == 1
    assert "must pass before adoption" in capsys.readouterr().out


def test_a_mismatched_virtual_env_warning_is_not_a_finding(tmp_path: Path) -> None:
    """uv warns when an outer VIRTUAL_ENV is set; that warning must not count as debt."""
    gate: Gate = {"name": "dependencies", "role": "dependencies", "command": ["uv"]}
    group: Group = {"path": ".", "checks": [gate]}
    output = "warning: `VIRTUAL_ENV=/other/.venv` does not match the project environment path `.venv`\n"
    assert debt.fingerprints(tmp_path, group, gate, output) == {}


def test_debt_appears_only_with_the_install_and_never_grows(repository: Path) -> None:
    """HE-DEBT-SHRINK-ONLY: the debt file is added by the install and only shrinks."""
    path = repository / debt.DEBT_FILE
    base = git(repository, "rev-parse", "HEAD")
    path.write_text(json.dumps({"version": 1, "gates": {"./lint": {"a": 1}}}))
    debt.require_shrink(repository, base)
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text("{}")
    path.unlink()
    installed = commit(repository, "install")
    path.write_text(json.dumps({"version": 1, "gates": {"./lint": {"a": 1}}}))
    with pytest.raises(ValueError, match="only the change that installs"):
        debt.require_shrink(repository, installed)
    recorded = commit(repository, "record debt")
    path.write_text(json.dumps({"version": 1, "gates": {"./lint": {"a": 2}}}))
    with pytest.raises(ValueError, match=r"grew for \./lint"):
        debt.require_shrink(repository, recorded)
    path.write_text(json.dumps({"version": 1, "gates": {"./types": {"b": 1}}}))
    with pytest.raises(ValueError, match=r"grew for \./types"):
        debt.require_shrink(repository, recorded)
    path.write_text(json.dumps({"version": 1, "gates": {}}))
    debt.require_shrink(repository, recorded)


def test_adoption_restarts_with_pyyaml_like_the_check(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    import importlib.util
    import os
    from importlib.machinery import ModuleSpec

    class Restarted(Exception):
        pass

    def restart(_file: str, arguments: list[str]) -> None:
        raise Restarted(arguments)

    find_spec = importlib.util.find_spec

    def without_yaml(name: str, package: str | None = None) -> ModuleSpec | None:
        return None if name == "yaml" else find_spec(name, package)

    def adopting(_root: Path) -> None:
        pytest.fail("adopted without PyYAML")

    monkeypatch.setattr(importlib.util, "find_spec", without_yaml)
    monkeypatch.setattr(os, "execvp", restart)
    monkeypatch.setattr(runner, "check_lock", adopting)
    monkeypatch.setattr(sys, "argv", ["hard-eng.py", "adopt"])
    with pytest.raises(Restarted) as restarted:
        runner.main()
    arguments = restarted.value.args[0]
    assert arguments[:5] == ["uv", "run", "--no-project", "--with", "pyyaml"]
    assert arguments[-2:] == ["hard-eng.py", "adopt"]


@pytest.mark.parametrize("tracked", [True, False])
def test_adoption_records_what_the_fixed_code_still_fails_with(
    runner: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tracked: bool
) -> None:
    fixing = (
        "import pathlib, sys; p = pathlib.Path('a.py'); t = p.read_text(); "
        "p.write_text(t.replace('old', 'new')); print('a.py:1:1: F1 still wrong'); "
        "print('Fixed 1 error.' if 'old' in t else ''); sys.exit(1)"
    )
    lint = {"name": "lint", "role": "lint", "command": [sys.executable, "-c", fixing]}
    (tmp_path / "hard-eng.gates.json").write_text(
        json.dumps({"packages": [], "shared": [lint]})
    )
    git(tmp_path, "config", "user.name", "Fixture")
    git(tmp_path, "config", "user.email", "fixture@example.invalid")
    commit(tmp_path, "baseline")
    (tmp_path / "a.py").write_text("old\n")
    if tracked:
        commit(tmp_path, "add the source")
    monkeypatch.setattr(runner, "provision_tools", no_provisioning)
    debt.OUTPUTS.clear()
    assert runner.adopt() == 0
    recorded = json.loads((tmp_path / debt.DEBT_FILE).read_text())["gates"]
    assert recorded == {"./lint": {"a.py:N:N: FN still wrong": 1}}


COUNT_WORD_PAIRS = [
    ("Found 3 errors.", "Found 1 error."),
    (
        "3 hidden fixes can be enabled with the `--unsafe-fixes` option.",
        "1 hidden fix can be enabled with the `--unsafe-fixes` option.",
    ),
    ("3 files would be reformatted", "1 file would be reformatted"),
    (" INFO 2 errors", " INFO 1 error"),
    (
        "Checked 3 files in 5ms. No fixes applied.",
        "Checked 1 file in 5ms. No fixes applied.",
    ),
    ("3 issues found.", "1 issue found."),
]


def assert_same_debt_line(repository: Path, recorded: str, current: str) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["ruff"]}
    group: Group = {"path": ".", "checks": [lint]}
    failed = {"./lint"}
    assert debt.record(repository, [group], failed, {"./lint": recorded + "\n"}) == 0
    base = commit(repository, "record debt")
    written = (repository / debt.DEBT_FILE).read_text()
    assert debt.judge(repository, group, lint, True, current + "\n") is False
    assert debt.record(repository, [group], failed, {"./lint": current + "\n"}) == 0
    assert (repository / debt.DEBT_FILE).read_text() == written
    debt.require_shrink(repository, base)


@pytest.mark.parametrize(("recorded", "current"), COUNT_WORD_PAIRS)
def test_a_count_word_for_one_or_many_is_the_same_debt_line(
    repository: Path, recorded: str, current: str
) -> None:
    assert_same_debt_line(repository, recorded, current)


TIME_PAIRS = [
    (
        "Checked 3 files in 2ms. No fixes applied.",
        "Checked 3 files in 1548\u00b5s. No fixes applied.",
    ),
    (
        "Checked 3 files in 1548\u00b5s. No fixes applied.",
        "Checked 3 files in 2ms. No fixes applied.",
    ),
    ("Finished in 1.5s", "Finished in 300ns"),
    ("Finished in 12.25ms", "Finished in 2us"),
]


@pytest.mark.parametrize(("recorded", "current"), TIME_PAIRS)
def test_a_time_in_another_unit_is_the_same_debt_line(
    repository: Path, recorded: str, current: str
) -> None:
    assert_same_debt_line(repository, recorded, current)


SAMPLES = Path(__file__).parent / "fixtures/debt"
LINT: Gate = {"name": "lint", "role": "lint", "command": ["lint"]}
LINT_GROUP: Group = {"path": ".", "checks": [LINT]}


@pytest.mark.parametrize("tool", ["biome", "ruff"])
def test_a_changed_source_line_in_a_code_frame_is_no_new_finding(
    repository: Path, capsys: pytest.CaptureFixture[str], tool: str
) -> None:
    (repository / debt.DEBT_FILE).write_text(
        (SAMPLES / f"{tool}-recorded-by-base.json").read_text()
    )
    after_fix = (SAMPLES / f"{tool}-one.txt").read_text()
    assert debt.judge(repository, LINT_GROUP, LINT, True, after_fix) is True
    printed = capsys.readouterr().out
    assert "findings beyond" not in printed
    assert "recorded lines are fixed" in printed
    assert debt.record(repository, [LINT_GROUP], {"./lint"}, {"./lint": after_fix}) == 0
    recorded = json.loads((repository / debt.DEBT_FILE).read_text())["gates"]["./lint"]
    assert not [line for line in recorded if re.match(r"[> N]*[\u2502|]", line)]
    assert debt.judge(repository, LINT_GROUP, LINT, True, after_fix) is False


def test_a_debt_file_recorded_with_link_codes_still_matches(repository: Path) -> None:
    (repository / debt.DEBT_FILE).write_text(
        (SAMPLES / "biome-recorded-by-base.json").read_text()
    )
    recorded = (repository / debt.DEBT_FILE).read_text()
    assert "\\u001b]N;;https://biomejs.dev" in recorded
    again = (SAMPLES / "biome-two.txt").read_text()
    assert debt.judge(repository, LINT_GROUP, LINT, True, again) is False

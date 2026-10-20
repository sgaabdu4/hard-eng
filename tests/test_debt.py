"""Shrink-only adoption debt for findings that existing code had at install."""

import json
import sys
import threading
from pathlib import Path
from types import ModuleType

import debt
import pytest
from conftest import commit, git
from gate_config import Gate, Group

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
        "DEBT lint: the failure above holds only the 1 lines" in capsys.readouterr().out
    )
    assert (
        run(runner, group, lint, "a.py:9:1: F841 unused x\nb.py:2:1: F841 unused y\n")
        is True
    )
    assert "  b.py:N:N: FN unused y" in capsys.readouterr().out
    assert run(runner, group, lint, "") is True
    assert "1 recorded lines are fixed" in capsys.readouterr().out

    assert debt.record(tmp_path, [group], set(), {}) == 0
    assert json.loads((tmp_path / debt.DEBT_FILE).read_text())["gates"] == {}


def test_a_later_adoption_only_drops_lines(tmp_path: Path) -> None:
    lint: Gate = {"name": "lint", "role": "lint", "command": ["ruff"]}
    group: Group = {"path": ".", "checks": [lint]}
    assert debt.record(tmp_path, [group], {"./lint"}, {"./lint": "a.py:1 x\n"}) == 0
    more = {"./lint": "a.py:1 x\nb.py:1 y\n"}
    assert debt.record(tmp_path, [group], {"./lint"}, more) == 0
    assert debt.load(tmp_path) == {"./lint": {"a.py:N x": 1}}


@pytest.mark.parametrize("role", sorted(debt.NEVER))
def test_tests_lockfiles_and_secrets_never_become_debt(
    tmp_path: Path, role: str, capsys: pytest.CaptureFixture[str]
) -> None:
    check: Gate = {"name": role, "role": role, "command": ["tool"]}
    group: Group = {"path": ".", "checks": [check]}
    assert debt.record(tmp_path, [group], {f"./{role}"}, {f"./{role}": "failed\n"}) == 1
    assert not (tmp_path / debt.DEBT_FILE).exists()
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

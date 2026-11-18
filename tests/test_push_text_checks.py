"""Prove the push of a project that leaves its full check to CI still judges the plan and the changed lines."""

from argparse import Namespace
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest
from conftest import commit, git


def work_branch(root: Path, plan: str, source: str, script: str = "") -> None:
    git(root, "branch", "-M", "main")
    (root / "a.py").write_text("".join(f"line {n}\n" for n in range(30)))
    commit(root, "base")
    git(root, "switch", "-qc", "work")
    (root / "a.py").write_text(source)
    (root / "PLAN.md").write_text(plan)
    if script:
        (root / "b.js").write_text(script)
    commit(root, "work")


def push_check(runner: ModuleType, root: Path, monkeypatch: pytest.MonkeyPatch) -> int:
    scan = Mock(return_value=0)
    gates = Mock(side_effect=AssertionError("no gate of the full check may run"))
    monkeypatch.setattr(runner, "ROOT", root)
    monkeypatch.setattr("gitleaks_scan.commit_secret_scan", scan)
    monkeypatch.setattr(runner, "check", gates)
    monkeypatch.setattr(runner, "run_gates", gates)
    arguments = Namespace(commit_secrets=True, base="main", shard=None)
    code = runner.check_command(arguments)
    scan.assert_called_once()
    return int(code)


def test_a_ready_plan_is_refused_before_the_push_when_ci_runs_the_full_check(
    runner: ModuleType,
    repository: Path,
    completed_plan: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ready = completed_plan.replace("Status: Complete", "Status: Ready")
    work_branch(repository, ready, "changed 0\n" + "line 1\n" * 29)
    assert push_check(runner, repository, monkeypatch) == 1
    assert "plan is Ready; this check requires Complete" in capsys.readouterr().out


def test_a_changed_line_text_finding_is_refused_before_the_push_when_ci_runs_the_full_check(
    runner: ModuleType,
    repository: Path,
    completed_plan: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    changed = "changed 0\n" + "line 1\n" * 29
    script = "// eslint-disable-next-line\nf();\n"
    work_branch(repository, completed_plan, changed, script)
    assert push_check(runner, repository, monkeypatch) == 1
    assert "eslint-disable" in capsys.readouterr().out


def test_a_complete_plan_and_clean_lines_pass_without_any_gate_of_the_full_check(
    runner: ModuleType,
    repository: Path,
    completed_plan: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work_branch(repository, completed_plan, "x = 1\n" + "line 1\n" * 29)
    assert push_check(runner, repository, monkeypatch) == 0

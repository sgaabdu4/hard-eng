"""A plain local check of a gate with shards makes the refusals of a shard job."""

import sys
import threading
from argparse import Namespace
from pathlib import Path
from types import ModuleType
from typing import cast

import gate_config
import pytest
import test_shards
import tool_setup
from conftest import configure
from gate_config import Gate, Group
from test_shards import add_to_settings, log_lines, pytest_group, shard_gate

shard_project = test_shards.shard_project


def run_plain(runner: ModuleType, command: list[str], shards: int | None = 2) -> bool:
    check = {**shard_gate(shards), "command": command}
    group = pytest_group(".", [cast(Gate, check)])
    return runner.run_gate(group, group["checks"][0], 300, threading.Lock(), [group])


PLAIN_REFUSALS = [
    (
        [sys.executable, "-m", "pytest", "tests"],
        None,
        './tests: the command names the path "tests", so every shard would run it whole.',
    ),
    (
        [sys.executable, "-m", "pytest"],
        'addopts = "-q tests"\n',
        './tests: addopts in pyproject.toml names the path "tests", so every shard would run it whole.',
    ),
    (
        [sys.executable, "-m", "pytest", "--cov-config=c.cfg"],
        None,
        "the tests command gives --cov-config, which moves the pytest or coverage.py settings.",
    ),
    (
        [sys.executable, "-m", "pytest"],
        'addopts = "-c other.ini"\n',
        "addopts in pyproject.toml gives -c, which moves the pytest or coverage.py settings.",
    ),
    (
        [sys.executable, "-m", "pytest"],
        'addopts = "--config-file=other.ini"\n',
        "addopts in pyproject.toml gives --config-file, which moves the pytest or coverage.py settings.",
    ),
]


@pytest.mark.parametrize(("command", "settings", "printed"), PLAIN_REFUSALS)
def test_a_local_check_of_a_shard_gate_refuses_what_tracked_files_hold(
    runner: ModuleType,
    shard_project: Path,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
    settings: str | None,
    printed: str,
) -> None:
    if settings:
        add_to_settings(shard_project, settings)
    assert run_plain(runner, command) is True
    assert printed in capsys.readouterr().out
    assert log_lines(shard_project) == []


@pytest.mark.parametrize("name", ["PYTEST_ADDOPTS", "COVERAGE_RCFILE"])
def test_a_local_check_reads_no_variable_and_no_gate_without_shards(
    runner: ModuleType,
    shard_project: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    name: str,
) -> None:
    command = [sys.executable, "-m", "pytest"]
    monkeypatch.setenv(name, "-q")
    run_plain(runner, command)
    printed = capsys.readouterr().out
    assert "moves the pytest or coverage.py settings" not in printed
    assert "run" in log_lines(shard_project)
    monkeypatch.delenv(name)
    for unsharded in ([*command, "tests"], [*command, "--cov-config=c.cfg"]):
        run_plain(runner, unsharded, None)
        printed = capsys.readouterr().out
        assert "every shard would run it whole" not in printed
        assert "moves the pytest or coverage.py settings" not in printed
        assert "run" in log_lines(shard_project)


def test_only_a_merge_inside_the_workflow_skips_the_workflow_check(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    options: list[dict[str, object]] = []

    def load_groups(*_arguments: object, **given: object) -> list[Group]:
        options.append(given)
        return []

    configure(runner.ROOT, [])
    monkeypatch.setattr(gate_config, "load_groups", load_groups)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    assert runner.check(base="0" * 40, plan_stage="Complete", shard="merge") == 0
    assert options == [{"dependents": True, "workflow_checked": True}]
    options.clear()
    monkeypatch.delenv("GITHUB_ACTIONS")
    assert runner.check(base="0" * 40, plan_stage="Complete", shard="merge") == 0
    assert options == [{"dependents": True, "workflow_checked": False}]
    options.clear()
    assert runner.check(base="0" * 40, plan_stage="Complete", shard="rest") == 0
    assert options[0] == {"dependents": True, "workflow_checked": False}


@pytest.mark.parametrize(("actions", "provided"), [("true", False), ("", True)])
def test_only_a_merge_inside_the_workflow_skips_the_python_runtime_setup(
    runner: ModuleType, monkeypatch: pytest.MonkeyPatch, actions: str, provided: bool
) -> None:
    started: list[str] = []
    monkeypatch.setattr(
        tool_setup, "ensure_python_runtime", lambda: started.append("runtime")
    )

    def checked(**_options: object) -> int:
        return 0

    def no_filter(_arguments: Namespace) -> list[str]:
        return []

    monkeypatch.setattr(runner, "check", checked)
    monkeypatch.setenv("GITHUB_ACTIONS", actions)
    arguments = Namespace(
        shard="merge",
        commit_secrets=False,
        base=None,
        plan_stage=None,
        without_dependents=False,
        related_tests=False,
        quick=False,
        static=False,
    )
    monkeypatch.setattr(runner, "language_filter", no_filter)
    assert runner.check_command(arguments) == 0
    assert bool(started) is provided

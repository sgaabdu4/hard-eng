"""Shapes that Hard Eng itself ships or that real projects have must pass the judges."""

import json
from pathlib import Path

import pytest
from gate_config import Gate, Group, validate_gate
from resolved_settings import judge_before_run, validate_resolved
from test_fallow_resolved import need_fallow, tests_group
from test_strict_refusals import project

PYPROJECT = '[project]\nname = "x"\nversion = "0"\nrequires-python = "{}"\n'
LINT: Gate = {"name": "lint", "role": "lint", "command": ["ruff", "check", "."]}


def ruff_groups(*paths: str) -> list[Group]:
    return [{"path": path, "language": "python", "checks": [LINT]} for path in paths]


def test_the_template_group_with_a_coverage_gate_and_a_tests_gate_runs(
    tmp_path: Path,
) -> None:
    """The judge that runs right before Fallow sees the tests gate that writes the coverage file."""
    need_fallow()
    root = project(
        tmp_path,
        {
            ".gitignore": "coverage/\n",
            ".fallowrc.json": json.dumps(
                {"health": {"coverage": "coverage/coverage-final.json"}}
            ),
            "src/main.ts": "export {};\n",
        },
    )
    group = tests_group()[0]
    fallow = group["checks"][0]
    judge_before_run(root, group, fallow, [group], 900)
    validate_resolved(root, [group], 900)


@pytest.mark.parametrize("minimum", [">=3.11", ">=3.14", "~=3.10"])
def test_the_installed_hooks_ruff_config_does_not_decide_the_target(
    tmp_path: Path, minimum: str
) -> None:
    """Hard Eng's installed `.hooks/ruff.toml` pins py312 for the hooks; the project's own target is judged."""
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT.format(minimum),
            "a.py": "x = 1\n",
            ".hooks/hard-eng-source.json": "{}",
            ".hooks/ruff.toml": 'target-version = "py312"\n',
            ".hooks/tool.py": "x = 1\n",
        },
    )
    validate_resolved(root, ruff_groups("."), 900)


def test_a_member_with_its_own_requires_python_is_judged_against_it(
    tmp_path: Path,
) -> None:
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT.format(">=3.10"),
            "a.py": "x = 1\n",
            "pkg/pyproject.toml": PYPROJECT.format(">=3.12"),
            "pkg/ruff.toml": 'target-version = "py312"\n',
            "pkg/b.py": "x = 1\n",
        },
    )
    every = ruff_groups(".", "pkg")
    validate_resolved(root, every, 900, every)


def test_a_compatible_release_minimum_is_read(tmp_path: Path) -> None:
    """HE-NO-SWITCH-OFF: `~=3.10` means 3.10 or newer, so py313 is above the minimum."""
    root = project(
        tmp_path,
        {
            "pyproject.toml": PYPROJECT.format("~=3.10")
            + '[tool.ruff]\ntarget-version = "py313"\n',
            "a.py": "x = 1\n",
        },
    )
    with pytest.raises(ValueError, match=r"target version 3\.13 is above"):
        validate_resolved(root, ruff_groups("."), 900)


def test_a_pnpm_shim_for_fallow_passes_the_load(tmp_path: Path) -> None:
    """The runner calls `fallow` directly, so a package manager's own shim in node_modules/.bin is not a shadow."""
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"scan": "fallow --fail-on-issues"}})
    )
    shim = tmp_path / "node_modules/.bin/fallow"
    shim.parent.mkdir(parents=True)
    shim.write_text('#!/bin/sh\nexec node "$basedir/../fallow/bin/fallow" "$@"\n')
    validate_gate({"name": "g", "command": ["bun", "run", "scan"]}, tmp_path, set())

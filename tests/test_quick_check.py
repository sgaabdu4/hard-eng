"""The quick check runs only the fast gate roles."""

from pathlib import Path
from types import ModuleType

import pytest
from conftest import configure, gate
from gate_config import Group
from reports import quick_groups

QUICK_ROLES = ("format", "lint", "types")
SLOW_ROLES = ("complexity", "dead-code", "custom")


def test_quick_set_leaves_out_slow_and_unlabelled_gates(runner: ModuleType) -> None:
    slow = [
        "tests",
        "performance",
        "complexity",
        "dead-code",
        "duplicates",
        "dependencies",
        "lockfiles",
        "vulnerabilities",
        "security",
        "secrets-history",
        "workflows",
        "shell",
        "custom",
    ]
    group: Group = {
        "path": ".",
        "checks": [{"name": role, "role": role, "command": ["x"]} for role in slow]
        + [{"name": "unlabelled", "command": ["x"]}],
    }
    assert quick_groups([group], installed=frozenset({"."}))[0]["checks"] == []


@pytest.mark.parametrize(
    ("quick", "expected"),
    [(True, QUICK_ROLES), (False, QUICK_ROLES + SLOW_ROLES)],
)
def test_quick_check_runs_only_the_fast_roles_and_plain_check_runs_all(
    runner: ModuleType, tmp_path: Path, quick: bool, expected: tuple[str, ...]
) -> None:
    configure(
        tmp_path,
        [
            gate(
                role,
                f"open({role!r}, 'w').close()",
                role=role,
                parallel=True,
            )
            for role in QUICK_ROLES + SLOW_ROLES
        ],
    )
    assert runner.check(quick=quick) == 0
    ran = {path.name for path in tmp_path.iterdir()} & set(QUICK_ROLES + SLOW_ROLES)
    assert ran == set(expected)


def test_the_first_quick_check_in_a_checkout_runs_the_install_one_time(
    runner: ModuleType, tmp_path: Path
) -> None:
    install = "import os, sys; open('trace', 'a').write('x'); sys.exit(os.path.exists('broken'))"
    configure(
        tmp_path,
        [
            gate("install", install, role="lockfiles"),
            gate("format", "pass", role="format", parallel=True),
        ],
    )
    state = tmp_path / ".git/hard-eng-installed"

    def installs(*, quick: bool) -> tuple[int, int]:
        code = runner.check(quick=quick)
        return code, len((tmp_path / "trace").read_text())

    assert installs(quick=True) == (0, 1)
    assert installs(quick=True) == (0, 1)
    state.unlink()
    assert installs(quick=False) == (0, 2)
    assert installs(quick=True) == (0, 2)
    state.unlink()
    (tmp_path / "broken").touch()
    assert installs(quick=True) == (1, 3)
    assert installs(quick=True) == (1, 4)

"""The quick check runs only the fast gate roles."""

from pathlib import Path
from types import ModuleType

import pytest
from conftest import configure, gate
from gate_config import Group
from reports import quick_groups

QUICK_ROLES = ("format", "lint", "types")
SLOW_ROLES = ("complexity", "dead-code", "custom")


def test_quick_set_is_chosen_by_role(runner: ModuleType) -> None:
    quick = [
        "format",
        "lint",
        "format-lint",
        "types",
        "annotations",
        "typing-style",
        "imports",
        "tests",
        "focused-tests",
        "secrets-files",
    ]
    slow = [
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
        "checks": [
            {"name": role, "role": role, "command": ["x"]} for role in quick + slow
        ]
        + [{"name": "unlabelled", "command": ["x"]}],
    }
    kept = quick_groups([group])[0]["checks"]
    assert [item["name"] for item in kept] == quick


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

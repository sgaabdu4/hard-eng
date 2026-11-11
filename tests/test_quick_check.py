"""The quick check runs only the fast gate roles."""

import threading
from pathlib import Path
from types import ModuleType
from typing import cast

import process_group
import pytest
from conftest import configure, gate
from gate_config import Gate, Group
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
    marked = frozenset({process_group.install_key(group)})
    assert quick_groups([group], installed=marked)[0]["checks"] == []


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
    (tmp_path / "broken").unlink()
    assert installs(quick=True) == (0, 5)
    (tmp_path / "broken").touch()
    assert installs(quick=False) == (1, 6)
    assert installs(quick=True) == (1, 7)


def test_an_install_marks_only_its_own_group_in_a_shared_folder(
    runner: ModuleType, tmp_path: Path
) -> None:
    install = cast(Gate, gate("install", "pass", role="lockfiles"))
    python, web = (
        cast(Group, {"path": ".", "language": language, "checks": [install]})
        for language in ("python", "javascript")
    )
    with (tmp_path / "lock").open("w+") as lock:
        before = process_group.read_installed(lock, tmp_path)
        assert runner.run_gate(python, install, 300, threading.Lock()) is False
        process_group.save_installed(lock, before, tmp_path)
        installed = process_group.read_installed(lock, tmp_path)
    kept = quick_groups([python, web], installed=installed)
    assert [len(group["checks"]) for group in kept] == [0, 1]


def test_a_changed_lock_file_drops_the_install_mark(tmp_path: Path) -> None:
    key = process_group.install_key({"path": "app", "language": "python"})
    package = tmp_path / "app"
    package.mkdir()
    (package / "uv.lock").write_text("one\n")
    with (tmp_path / "lock").open("w+") as lock:
        before = process_group.read_installed(lock, tmp_path)
        process_group.note_install(key, "lockfiles", False)
        process_group.save_installed(lock, before, tmp_path)
        assert process_group.read_installed(lock, tmp_path) == {key}
        (package / "uv.lock").write_text("one\ntwo\n")
        assert process_group.read_installed(lock, tmp_path) == frozenset()

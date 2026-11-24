"""The quick check runs only the fast gate roles."""

import threading
from pathlib import Path
from types import ModuleType
from typing import IO, cast

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


STATIC_ROLES = ("complexity", "dead-code", "duplicates", "dependencies")
TWISTY = "def f(a):\n" + "".join(
    f"    if a == {n}:\n        return {n}\n" for n in range(5)
)
OVER_LIMIT = (
    "import ast, sys; tree = ast.parse(open('src.py').read()); "
    "sys.exit(sum(isinstance(node, ast.If) for node in ast.walk(tree)) > 3)"
)


def test_a_static_check_runs_the_analyzer_roles_and_no_tests(
    runner: ModuleType, tmp_path: Path
) -> None:
    roles = QUICK_ROLES + STATIC_ROLES + ("tests", "custom")
    configure(
        tmp_path,
        [
            gate(role, f"open({role!r}, 'w').close()", role=role, parallel=True)
            for role in roles
        ],
    )
    assert runner.check(static=True) == 0
    assert {path.name for path in tmp_path.iterdir()} & set(roles) == set(STATIC_ROLES)


def test_a_function_over_the_complexity_limit_fails_the_static_check_and_passes_the_quick_one(
    runner: ModuleType, tmp_path: Path
) -> None:
    (tmp_path / "src.py").write_text(TWISTY)
    configure(
        tmp_path,
        [
            gate("format", "pass", role="format", parallel=True),
            gate("complexity", OVER_LIMIT, role="complexity", parallel=True),
            gate(
                "tests", "open('tests-ran', 'w').close()", role="tests", parallel=True
            ),
        ],
    )
    assert runner.check(quick=True) == 0
    assert runner.check(static=True) == 1
    assert not (tmp_path / "tests-ran").exists()
    (tmp_path / "src.py").write_text("def f(a):\n    return a\n")
    assert runner.check(static=True) == 0


def test_a_quick_check_refuses_a_bad_plan_line_as_the_full_check_does(
    runner: ModuleType, tmp_path: Path, completed_plan: str
) -> None:
    configure(tmp_path, [gate("format", "pass", role="format", parallel=True)])
    assert runner.check(quick=True) == 0
    bad = "- [x] Observe the configured command exit."
    (tmp_path / "PLAN.md").write_text(
        completed_plan.replace(
            "- [x] Observe the configured command exit → N/A — fixture plan has no product test.",
            bad,
        )
    )
    assert bad in (tmp_path / "PLAN.md").read_text()
    with pytest.raises(ValueError, match="Acceptance \\+ steps line needs"):
        runner.check(quick=True)
    with pytest.raises(ValueError, match="Acceptance \\+ steps line needs"):
        runner.check()


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


def test_a_quick_check_generates_code_before_the_types_until_the_install_and_it_pass(
    runner: ModuleType, tmp_path: Path
) -> None:
    made = "import os, sys; open('trace', 'a').write('x'); open('made', 'w').close(); sys.exit(os.path.exists('broken'))"
    reads = "import os, sys; sys.exit(not os.path.exists('made'))"
    configure(
        tmp_path,
        [
            gate("install", "pass", role="lockfiles"),
            gate("codegen", made, role="generated"),
            gate("types", reads, role="types", parallel=True),
        ],
    )

    def generates() -> tuple[int, int]:
        code = runner.check(quick=True)
        return code, len((tmp_path / "trace").read_text())

    assert generates() == (0, 1)
    assert generates() == (0, 1)
    (tmp_path / ".git/hard-eng-installed").unlink()
    (tmp_path / "broken").touch()
    assert generates() == (1, 2)
    assert generates() == (1, 3)
    (tmp_path / "broken").unlink()
    assert generates() == (0, 4)
    assert generates() == (0, 4)


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


def mark_install(tmp_path: Path, lock: IO[str], key: str) -> None:
    before = process_group.read_installed(lock, tmp_path)
    process_group.note_install(key, "lockfiles", False)
    process_group.save_installed(lock, before, tmp_path)
    assert process_group.read_installed(lock, tmp_path) == {key}


def test_a_changed_lock_file_drops_the_install_mark(tmp_path: Path) -> None:
    key = process_group.install_key({"path": "app", "language": "python"})
    package = tmp_path / "app"
    package.mkdir()
    (package / "uv.lock").write_text("one\n")
    with (tmp_path / "lock").open("w+") as lock:
        mark_install(tmp_path, lock, key)
        (package / "uv.lock").write_text("one\ntwo\n")
        assert process_group.read_installed(lock, tmp_path) == frozenset()


def test_a_removed_install_folder_drops_the_install_mark(tmp_path: Path) -> None:
    key = process_group.install_key({"path": "app", "language": "python"})
    package = tmp_path / "app"
    (package / ".venv").mkdir(parents=True)
    (package / "uv.lock").write_text("one\n")
    with (tmp_path / "lock").open("w+") as lock:
        mark_install(tmp_path, lock, key)
        (package / ".venv").rmdir()
        assert process_group.read_installed(lock, tmp_path) == frozenset()


def test_a_quick_check_installs_again_after_the_lock_file_of_a_group_with_no_language_changes(
    runner: ModuleType, tmp_path: Path
) -> None:
    """A workspace root that holds only its members has the install and no language."""
    configure(
        tmp_path,
        [
            gate("install", "open('trace', 'a').write('x')", role="lockfiles"),
            gate("format", "pass", role="format", parallel=True),
        ],
    )
    lock = tmp_path / "bun.lock"
    lock.write_text("one\n")

    def installs() -> int:
        assert runner.check(quick=True) == 0
        return len((tmp_path / "trace").read_text())

    assert installs() == 1
    assert installs() == 1
    lock.write_text("one\ntwo\n")
    assert installs() == 2
    assert installs() == 2

import os
import subprocess
from collections.abc import Callable
from functools import partial
from pathlib import Path

import change_size
import pytest
from conftest import commit, git
from plans import validate_plans
from test_plans import edit, new_file, sized_branch


@pytest.mark.parametrize(
    ("change", "verdict"),
    [
        (partial(edit, name="a.py", count=2), (True, "1 file, 4 changed lines")),
        (new_file, (False, "it adds, deletes or renames the file new.py")),
    ],
    ids=["small", "new"],
)
def test_sandbox_placeholder_does_not_add_a_file(
    repository: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: Callable[[Path], object],
    verdict: tuple[bool, str],
) -> None:
    sized_branch(repository)
    change(repository)
    # Inside the sandbox .bashrc is /dev/null bound over an empty file, so Git lists it.
    os.mkfifo(repository / ".bashrc")
    listed = change_size._git_output

    def sandbox_listing(root: Path, *arguments: str) -> str:
        found = listed(root, *arguments)
        return found + "\0.bashrc" if arguments[0] == "ls-files" else found

    monkeypatch.setattr(change_size, "_git_output", sandbox_listing)
    assert change_size.size_verdict(repository) == verdict


def test_the_debt_file_does_not_count_toward_the_size(repository: Path) -> None:
    sized_branch(repository)
    git(repository, "switch", "-q", "main")
    debt_file = repository / "hard-eng.debt.json"
    debt_file.write_text("".join(f"line {n}\n" for n in range(30)))
    commit(repository, "debt")
    git(repository, "switch", "-q", "work")
    git(repository, "rebase", "-q", "main")
    edit(repository, "a.py", 2)
    edit(repository, "hard-eng.debt.json", 25)
    assert change_size.size_verdict(repository) == (True, "1 file, 4 changed lines")


def test_small_change_needs_no_plan(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    validate_plans(repository)
    assert "Size: small (1 file, 4 changed lines); no plan needed." in (
        capsys.readouterr().out
    )


def test_documentation_only_change_needs_no_plan(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / "notes.md").write_text("notes\n" * 50)
    validate_plans(repository)
    assert "Size: small (documentation only)" in capsys.readouterr().out


def test_new_documentation_file_beside_a_small_fix_stays_small(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    (repository / "docs").mkdir()
    (repository / "docs/decision.md").write_text("why\n" * 80)
    validate_plans(repository)
    assert "Size: small (1 file, 4 changed lines)" in capsys.readouterr().out


def test_new_documentation_file_beside_a_new_code_file_is_big(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    new_file(repository)
    (repository / "docs").mkdir()
    (repository / "docs/decision.md").write_text("why\n")
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)
    assert "Size: big, because it adds" in capsys.readouterr().out


def test_a_check_with_no_base_passes_a_first_install_that_the_base_lacks(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng.py").write_text("x = 1\n")
    commit(repository, "Install Hard Eng")
    validate_plans(repository)
    assert "Size:" not in capsys.readouterr().out
    new_file(repository)
    with pytest.raises(ValueError, match="applicable PLAN"):
        validate_plans(repository)


def test_a_check_with_no_base_passes_a_clean_branch_with_no_branch_point(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    git(repository, "branch", "-M", "trunk")
    validate_plans(repository)
    assert "Size:" not in capsys.readouterr().out


def merging(repository: Path, other: str, linked: bool, conflict: bool) -> Path:
    sized_branch(repository)
    edit(repository, "a.py", 2)
    commit(repository, "task edit")
    git(repository, "switch", "-q", "main")
    (repository / "base_new.py").write_text("x = 1\n")
    if conflict:
        lines = (repository / "a.py").read_text().splitlines()
        (repository / "a.py").write_text("\n".join(["base line", *lines[1:]]) + "\n")
    commit(repository, "base moves")
    git(repository, "switch", "-qc", "other", "main~1")
    (repository / "other.py").write_text("y = 1\n")
    commit(repository, "other work")
    git(repository, "switch", "-q", "work")
    root = repository
    if linked:
        git(repository, "branch", "work2", "work")
        git(repository, "switch", "-q", "main")
        root = repository.parent / "linked"
        git(repository, "worktree", "add", "-q", str(root), "work2")
    subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", other],
        cwd=root,
        capture_output=True,
        check=False,
    )
    assert git(root, "rev-parse", "-q", "--verify", "MERGE_HEAD")
    assert bool(git(root, "ls-files", "--unmerged")) == conflict
    return root


@pytest.mark.parametrize("conflict", [True, False], ids=["conflict", "staged"])
@pytest.mark.parametrize("linked", [False, True], ids=["main checkout", "linked"])
def test_a_merge_of_the_base_in_progress_does_not_count_the_base_changes(
    repository: Path, linked: bool, conflict: bool
) -> None:
    root = merging(repository, "main", linked, conflict)
    small, reason = change_size.size_verdict(root)
    assert small, reason
    assert reason.startswith("1 file, ")


@pytest.mark.parametrize("linked", [False, True], ids=["main checkout", "linked"])
def test_a_merge_of_another_branch_in_progress_counts_its_files(
    repository: Path, linked: bool
) -> None:
    root = merging(repository, "other", linked, False)
    assert change_size.size_verdict(root) == (
        False,
        "it adds, deletes or renames the file other.py",
    )


def test_a_branch_that_installs_hard_eng_names_the_install_as_the_reason(
    repository: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    sized_branch(repository)
    (repository / ".agents").mkdir()
    (repository / ".agents/biome.json").write_text("{}\n")
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text("{}\n")
    commit(repository, "Install Hard Eng")
    assert change_size.size_verdict(repository) == (
        False,
        "this branch installs Hard Eng",
    )
    assert not change_size.plan_not_needed(repository)
    assert "Size: big, because this branch installs Hard Eng; a plan is needed." in (
        capsys.readouterr().out
    )


def test_a_change_with_no_installed_path_starts_no_update_lookup(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (repository / ".hooks").mkdir()
    (repository / ".hooks/hard-eng-source.json").write_text(
        '{"revision": "' + "a" * 40 + '"}\n'
    )
    sized_branch(repository)
    edit(repository, "a.py", 2)
    started: list[str] = []
    real = subprocess.check_output

    def spy(command: list[str], *arguments: object, **options: object) -> str:
        started.append(command[1])
        return real(command, *arguments, **options)

    monkeypatch.setattr(subprocess, "check_output", spy)
    assert change_size.size_verdict(repository) == (True, "1 file, 4 changed lines")
    assert not {"status", "show", "log"}.intersection(started)
    started.clear()
    edit(repository, "a.py", 1)
    (repository / "AGENTS.md").write_text("rules\n")
    change_size.size_verdict(repository)
    assert len({"status", "show", "log"}.intersection(started)) <= 2

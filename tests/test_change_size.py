import os
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

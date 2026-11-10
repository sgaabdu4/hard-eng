import os
from collections.abc import Callable
from functools import partial
from pathlib import Path

import change_size
import pytest
from conftest import commit, git
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

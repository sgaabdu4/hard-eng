"""A `.gitleaksignore` entry names the file that Gitleaks reads, in the spelling Gitleaks accepts."""

import pytest
from gitleaks_entries import named_path, outside


@pytest.mark.parametrize(
    ("entry", "path"),
    [
        ("src/a.py:github-pat:1", "src/a.py"),
        ("src\\a.py:github-pat:1", "src/a.py"),
        ("0123456789abcdef0123456789abcdef01234567:src/a.py:github-pat:1", "src/a.py"),
        ("0123456789abcdef0123456789abcdef01234567:src\\a.py:github-pat:1", "src/a.py"),
    ],
)
def test_the_path_of_an_entry_uses_the_separator_that_gitleaks_reads(
    entry: str, path: str
) -> None:
    assert named_path(entry) == path


def test_a_backslash_path_that_leaves_the_repository_is_outside() -> None:
    assert outside("..\\secret.py:github-pat:1")

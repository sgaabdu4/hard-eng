"""A `.gitleaksignore` entry names the file that Gitleaks reads, in the spelling Gitleaks accepts."""

from pathlib import Path

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


def test_a_backslash_entry_for_a_generated_file_is_judged_like_the_slash_entry(
    tmp_path: Path,
) -> None:
    """Gitleaks reads `docs\\gen\\secret.txt` as `docs/gen/secret.txt`, so the judge must find the same fingerprint and the same generated file."""
    from test_ignore_file_holes import KEY, RULE
    from test_strict_refusals import judged, project

    files = {
        "docs/gen/secret.txt": KEY,
        ".gitattributes": "docs/gen/secret.txt linguist-generated=true\n",
    }
    root = project(tmp_path, files)
    assert judged(root, f"docs/gen/secret.txt:{RULE}:1") == ""
    assert judged(root, f"docs\\gen\\secret.txt:{RULE}:1") == ""

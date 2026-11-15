"""The full check skips the changed-file comment check and the added-line switch-off scan, so its whole-project pass must refuse every case they refuse."""

import functools
import re
from collections.abc import Callable
from pathlib import Path

import comments
import pytest
import test_comments
import test_comments_push_range
import test_swift
from conftest import commit, init

SOURCES = (test_comments, test_comments_push_range, test_swift)
FINDING = re.compile(r"([^\s;]+:\d+) (?:adds|holds) ([^;\n]+)")
LOSS = re.compile(r"tests lose \d+ assertion lines net")
CONFIG = ".gitleaks.toml"


def findings(message: str) -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for place, what in FINDING.findall(message):
        name = place.rsplit(":", 1)[0]
        found.add((name, "") if name.endswith(CONFIG) else (place, what.strip()))
    return found | {("loss", text) for text in LOSS.findall(message)}


def through_the_full_check(original: Callable[..., None]) -> Callable[..., None]:
    def run(root: Path, base: str | None = None, *rest: bool, **named: bool) -> None:
        try:
            original(root, base, *rest, **named)
        except ValueError as refused:
            wanted = findings(str(refused))
            if wanted:
                with pytest.raises(ValueError) as full:
                    comments.validate_rules(root, base, True, True)
                assert wanted <= findings(str(full.value))
            raise

    return run


def with_the_full_check_beside_each_refusal(
    test: Callable[..., None],
) -> Callable[..., None]:
    @functools.wraps(test)
    def run(*args: object, **named: object) -> None:
        with pytest.MonkeyPatch.context() as patch:
            for source in SOURCES:
                for name in ("validate_comments", "validate_suppressions"):
                    if hasattr(source, name):
                        patch.setattr(
                            source,
                            name,
                            through_the_full_check(getattr(comments, name)),
                        )
            test(*args, **named)

    return run


FORMS = [
    ("a.py", "x = 1  # no" + "qa\n"),
    ("a.ts", "// @ts-" + "ignore\nconst a = 1;\n"),
    ("a.md", "see gitleaks" + ":allow here\n"),
    ("a.yml", "key: x  # gitleaks" + ":allow\n"),
    ("a.json", '{"k": "gitleaks' + ':allow"}\n'),
    ("a.txt", "no" + "semgrep here\n"),
    ("a.py", "# first\n# second\nx = 1\n"),
    ("a.sh", "echo\n# first\n# second\n"),
    (".gitleaksignore", "abc:config.yml:generic-api-key:1\n"),
    (".semgrepignore", "src/\n"),
]


def refused_files(check: Callable[[], None]) -> set[str]:
    try:
        check()
    except ValueError as refused:
        return {place.rsplit(":", 1)[0] for place, _ in FINDING.findall(str(refused))}
    return set()


@pytest.mark.parametrize("folder", ["", ".hooks/", ".agents/", ".claude/", "gen/"])
@pytest.mark.parametrize(("name", "text"), FORMS)
def test_both_checks_refuse_the_same_files_in_owned_exempt_and_generated_folders(
    tmp_path: Path, folder: str, name: str, text: str
) -> None:
    """The exempt folders, generated output and files that are not source files get the same answer from both checks."""
    root = tmp_path / "repo"
    init(root)
    (root / "README.md").write_text("fixture\n")
    (root / ".gitattributes").write_text("gen/** linguist-generated=true\n")
    commit(root, "baseline")
    (root / folder / name).parent.mkdir(parents=True, exist_ok=True)
    (root / folder / name).write_text(text)

    def changed() -> None:
        comments.validate_comments(root, "HEAD")
        comments.validate_suppressions(root, "HEAD")

    def full() -> None:
        comments.validate_rules(root, "HEAD", True, True)

    assert refused_files(changed) == refused_files(full)


for source in SOURCES:
    prefix = source.__name__.removeprefix("test_")
    for name, function in vars(source).items():
        if name.startswith("test_") and callable(function):
            registered = with_the_full_check_beside_each_refusal(function)
            globals()[f"test_{prefix}_{name.removeprefix('test_')}"] = registered

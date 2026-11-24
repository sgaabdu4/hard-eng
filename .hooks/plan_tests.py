"""Whether a test that a plan names as `path::name` exists: one definition form per file kind."""

import re
from pathlib import Path, PurePosixPath

from plans import CHECKBOX_REST, _is_test, line_references, plan_status
from source_scan import code_without_comments

ACCEPTANCE_HEADING = re.compile(r"(?m)^## Acceptance \+ steps\s*$")
NEXT_HEADING = re.compile(r"(?m)^## ")


def acceptance_span(content: str) -> tuple[int, int] | None:
    """Where `## Acceptance + steps` holds its lines; None when the plan has no such heading."""
    heading = ACCEPTANCE_HEADING.search(content)
    if heading is None:
        return None
    end = NEXT_HEADING.search(content, heading.end())
    return heading.end(), end.start() if end else len(content)


def acceptance_rows(content: str) -> list[tuple[int, list[tuple[str, str]]]]:
    """Each acceptance checkbox of a plan as its line number and its `path::test` names, read without the section and N/A rules that `plan_sections` holds, so an old plan of any form has its rows."""
    span = acceptance_span(content)
    if span is None:
        return []
    first = content.count("\n", 0, span[0]) + 1
    return [
        (first + offset, line_references(found[1]))
        for offset, line in enumerate(content[span[0] : span[1]].splitlines())
        if (found := CHECKBOX_REST.match(line))
    ]


def repo_paths(root: Path, text: str) -> set[str]:
    """The names a plan's path can match in a list of changed files: its normal form, each parent folder, and the real path beneath the root."""
    rel = PurePosixPath(text)
    paths = {
        rel.as_posix(),
        *(parent.as_posix() for parent in rel.parents if parent != PurePosixPath(".")),
    }
    try:
        paths.add((root / text).resolve().relative_to(root.resolve()).as_posix())
    except ValueError:
        pass
    return paths


HASH_COMMENT_SUFFIXES = {".py", ".rb", ".sh", ".bash", ".zsh", ".pl", ".ex", ".exs"}


def uncommented(file: Path) -> str:
    """The file's text without comments, which cannot define a test; Rust strings hold no interpolation, so every Rust comment is found."""
    text = file.read_text()
    if file.suffix == ".rs":
        return code_without_comments(text, ".rs")
    marker = "#" if file.suffix in HASH_COMMENT_SUFFIXES else "//"
    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith(marker)
    )


RUST_TEST_ATTRIBUTES = (
    "test",
    "rstest",
    "test_case",
    "test_matrix",
    "wasm_bindgen_test",
    "quickcheck",
    "gtest",
)
RUST_CHAR = r"'(?:\\.|[^'\\])'"
RUST_ATOM = rf'"(?:\\.|[^"\\])*"|{RUST_CHAR}|\'(?!(?:\\.|[^\'\\])\')|[^\]\["\']'
RUST_NESTED = rf"(?:{RUST_ATOM}|\[(?:{RUST_ATOM})*\])*"
RUST_ATTRIBUTE_BODY = rf"(?:{RUST_ATOM}|\[{RUST_NESTED}\])*"
RUST_TEST_NAME = rf"\s*(?:\w+::)*(?:{'|'.join(RUST_TEST_ATTRIBUTES)})\s*"
# The match starts only where an item can start and takes the first test attribute, so a stack is read once.
RUST_TEST = (
    rf"(?:\A|[;{{}}])\s*(?:#!\[{RUST_ATTRIBUTE_BODY}\]\s*)*"
    rf"(?:#\[(?!{RUST_TEST_NAME}[\](]){RUST_ATTRIBUTE_BODY}\]\s*)*"
    rf"#\[{RUST_TEST_NAME}(?:\({RUST_ATTRIBUTE_BODY}\))?\s*\]\s*"
    rf"(?:#\[{RUST_ATTRIBUTE_BODY}\]\s*)*"
    r"(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+"
)


def names_tests(path: PurePosixPath) -> bool:
    """Whether a plan's `path::name` can name a test there; Rust unit tests live in src/."""
    return _is_test(path) or path.suffix == ".rs"


def missing_tests(root: Path, references: list[tuple[str, str]]) -> list[str]:
    missing = []
    texts: dict[Path, str] = {}
    for path, name in references:
        file = (root / path).resolve()
        quoted = rf"[\"'`]{re.escape(name)}[\"'`]"
        definition = {
            ".py": rf"\bdef\s+{re.escape(name)}\s*\(",
            ".swift": rf"\bfunc\s+{re.escape(name)}\s*\(|{quoted}",
            ".rs": rf"{RUST_TEST}{re.escape(name)}\s*[<(]",
        }.get(file.suffix, quoted)
        if not (
            file.is_relative_to(root.resolve())
            and names_tests(PurePosixPath(path))
            and file.is_file()
            and re.search(
                definition,
                texts[file]
                if file in texts
                else texts.setdefault(file, uncommented(file)),
            )
        ):
            missing.append(f"{path}::{name}")
    return missing


def unchanged_plan_test_problem(
    root: Path, paths: list[Path], judged: list[Path], changed: set[str]
) -> None:
    """A change to a test file also judges every other Complete plan that names a test in it."""
    tests = [name for name in changed if names_tests(PurePosixPath(name))]
    for path in paths:
        if path in judged:
            continue
        content = path.read_text()
        if not tests or not any(name in content for name in tests):
            continue
        if plan_status(content) != "Complete":
            continue
        named = [
            (number, reference)
            for number, references in acceptance_rows(content)
            for reference in references
            if repo_paths(root, reference[0]) & changed
        ]
        if missing := missing_tests(root, [reference for _, reference in named]):
            lines = {
                f"{path}::{name}": number for number, (path, name) in reversed(named)
            }
            raise ValueError(
                f"{path.relative_to(root)}: acceptance names tests that do not exist: "
                + ", ".join(f"{found} (line {lines[found]})" for found in missing)
                + ". Update that plan to the replacement test"
            )

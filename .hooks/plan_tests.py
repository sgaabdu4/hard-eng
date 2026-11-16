"""Whether a test that a plan names as `path::name` exists: one definition form per file kind."""

import re
from pathlib import Path, PurePosixPath

from plans import _is_test

HASH_COMMENT_SUFFIXES = {".py", ".rb", ".sh", ".bash", ".zsh", ".pl", ".ex", ".exs"}


def uncommented(file: Path) -> str:
    """The file's text without whole-line comments, which cannot define a test."""
    marker = "#" if file.suffix in HASH_COMMENT_SUFFIXES else "//"
    return "\n".join(
        line
        for line in file.read_text().splitlines()
        if not line.lstrip().startswith(marker)
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
RUST_GAP = r"(?:\s|//[^\n]*)*"
RUST_TEST = (
    rf"#\[(?:\w+::)*(?:{'|'.join(RUST_TEST_ATTRIBUTES)})(?:\({RUST_ATTRIBUTE_BODY}\))?\]{RUST_GAP}"
    rf"(?:#\[{RUST_ATTRIBUTE_BODY}\]{RUST_GAP})*"
    r"(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?fn\s+"
)


def names_tests(path: PurePosixPath) -> bool:
    """Whether a plan's `path::name` can name a test there; Rust unit tests live in src/."""
    return _is_test(path) or path.suffix == ".rs"


def missing_tests(root: Path, references: list[tuple[str, str]]) -> list[str]:
    missing = []
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
            and re.search(definition, uncommented(file))
        ):
            missing.append(f"{path}::{name}")
    return missing

"""Code comments are none by default; a changed source file may hold one-line comments only."""

import io
import re
import tokenize
from pathlib import Path

from gate_config import changed_files, generated_sources

HASH = {".py", ".pyi", ".sh", ".bash", ".zsh", ".rb"}
SLASH = {
    ".dart", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx",
    ".rs", ".go", ".swift", ".kt", ".kts", ".java", ".scala", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".php",
}  # fmt: skip
DIRECTIVE = re.compile(
    r"^(#!|#\s*-\*-|//\s*ignore(_for_file)?:|///\s*<reference|//go:|//\s*\+build"
    r"|//\s*#(region|endregion))|(eslint|prettier|biome|jscpd|istanbul|c8|coverage)[-:]"
    r"|@ts-|noqa|type:\s*ignore|pyright:|pylint:|mypy:|pragma|fmt:\s*(off|on|skip)"
    r"|isort:|shellcheck|nolint|NOSONAR"
)


def python_comment_lines(text: str) -> set[int] | None:
    """Full-line comments by tokenizer, so `#` inside strings is not a comment."""
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        return {
            token.start[0]
            for token in tokens
            if token.type == tokenize.COMMENT and token.line.strip().startswith("#")
        }
    except (tokenize.TokenError, SyntaxError):
        return None


def slash_comment_lines(lines: list[str]) -> set[int]:
    found: set[int] = set()
    inside = False
    for number, line in enumerate(lines, 1):
        text = line.strip()
        if inside or text.startswith(("//", "/*")):
            found.add(number)
            inside = (inside or text.startswith("/*")) and "*/" not in text
    return found


def comment_blocks(path: Path) -> list[tuple[int, int]]:
    """(first line, length) of each comment block longer than one line."""
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    comments = python_comment_lines(text) if path.suffix in {".py", ".pyi"} else None
    if comments is None:
        comments = (
            slash_comment_lines(lines)
            if path.suffix in SLASH
            else {n for n, line in enumerate(lines, 1) if line.lstrip().startswith("#")}
        )
    blocks: list[tuple[int, int]] = []
    start, length = 0, 0
    for number, line in enumerate([*lines, ""], 1):
        if number in comments and not DIRECTIVE.search(line.strip()):
            start, length = (start, length + 1) if length else (number, 1)
            continue
        if length > 1:
            blocks.append((start, length))
        length = 0
    return blocks


def validate_comments(root: Path, base: str) -> None:
    names = changed_files(root, base)
    if names is None:
        raise ValueError(
            "Cannot verify comment scope; fetch or supply a valid Git --base"
        )
    sources = sorted(
        name
        for name in names
        if Path(name).suffix in HASH | SLASH
        and (root / name).is_file()
        and not (root / name).is_symlink()
    )
    skipped = generated_sources(root, sources)
    found = [
        f"{name}:{start} holds a {length}-line comment block"
        for name in sources
        if name not in skipped
        for start, length in comment_blocks(root / name)
    ]
    if found:
        raise ValueError(
            "Code comments are none by default: delete each block below, and add one "
            "terse line of why only where naming, types, structure or a test cannot "
            "carry a needed non-obvious constraint. " + "; ".join(found)
        )

"""Code comments are none by default; a changed source file may hold one-line comments only.

Installed agent skills under .agents/ are vendored tooling and are not checked.
"""

import io
import re
import tokenize
from pathlib import Path

from gate_config import changed_files, generated_sources

HASH = {".py", ".pyi", ".sh", ".bash", ".zsh"}
SLASH = {
    ".dart", ".js", ".mjs", ".cjs", ".jsx", ".ts", ".mts", ".cts", ".tsx",
    ".rs", ".go", ".swift", ".kt", ".kts", ".java", ".scala", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".php",
}  # fmt: skip
DIRECTIVE = re.compile(
    r"^(#!|#\s*-\*-|//\s*ignore(_for_file)?:|///\s*<reference|//go:|//\s*\+build"
    r"|//\s*#(region|endregion))|(eslint|prettier|biome|jscpd|istanbul|c8|coverage)[-:]"
    r"|@ts-|noqa|type:\s*ignore|pyright:|pylint:|mypy:|pragma|fmt:\s*(off|on|skip)"
    r"|isort:|shellcheck|nolint|NOSONAR|nosemgrep|nosec"
)
# Delimiters, blank comment lines, JSDoc type tags and rustdoc section headings carry no narration.
NEUTRAL = re.compile(
    DIRECTIVE.pattern
    + r"|^(/\*+|\*+/|/\*+\s*\*+/|\*|/{2,}!?|#+)$"
    + r"|^(/\*+|\*|/{2,})\s*@(param|arg|argument|returns?|type|typedef|template|property"
    + r"|prop|callback|satisfies|import|overload|this|enum|extends|augments|implements)\b"
    + r"|^/{3}!?\s*#\s*(Errors|Panics|Safety|Examples?)$"
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


SINGLE_QUOTE_STRINGS = {
    ".dart",
    ".js",
    ".mjs",
    ".cjs",
    ".jsx",
    ".ts",
    ".mts",
    ".cts",
    ".tsx",
    ".php",
}
CHARACTER = re.compile(r"'(\\.[^']{0,8}|[^'\\\n])'")
HEREDOC = re.compile(r"(?<!<)<<(?!<)[-~]?\s*(['\"]?)([A-Za-z_]\w*)\1")


def string_end(text: str, index: int, quote: str) -> int:
    """Index just past the string that opens at index with quote."""
    while index < len(text):
        if text[index] == "\\" and quote != "`":
            index += 2
        elif text.startswith(quote, index):
            return index + len(quote)
        else:
            index += 1
    return len(text)


def string_start(text: str, index: int, suffix: str) -> str | None:
    """The quote that opens a string at index, or None for code and character literals."""
    triple = text[index : index + 3]
    if triple in {'"""', "'''"} and (triple == '"""' or suffix in SINGLE_QUOTE_STRINGS):
        return triple
    if text[index] in '"`' or (text[index] == "'" and suffix in SINGLE_QUOTE_STRINGS):
        return text[index]
    return None


def slash_comment_lines(text: str, suffix: str) -> set[int]:
    """Lines that open with a comment, or begin inside a block comment, outside strings."""
    found: set[int] = set()
    index, line, blank = 0, 1, True
    while index < len(text):
        character = text[index]
        if character == "\n":
            index, line, blank = index + 1, line + 1, True
        elif character in " \t\r":
            index += 1
        elif text.startswith(("//", "/*"), index):
            close = text.find("\n" if text[index + 1] == "/" else "*/", index + 2)
            close = len(text) if close < 0 else close + (text[index + 1] == "*") * 2
            spanned = text.count("\n", index, close)
            found |= {line} if blank or spanned else set()
            found |= set(range(line + 1, line + 1 + spanned))
            line += spanned
            index, blank = close, False
        elif (quote := string_start(text, index, suffix)) is not None:
            close = string_end(text, index + len(quote), quote)
            line += text.count("\n", index, close)
            index, blank = close, False
        else:
            literal = CHARACTER.match(text, index) if character == "'" else None
            index, blank = (literal.end() if literal else index + 1), False
    return found


def hash_comment_lines(lines: list[str]) -> set[int]:
    """Full-line `#` comments outside shell strings and heredocs."""
    found: set[int] = set()
    heredoc: str | None = None
    quote: str | None = None
    for number, line in enumerate(lines, 1):
        if heredoc is not None:
            heredoc = None if line.strip() == heredoc else heredoc
            continue
        if quote is None and line.lstrip().startswith("#"):
            found.add(number)
            continue
        code = ""
        for character in line:
            if quote is None and character == "#" and (not code or code[-1].isspace()):
                break
            if character in "\"'" and (quote is None or quote == character):
                quote = None if quote else character
            code += character
        opened = HEREDOC.search(code) if quote is None else None
        heredoc = opened.group(2) if opened else None
    return found


def comment_blocks(path: Path) -> list[tuple[int, int]]:
    """(first narration line, narration lines) of each block with more than one."""
    text = path.read_text(errors="replace")
    lines = text.splitlines()
    comments = python_comment_lines(text) if path.suffix in {".py", ".pyi"} else None
    if comments is None:
        comments = (
            slash_comment_lines(text, path.suffix)
            if path.suffix in SLASH
            else hash_comment_lines(lines)
        )
    blocks: list[tuple[int, int]] = []
    start, length = 0, 0
    for number, line in enumerate([*lines, ""], 1):
        if number in comments:
            if not NEUTRAL.search(line.strip()):
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
        and not name.startswith(".agents/")
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

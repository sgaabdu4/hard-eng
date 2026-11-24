"""HE-UI-SOURCE for the whole project: every UI file under `ui_paths` is judged, old lines included."""

import json
import re
from fnmatch import fnmatchcase
from pathlib import Path, PurePosixPath

from flutter_screens import flutter_packages
from generated_marks import generated_sources
from plans import _is_test as is_test_path
from ui_exempt import code_of, exemption
from ui_library import (
    BASE_STEP,
    base_element_hits,
    index_findings,
    library_parts,
    role_findings,
)
from ui_raw import (
    COLOUR_STEP,
    PALETTE_STEP,
    SIZE_STEP,
    STYLE_SUFFIXES,
    raw_value_hits,
)
from ui_rules import (
    DART_COLOUR,
    SWIFT_COLOUR,
    UNOWNED,
    is_theme_path,
)
from ui_tokens import (
    DESIGN_NAME,
    colours_in,
    length_px,
    token_facts,
    token_findings,
)

WEB_SUFFIXES = (
    ".css",
    ".scss",
    ".less",
    ".html",
    ".vue",
    ".svelte",
    ".astro",
    ".jsx",
    ".tsx",
    ".js",
    ".ts",
)
NATIVE_SUFFIXES = (".dart", ".swift")
NAMED_DART_COLOUR = re.compile(r"Colors\.\w+")
DART_RAW = re.compile(DART_COLOUR.pattern + r"|\bColor(?:\.new)?\(\s*0[xX]")
SYSTEM_COLOURS = "red|orange|yellow|green|mint|teal|cyan|blue|indigo|purple|pink|brown|gray|black|white"
SWIFT_RAW = re.compile(
    SWIFT_COLOUR.pattern
    + rf"|\b(?:UI|NS)?Color\.(?:{SYSTEM_COLOURS})\b"
    + r"|\.(?:foregroundColor|foregroundStyle|background|tint|fill|stroke|accentColor"
    + rf"|border|shadow)\(\s*\.(?:{SYSTEM_COLOURS})\b"
)


def inside(name: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(name, pattern) for pattern in patterns)


def judged_names(root: Path, texts: dict[str, str], ui_paths: list[str]) -> list[str]:
    names = [
        name
        for name in texts
        if name.endswith(WEB_SUFFIXES + NATIVE_SUFFIXES)
        and not name.startswith(UNOWNED)
        and inside(name, ui_paths)
        and not is_test_path(PurePosixPath(name))
    ]
    skipped = generated_sources(root, names)
    return [name for name in names if name not in skipped]


TOKEN_BLOCK = re.compile(
    r"\s*(?:@media[^{}]*\{\s*)?(?::root|@theme(?:\s+\w+)?)\s*\{(?:\s*--[\w-]+\s*:[^;{}]*;)*\s*\}"
    r"(?:\s*\})?"
)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_IMPORT = re.compile(r"@import[^;]*;")
THEME_COLOUR = re.compile(r"--color-([\w-]+)\s*:")
THEME_BLOCK = re.compile(r"@theme[^{]*\{([^}]*)\}")
CONFIG_VALUE_END = re.compile(r"[,\n}]")


def only_custom_properties(name: str, text: str) -> bool:
    if not name.endswith(STYLE_SUFFIXES):
        return False
    rest = CSS_IMPORT.sub("", CSS_COMMENT.sub("", text))
    return bool(rest.strip()) and not TOKEN_BLOCK.sub("", rest).strip()


TOKEN_SUFFIXES = (*STYLE_SUFFIXES, ".ts", ".js", ".mjs", ".cjs")


def token_file(name: str, text: str) -> bool:
    return only_custom_properties(name, text) or (
        name.endswith(TOKEN_SUFFIXES) and is_theme_path(name)
    )


def config_value(rest: str) -> str:
    """The value after a key: a whole braced block, else the text up to the next comma, line end or brace."""
    if not rest.lstrip().startswith("{"):
        return CONFIG_VALUE_END.split(rest, maxsplit=1)[0]
    depth = 0
    for position, char in enumerate(rest):
        depth += (char == "{") - (char == "}")
        if char == "}" and depth == 0:
            return rest[:position]
    return rest


CONFIG_TOKEN = re.compile(
    r"(?P<key>['\"]?[\w-]+['\"]?)\s*:\s*(?P<open>\{)?|(?P<close>\})"
)


def config_colour_names(text: str) -> set[str]:
    """Each palette name as its path of nested keys down to a leaf that holds a literal colour (blue-50)."""
    code = code_of(text)
    names: set[str] = set()
    path: list[str] = []
    for token in CONFIG_TOKEN.finditer(code):
        if token["close"]:
            path = path[:-1]
            continue
        key = token["key"].strip("'\"")
        if token["open"]:
            path.append(key)
        elif colours_in(config_value(code[token.end() :])):
            full = path if key == "DEFAULT" else [*path, key]
            if "colors" in full:
                full = full[len(full) - full[::-1].index("colors") :]
            if full:
                names.add("-".join(full))
    return names


def defined_colours(texts: dict[str, str]) -> set[str]:
    names: set[str] = set()
    for name, text in texts.items():
        if PurePosixPath(name).name.startswith("tailwind.config."):
            names |= config_colour_names(text)
        elif name.endswith(STYLE_SUFFIXES):
            blocks = (
                text if token_file(name, text) else "".join(THEME_BLOCK.findall(text))
            )
            names |= set(THEME_COLOUR.findall(blocks))
    return names


def token_values(texts: dict[str, str]) -> set[tuple[str, str | float]]:
    """The colours and lengths of the token files as values, so 28px equals 1.75rem."""
    facts = token_facts(
        [
            text
            for name, text in texts.items()
            if name.endswith(TOKEN_SUFFIXES) and token_file(name, text)
        ]
    )
    values: set[tuple[str, str | float]] = {("c", colour) for colour in facts.colours}
    values |= {("l", length) for length in facts.lengths}
    return values


def is_token_literal(hit: str, tokens: set[tuple[str, str | float]]) -> bool:
    typed = hit.rsplit(": ", 1)[-1]
    length = length_px(typed)
    return any(("c", colour) in tokens for colour in colours_in(typed)) or (
        length is not None and ("l", length) in tokens
    )


def shown_colour(line: str, hit: re.Match[str]) -> str:
    named = NAMED_DART_COLOUR.match(line, hit.start())
    return named[0] if named else hit[0].strip()


BLOCK_COMMENT = re.compile(
    r"(?:^|(?<=\s))//[^\n]*|/\*.*?\*/|<!--.*?-->", re.DOTALL | re.MULTILINE
)
LINE_COMMENT_START = re.compile(r"\s*//")


def blank_comment(hit: re.Match[str]) -> str:
    """A block comment becomes its line breaks, unless a quote is open before it on its line; a line comment is kept as it is, so a /* inside it opens nothing."""
    before = hit.string[: hit.start()].rsplit("\n", 1)[-1]
    if hit[0].startswith("//") or any(before.count(quote) % 2 for quote in "'\"`"):
        return hit[0]
    return "\n" * hit[0].count("\n")


def code_lines(text: str) -> list[tuple[int, str]]:
    """The lines that hold code: block comments are cut with their line breaks kept, and a whole `//` line is skipped."""
    return [
        (number, line)
        for number, line in enumerate(
            BLOCK_COMMENT.sub(blank_comment, text).splitlines(), 1
        )
        if line.strip() and not LINE_COMMENT_START.match(line)
    ]


def native_findings(name: str, lines: list[tuple[int, str]]) -> list[str]:
    if is_theme_path(name):
        return []
    pattern = DART_RAW if name.endswith(".dart") else SWIFT_RAW
    return [
        f"{name}:{number}: a colour typed in the file ({shown_colour(line, hit)}). {COLOUR_STEP}"
        for number, line in lines
        if (hit := pattern.search(line))
    ]


def file_findings(
    name: str,
    text: str,
    library: list[str],
    defined: set[str],
    tokens: set[tuple[str, str | float]],
) -> list[str]:
    kind = exemption(name, text)
    if kind == "pdf":
        return []
    lines = code_lines(text)
    if name.endswith(NATIVE_SUFFIXES):
        return native_findings(name, lines)
    found: list[str] = []
    if not token_file(name, text):
        for number, what, hit in raw_value_hits(name, lines, defined):
            if kind and what != "palette" and is_token_literal(hit, tokens):
                continue
            step = {"colour": COLOUR_STEP, "palette": PALETTE_STEP}.get(what, SIZE_STEP)
            noun = "size" if what == "size" else "colour"
            found.append(f"{name}:{number}: a {noun} typed in the file ({hit}). {step}")
    if kind != "email" and not inside(name, library):
        found += [
            f"{name}:{number}: a base element ({tag}) outside the library. {BASE_STEP}"
            for number, tag in base_element_hits(lines)
        ]
    return found


WIDGET_WORD = re.compile(r"Widget\b")
COMPONENT_SUFFIXES = (".tsx", ".jsx", ".vue", ".svelte", ".astro", *STYLE_SUFFIXES)


def coverage_findings(
    root: Path, texts: dict[str, str], ui_paths: list[str]
) -> list[str]:
    libs = flutter_packages(root)
    names = [
        name
        for name, text in texts.items()
        if not name.startswith(UNOWNED)
        and not inside(name, ui_paths)
        and not is_test_path(PurePosixPath(name))
        and (
            name.endswith(COMPONENT_SUFFIXES)
            or (
                name.endswith(".dart")
                and WIDGET_WORD.search(text)
                and any(name.startswith(f"{base}lib/") for base in libs)
            )
        )
        and exemption(name, text) != "pdf"
    ]
    skipped = generated_sources(root, names)
    return [
        f"{name}: {'a stylesheet' if name.endswith(STYLE_SUFFIXES) else 'a component file'} outside ui_paths. If users receive it, add its folder to ui_paths in hard-eng.gates.json; if it is only a preview, remove it from git and list its folder in .gitignore"
        for name in names
        if name not in skipped
    ]


def setting_findings(
    root: Path, texts: dict[str, str], ui_paths: list[str], library: list[str]
) -> list[str]:
    if not library:
        value = default_library(root, list(texts), ui_paths) or ["<folder>/*"]
        return [
            f'hard-eng.gates.json: ui_library is missing or empty. Add shipping "ui_library": {json.dumps(value)}, the folder of the shared parts; screens stay outside it'
        ]
    found: list[str] = []
    for entry in library:
        matched = [name for name in texts if fnmatchcase(name, entry)]
        if not matched:
            found.append(
                f"hard-eng.gates.json: ui_library entry {entry} matches no file"
            )
        elif not all(inside(name, ui_paths) for name in matched):
            found.append(
                f"hard-eng.gates.json: ui_library entry {entry} is outside ui_paths"
            )
    return found


def library_covers_screens(
    root: Path, texts: dict[str, str], ui_paths: list[str], library: list[str]
) -> list[str]:
    outside = [
        name
        for name in judged_names(root, texts, ui_paths)
        if not inside(name, library)
    ]
    if library and not outside:
        return [
            "hard-eng.gates.json: ui_library holds every UI file of ui_paths; screens must lie outside the library"
        ]
    return []


def default_library(root: Path, names: list[str], ui_paths: list[str]) -> list[str]:
    """The `ui` folders among the project's UI files as library entries, when they pass the library rules; else none."""
    texts = dict.fromkeys(names, "")
    entries = sorted(
        {
            "/".join(parts[: parts.index("ui") + 1]) + "/*"
            for name in names
            if inside(name, ui_paths)
            and "ui" in (parts := PurePosixPath(name).parts[:-1])
        }
    )
    if not entries or setting_findings(root, texts, ui_paths, entries):
        return []
    return [] if library_covers_screens(root, texts, ui_paths, entries) else entries


def compared_token_file(name: str, text: str, ui_paths: list[str]) -> bool:
    if PurePosixPath(name).name.startswith("tailwind.config."):
        return True
    return (
        inside(name, ui_paths)
        and not is_test_path(PurePosixPath(name))
        and ((name.endswith(".dart") and is_theme_path(name)) or token_file(name, text))
    )


def ui_findings_whole(
    root: Path, texts: dict[str, str], ui_paths: list[str], library: list[str]
) -> list[str]:
    defined = defined_colours(texts)
    tokens = token_values(texts)
    token_texts = [
        texts[name]
        for name in texts
        if compared_token_file(name, texts[name], ui_paths)
    ]
    parts = [
        part
        for name, text in texts.items()
        if inside(name, library)
        for part in library_parts(name, text)
    ]
    return (
        setting_findings(root, texts, ui_paths, library)
        + library_covers_screens(root, texts, ui_paths, library)
        + coverage_findings(root, texts, ui_paths)
        + role_findings(parts)
        + index_findings(texts, library)
        + token_findings(texts.get(DESIGN_NAME), token_texts)
        + [
            item
            for name in judged_names(root, texts, ui_paths)
            for item in file_findings(name, texts[name], library, defined, tokens)
        ]
    )

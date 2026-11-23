"""HE-UI-SOURCE: web base elements live only in the shared library."""

import re
from fnmatch import fnmatchcase
from pathlib import Path

BASE_ELEMENTS = ("button", "input", "select", "textarea", "dialog")
_NAMES = "|".join(BASE_ELEMENTS)
BASE_ELEMENT = re.compile(rf"<({_NAMES})\b|createElement\(\s*(['\"])({_NAMES})\2")
BASE_STEP = "Make it a part of the shared library and use that part"


def base_element_hits(lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    return [
        (number, f"<{hit[1]}" if hit[1] else f"createElement('{hit[3]}')")
        for number, text in lines
        for hit in BASE_ELEMENT.finditer(text)
    ]


FIXED_ROLES = {
    "password field": ("PasswordField", "PasswordInput"),
    "search field": ("SearchField", "SearchBar", "SearchInput"),
    "empty state": ("EmptyState",),
    "error message": ("ErrorMessage", "FieldError"),
    "destructive confirm": ("ConfirmDialog", "ConfirmationDialog"),
}
COMPONENT_EXPORT = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function|const|class)\s+([A-Z]\w*)",
    re.MULTILINE,
)
SCRIPT_EXPORT = re.compile(
    r"^export\s+(?:async\s+)?(?:function|const|class)\s+(\w+)", re.MULTILINE
)
DART_PART = re.compile(
    r"^class\s+([A-Z]\w*)(?:<[^>]+>)?\s+extends\s+\w*Widget\b", re.MULTILINE
)
FILE_PARTS = (".vue", ".svelte", ".astro")


def library_parts(name: str, text: str) -> list[str]:
    stem = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    if name.endswith(FILE_PARTS):
        return [stem]
    if name.endswith((".tsx", ".jsx")):
        return COMPONENT_EXPORT.findall(text)
    if name.endswith((".js", ".ts")):
        return SCRIPT_EXPORT.findall(text)
    if name.endswith(".dart"):
        return DART_PART.findall(text)
    return []


def role_findings(parts: list[str]) -> list[str]:
    found = []
    for role, words in FIXED_ROLES.items():
        holders = sorted(
            {part for part in parts if any(word in part for word in words)}
        )
        if len(holders) > 1:
            found.append(
                f"{role}: {len(holders)} library parts ({', '.join(holders)}). Keep one part for this control"
            )
    return found


INDEX_NAME = "UI-LIBRARY.md"
INDEX_HEAD = "# UI library\n\nOne section for each library entry of `ui_library`; one row for each part. Written by `python3 .hooks/hard-eng.py ui-library --write`; the use lines are written by hand.\n"
INDEX_ROW = re.compile(r"^- `([^`]+)` — ?(.*)$")
INDEX_SECTION = re.compile(r"^## (.+)$")


def expected_index(texts: dict[str, str], library: list[str]) -> dict[str, list[str]]:
    return {
        entry: sorted(
            {
                part
                for name, text in texts.items()
                if fnmatchcase(name, entry)
                for part in library_parts(name, text)
            }
        )
        for entry in library
    }


def read_index(text: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    section = ""
    for line in text.splitlines():
        if heading := INDEX_SECTION.match(line):
            section = heading[1].strip("`")
            found[section] = {}
        elif (row := INDEX_ROW.match(line)) and section:
            found[section][row[1]] = row[2].strip()
    return found


def index_text(
    texts: dict[str, str], library: list[str], old: dict[str, dict[str, str]]
) -> str:
    blocks = [INDEX_HEAD]
    for entry, parts in expected_index(texts, library).items():
        rows = "".join(
            f"- `{part}` — {old.get(entry, {}).get(part, '')}\n" for part in parts
        )
        blocks.append(f"## `{entry}`\n\n{rows}")
    return "\n".join(blocks)


def index_findings(texts: dict[str, str], library: list[str]) -> list[str]:
    if INDEX_NAME not in texts:
        return [
            f"{INDEX_NAME} is missing. Run `python3 .hooks/hard-eng.py ui-library --write`"
        ]
    old = read_index(texts[INDEX_NAME])
    found: list[str] = []
    for entry, parts in expected_index(texts, library).items():
        rows = old.get(entry, {})
        found += [
            f"{INDEX_NAME}: {part} is missing from {INDEX_NAME}"
            for part in parts
            if part not in rows
        ]
        found += [
            f"{INDEX_NAME} lists {part}, which no library file holds"
            for part in rows
            if part not in parts
        ]
        found += [
            f"{INDEX_NAME}: the use line of {part} is empty"
            for part in parts
            if part in rows and not rows[part]
        ]
    return found


def write_index(root: Path) -> int:
    from shipping import load_policy
    from whole_project import text_files

    policy = load_policy(root)
    texts = text_files(root)
    old = read_index(texts.get(INDEX_NAME, ""))
    (root / INDEX_NAME).write_text(
        index_text(texts, policy["ui_library"] if policy else [], old)
    )
    return 0

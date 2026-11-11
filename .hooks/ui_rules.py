"""HE-UI-SOURCE: added UI lines hold no every-property transition and no colour literal outside a theme file."""

import re
from pathlib import Path, PurePosixPath

from gate_config import generated_sources
from plans import _is_test as is_test_path

UNOWNED = (".hooks/", ".agents/", ".claude/")
THEME_WORDS = ("theme", "token", "color", "colour", "palette")
COMMENT_LINE = re.compile(r"^\s*(?://|/\*|<!--|\*(?:\s|/|$))")
TRANSITION_CLASS = re.compile(r"(?<![\w-])transition-all(?![\w-])")
TRANSITION_STYLE = re.compile(
    r"(?<!\w)transition(?:-property|Property)?[\"']?\s*:\s*[\"'`]?(?:[^;\"'`,]*,\s*)?all(?![\w-])"
)
TAILWIND_COLOUR = re.compile(
    r"-\[(?:#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F\w])"
    r"|(?:rgba?|hsla?|oklch)\()"
)
DART_COLOUR = re.compile(
    r"\bColor\(\s*0x|\bColor\.from(?:ARGB|RGBO)\(|\bColors\.(?!transparent\b)[A-Za-z]"
)
SWIFT_COLOUR = re.compile(r"\b(?:UI|NS)?Color\(\s*red:|#colorLiteral\(")
TRANSITION_STEP = (
    "List the properties that change, for example transition-[opacity,transform] "
    "or transition: opacity 150ms"
)
COLOUR_STEP = (
    "Use a colour of the theme, or add the colour to a theme or token file "
    "(a path that holds theme, token, color or palette)"
)


def is_theme_path(name: str) -> bool:
    path = PurePosixPath(name)
    lowered = [part.lower() for part in path.parts]
    return path.name.startswith("tailwind.config.") or any(
        word in part for part in lowered for word in THEME_WORDS
    )


def colour_pattern(name: str) -> re.Pattern[str]:
    if name.endswith(".dart"):
        return DART_COLOUR
    return SWIFT_COLOUR if name.endswith(".swift") else TAILWIND_COLOUR


def ui_findings(root: Path, candidates: dict[str, list[tuple[int, str]]]) -> list[str]:
    """Findings for the candidate lines of each UI file: every-property transitions and typed colours."""
    names = sorted(name for name in candidates if not name.startswith(UNOWNED))
    skipped = generated_sources(root, names)
    found: list[str] = []
    for name in names:
        if name in skipped or is_test_path(PurePosixPath(name)):
            continue
        colours = None if is_theme_path(name) else colour_pattern(name)
        for number, text in candidates[name]:
            if COMMENT_LINE.match(text):
                continue
            if TRANSITION_CLASS.search(text) or TRANSITION_STYLE.search(text):
                found.append(
                    f"{name}:{number}: a transition on every property. {TRANSITION_STEP}"
                )
            elif colours is not None and (hit := colours.search(text)):
                found.append(
                    f"{name}:{number}: a colour typed in the file ({hit[0].strip()}). {COLOUR_STEP}"
                )
    return found

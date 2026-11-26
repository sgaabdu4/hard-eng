"""HE-UI-SOURCE: raw colours and lengths typed in web, CSS and HTML files."""

import re

STYLE_SUFFIXES = (".css", ".scss", ".less")
HEX = r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})(?![\w-])"
HEX_VALUE = re.compile(rf"(?<!url\()(?<!url\(\")(?<!url\(')(?<![\w&/]){HEX}")
COLOUR_FUNCTION = re.compile(
    r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch|hwb)\((?!\s*var\()[^()]*(?:\([^()]*\)[^()]*)*\)?"
)
COLOUR_NAME = re.compile(
    r"(?<![\w-])(?:"
    "aliceblue|antiquewhite|aqua|aquamarine|azure|beige|bisque|black|blanchedalmond|blue|"
    "blueviolet|brown|burlywood|cadetblue|chartreuse|chocolate|coral|cornflowerblue|cornsilk|"
    "crimson|cyan|darkblue|darkcyan|darkgoldenrod|darkgray|darkgreen|darkgrey|darkkhaki|"
    "darkmagenta|darkolivegreen|darkorange|darkorchid|darkred|darksalmon|darkseagreen|"
    "darkslateblue|darkslategray|darkslategrey|darkturquoise|darkviolet|deeppink|deepskyblue|"
    "dimgray|dimgrey|dodgerblue|firebrick|floralwhite|forestgreen|fuchsia|gainsboro|ghostwhite|"
    "gold|goldenrod|gray|green|greenyellow|grey|honeydew|hotpink|indianred|indigo|ivory|khaki|"
    "lavender|lavenderblush|lawngreen|lemonchiffon|lightblue|lightcoral|lightcyan|"
    "lightgoldenrodyellow|lightgray|lightgreen|lightgrey|lightpink|lightsalmon|lightseagreen|"
    "lightskyblue|lightslategray|lightslategrey|lightsteelblue|lightyellow|lime|limegreen|linen|"
    "magenta|maroon|mediumaquamarine|mediumblue|mediumorchid|mediumpurple|mediumseagreen|"
    "mediumslateblue|mediumspringgreen|mediumturquoise|mediumvioletred|midnightblue|mintcream|"
    "mistyrose|moccasin|navajowhite|navy|oldlace|olive|olivedrab|orange|orangered|orchid|"
    "palegoldenrod|palegreen|paleturquoise|palevioletred|papayawhip|peachpuff|peru|pink|plum|"
    "powderblue|purple|rebeccapurple|red|rosybrown|royalblue|saddlebrown|salmon|sandybrown|"
    "seagreen|seashell|sienna|silver|skyblue|slateblue|slategray|slategrey|snow|springgreen|"
    "steelblue|tan|teal|thistle|tomato|turquoise|violet|wheat|white|whitesmoke|yellow|"
    "yellowgreen"
    r")(?![\w-])"
)
NOT_A_WORD = re.compile(r"(?:url|var)\([^)]*\)", re.IGNORECASE)
QUOTED_TEXT = re.compile(r"([\"'`])((?:(?!\1).)*)\1")
TEMPLATE_HOLE = re.compile(r"\$\{[^}]*\}")
COLOUR_PROPERTY = re.compile(
    r"--[\w-]+|(?:background|border|outline|column-rule)(?:-[a-z]+)*|color|fill|stroke"
    r"|[a-z]+-color|box-shadow|text-shadow|text-decoration|filter"
)
LENGTH_PROPERTY = re.compile(
    r"(?:padding|margin|inset|border(?:-[a-z]+)?-radius|gap|row-gap|column-gap|top|right"
    r"|bottom|left|width|height|min-width|max-width|min-height|max-height|font-size"
    r"|flex-basis)(?:-[a-z]+)*"
)
LENGTH = re.compile(
    r"(?<![\w.#-])(?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*)(?:px|rem|em|pt)\b"
)
BARE_NUMBER = re.compile(
    r"\s*['\"]?((?:[1-9]\d*(?:\.\d+)?|0?\.\d*[1-9]\d*))['\"]?\s*,?\s*"
)
NEXT_PROPERTY = r",\s*[\"']?[A-Za-z][\w-]*[\"']?\s*:"
DECLARATION = re.compile(
    rf"(?<![\w(-])(--[\w-]+|[A-Za-z][\w-]*)\s*:\s*((?:(?!{NEXT_PROPERTY})[^;{{}}\]])*)"
)
CAMEL = re.compile(r"(?<=[a-z])(?=[A-Z])")
ATTRIBUTE_COLOUR = re.compile(
    rf"\b(?:fill|stroke|stop-color|flood-color|color|bgcolor)\s*=\s*[\"']({HEX})[\"']"
)
QUOTED_HEX = re.compile(
    rf"(?P<before>[\w:.(-]*\s*[=:(]?\s*)(?P<quote>[\"'`])(?P<hex>{HEX})(?P=quote)"
)
NOT_A_COLOUR = re.compile(
    r"(?:href|id|to|for|htmlfor|name|key|target|from|path|anchor|xlink:href|data-[\w-]+|aria-[\w-]+)"
    r"\s*[=:]\s*$|\(\s*$",
    re.IGNORECASE,
)
DIGIT = re.compile(r"\d")
STYLE_OPEN = re.compile(
    r"style=\{\{|\b\w*[Ss]tyles?\s*[=:]\s*\{|\b(?:sx|css)\s*[=:]\s*\{+|StyleSheet\.create\(\s*\{"
)
APPLY = re.compile(r"@apply\b")
UNIT_NUMBER = r"-?\d*\.?\d+(?:px|rem|em|pt)"
ARBITRARY_COLOUR = re.compile(
    rf"(?<![\w-])(?:[\w-]+:)*-?[a-z-]+-\[(?:{HEX}|(?:rgba?|hsla?|oklch)\((?!\s*var\())[^\]\s\"'`]*\]"
)
ARBITRARY_LENGTH = re.compile(
    r"(?<![\w-])(?:[\w-]+:)*-?(?:p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy]|inset(?:-[xy])?"
    r"|top|right|bottom|left|w|h|min-w|max-w|min-h|max-h|size|basis|rounded(?:-[a-z]{1,2})?"
    r"|text)-\[(?![^\]]*var\()([^\]\s\"'`]*" + UNIT_NUMBER + r"[^\]\s\"'`]*)\]"
)
PALETTE = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan"
    "|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
PALETTE_CLASS = re.compile(
    r"(?<![\w-])(?:[\w-]+:)*(?:text|bg|border(?:-[xytrblse])?|ring|fill|stroke|outline|from|via|to"
    rf"|divide|placeholder|accent|caret|decoration)-((?:{PALETTE})-\d{{2,3}}|white|black)(?:/\d+)?(?![\w-])"
)
COLOUR_STEP = (
    "Use a token of the design source (a custom property or a theme colour), "
    "and add a new colour to the token file and to DESIGN.md"
)
PALETTE_STEP = (
    "Tailwind's default palette is not a project token: define the project's own colours "
    "in the theme block, drop the defaults with `@theme { --color-*: initial; }`, "
    "and use those names"
)
SIZE_STEP = (
    "Use a spacing, size, radius or font size token of the design source, "
    "and add a new value to the token file and to DESIGN.md"
)


def kebab(name: str) -> str:
    return CAMEL.sub("-", name).lower()


def colour_names(value: str, in_style_object: bool) -> list[str]:
    """The colour names of a value, in any case; in a style object only a quoted string holds one, so a constant such as WHITE is no colour."""
    if in_style_object:
        value = " ".join(
            TEMPLATE_HOLE.sub(" ", text) for _, text in QUOTED_TEXT.findall(value)
        )
    return COLOUR_NAME.findall(NOT_A_WORD.sub(" ", value).lower())


def declaration_hits(line: str, in_style_object: bool) -> list[tuple[str, str]]:
    """(kind, text) for each colour or length typed as a property value on this line."""
    found: list[tuple[str, str]] = []
    for match in DECLARATION.finditer(line):
        prop, value = kebab(match[1]), match[2]
        colour = bool(COLOUR_PROPERTY.fullmatch(prop))
        if colour:
            found += [("colour", hit[0]) for hit in HEX_VALUE.finditer(value)]
        if colour:
            found += [
                ("colour", f"{prop}: {word}")
                for word in colour_names(value, in_style_object)
            ]
        if LENGTH_PROPERTY.fullmatch(prop):
            found += [("size", f"{prop}: {hit[0]}") for hit in LENGTH.finditer(value)]
            if in_style_object and (bare := BARE_NUMBER.fullmatch(value.split("}")[0])):
                found.append(("size", f"{prop}: {bare[1]}"))
    return found


def string_hits(line: str) -> list[tuple[str, str]]:
    if "#" not in line:
        return []
    found = [("colour", hit[1]) for hit in ATTRIBUTE_COLOUR.finditer(line)]
    for hit in QUOTED_HEX.finditer(line):
        value = hit["hex"]
        if NOT_A_COLOUR.search(hit["before"] + " ") or not (
            len(value) in (7, 9) or DIGIT.search(value)
        ):
            continue
        found.append(("colour", value))
    return found


def class_hits(line: str, defined: set[str]) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if "-[" in line:
        found += [("colour", hit[0]) for hit in ARBITRARY_COLOUR.finditer(line)]
        found += [("size", hit[0]) for hit in ARBITRARY_LENGTH.finditer(line)]
    found += [
        ("palette", hit[0])
        for hit in PALETTE_CLASS.finditer(line)
        if not palette_defined(hit[1], defined)
    ]
    return found


def palette_defined(name: str, defined: set[str]) -> bool:
    return name in defined or any(
        entry.endswith("-") and name.startswith(entry) for entry in defined
    )


def object_depth(line: str, open_at: int = 0) -> int:
    part = line[open_at:]
    return part.count("{") - part.count("}")


def outermost(hits: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Each hit once, and none that is only a part of a bigger hit of the same kind, such as #abcdef in bg-[#abcdef]; an underscore in a bigger hit reads as a space."""
    unique = list(dict.fromkeys(hits))
    return [
        hit
        for hit in unique
        if not any(
            hit != other
            and hit[0] == other[0]
            and (hit[1] in other[1] or hit[1] in other[1].replace("_", " "))
            for other in unique
        )
    ]


BRACKET_GROUP = re.compile(r"\[[^\]\s]*\]")
STYLE_ATTRIBUTE = re.compile(r"style=\{")
IDENTIFIER = re.compile(r"[A-Za-z_$][\w$]*")


def style_expression(line: str, start: int) -> str:
    """The braced expression of a style attribute that starts at `start`, to its matching brace or the line end."""
    depth = 0
    for position in range(start, len(line)):
        depth += (line[position] == "{") - (line[position] == "}")
        if depth == 0:
            return line[start : position + 1]
    return line[start:]


def used_style_objects(lines: list[tuple[int, str]]) -> re.Pattern[str] | None:
    """The declaration of each object that a style attribute names anywhere in its expression (a function that returns an object is a stated limit)."""
    names = {
        name
        for _, line in lines
        for hit in STYLE_ATTRIBUTE.finditer(line)
        for name in IDENTIFIER.findall(style_expression(line, hit.end() - 1))
    }
    if not names:
        return None
    return re.compile(
        rf"\b(?:const|let|var)\s+(?:{'|'.join(re.escape(name) for name in sorted(names))})\b[^=\n]*=\s*\{{"
    )


def raw_value_hits(
    name: str, lines: list[tuple[int, str]], defined: set[str]
) -> list[tuple[int, str, str]]:
    """(line, kind, text) for each raw colour or length; a token file is never passed in."""
    found: list[tuple[int, str, str]] = []
    depth = 0
    used = used_style_objects(lines)
    for number, line in lines:
        opened = (
            (STYLE_OPEN.search(line) or (used and used.search(line)))
            if depth <= 0
            else None
        )
        if opened:
            depth = object_depth(line, opened.start())
            in_style_object = True
        else:
            in_style_object = depth > 0
            depth += object_depth(line) if in_style_object else 0
        spaced = BRACKET_GROUP.sub(lambda group: group[0].replace("_", " "), line)
        hits = declaration_hits(spaced, in_style_object)
        hits += [("colour", hit[0]) for hit in COLOUR_FUNCTION.finditer(spaced)]
        if not name.endswith(STYLE_SUFFIXES):
            hits += string_hits(line)
            hits += class_hits(line, defined)
        elif APPLY.search(line):
            hits += class_hits(line, defined)
        found += [(number, kind, text) for kind, text in outermost(hits)]
    return found

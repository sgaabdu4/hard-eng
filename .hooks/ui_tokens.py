"""HE-UI-SOURCE: the DESIGN.md front matter and the token files hold the same colours, lengths and font families."""

import math
import re
from typing import NamedTuple

from ui_exempt import code_of

CSS_HEX = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![\w-])")
CSS_RGB = re.compile(
    r"rgba?\(\s*([\d.]+%?)[ ,]+([\d.]+%?)[ ,]+([\d.]+%?)(?:\s*[,/]\s*([\d.]+%?))?\s*\)"
)
DART_HEX = re.compile(r"(?:Color\(|\.new\()\s*0x([0-9a-fA-F]{8})\s*\)")
DART_ARGB = re.compile(
    r"Color\.fromARGB\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)"
)
DART_RGBO = re.compile(
    r"Color\.fromRGBO\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*([\d.]+)\s*\)"
)
DART_FROM = re.compile(
    r"Color\.from\(\s*alpha:\s*([\d.]+)\s*,\s*red:\s*([\d.]+)\s*,\s*green:\s*([\d.]+)\s*,\s*blue:\s*([\d.]+)\s*,?\s*\)"
)
CSS_FUNCTION = re.compile(r"\b(hsla?|oklch|oklab)\(([^()]*)\)")
ARGUMENT_SPLIT = re.compile(r"[\s,/]+")
CSS_KEYWORDS = frozenset(("initial", "inherit", "unset", "revert"))
CSS_LENGTH = re.compile(r"(?<![\w.#-])(\d*\.?\d+)(px|rem|em|pt)\b")
PX_PER_UNIT = {"px": 1.0, "rem": 16.0, "em": 16.0, "pt": 4 / 3}
DART_LENGTH = re.compile(
    r"static const (?:double )?\w+\s*=\s*(\d+(?:\.0+)?)\s*;|\b(?:fontSize|size):\s*(\d+(?:\.0+)?)\s*[,)]"
)
FONT_PROPERTY = "size|weight|style|tracking|letter|leading|line|stretch|variant|feature|variation|kerning"
CSS_FAMILY = re.compile(
    rf"(?:--font(?!-(?:{FONT_PROPERTY})\b)[\w-]*|--[\w-]*family[\w-]*|font-family)\s*:\s*([^;]+);"
)
CSS_GENERIC_FAMILY = re.compile(
    r"--[\w-]+\s*:\s*([^;]*,\s*(?:sans-serif|serif|monospace|system-ui|cursive|fantasy|ui-[\w-]+))\s*;"
)
CSS_SHADOW = re.compile(
    r"--[\w-]*shadow[\w-]*\s*:[^;]*;|\b\w*[Ss]hadow\w*\s*:\s*[^,;)\n]*"
)
DART_NAMED_COLOUR = re.compile(r"\bColors\.([A-Za-z]+)(?![\w.\[])")
MATERIAL_COLOURS = {
    "red": "f44336",
    "pink": "e91e63",
    "purple": "9c27b0",
    "deepPurple": "673ab7",
    "indigo": "3f51b5",
    "blue": "2196f3",
    "lightBlue": "03a9f4",
    "cyan": "00bcd4",
    "teal": "009688",
    "green": "4caf50",
    "lightGreen": "8bc34a",
    "lime": "cddc39",
    "yellow": "ffeb3b",
    "amber": "ffc107",
    "orange": "ff9800",
    "deepOrange": "ff5722",
    "brown": "795548",
    "grey": "9e9e9e",
    "blueGrey": "607d8b",
    "white": "ffffff",
    "black": "000000",
}
DART_FAMILY = re.compile(
    r"fontFamily:\s*['\"]([^'\"]+)['\"]"
    r"|static const String \w*[Ff]amily\w*\s*=\s*['\"]([^'\"]+)['\"]"
)
DART_SPACING = re.compile(
    r"\bletterSpacing:\s*(\d*\.?\d+)\s*[,)]"
    r"|static const (?:double )?\w*(?:[Ss]pacing|[Ll]etter)\w*\s*=\s*(\d*\.?\d+)\s*;"
)
CSS_NAMED = re.compile(r"--([\w-]+)\s*:\s*([^;]+);")
DART_NAMED = re.compile(r"static const (?:\w+ )?(\w+)\s*=\s*([^;]+);")
GROUP_WORDS = re.compile(
    r"^(?:(colors?|colours?)|(spacing|space)|(radius|rounded)|(size|font|text))"
)
GROUP_KINDS = ("c", "s", "r", "t")
NOT_ALNUM = re.compile(r"[^a-z0-9]")
DESIGN_NAME = "DESIGN.md"
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class Facts(NamedTuple):
    colours: set[str]
    lengths: set[float]
    families: set[str]
    named: dict[tuple[str, str], set[str]]


def channel_byte(word: str) -> int:
    return half_up(float(word[:-1]) * 2.55 if word.endswith("%") else float(word))


def half_up(value: float) -> int:
    return math.floor(value + 0.5)


def rgba(red: int, green: int, blue: int, alpha: float) -> str:
    return f"{red:02x}{green:02x}{blue:02x}{half_up(alpha * 255):02x}"


def unit_value(word: str, scale: float = 1.0) -> float:
    return (
        float(word[:-1]) / 100 * scale
        if word.endswith("%")
        else float(word.removesuffix("deg"))
    )


def clip_byte(value: float) -> int:
    return half_up(max(0.0, min(1.0, value)) * 255)


def srgb_encode(value: float) -> float:
    value = max(0.0, min(1.0, value))
    return 12.92 * value if value <= 0.0031308 else 1.055 * value ** (1 / 2.4) - 0.055


def hsl_channels(hue: float, saturation: float, lightness: float) -> tuple[float, ...]:
    amount = saturation * min(lightness, 1 - lightness)

    def channel(offset: int) -> float:
        position = (offset + hue / 30) % 12
        return lightness - amount * max(-1.0, min(position - 3, 9 - position, 1.0))

    return channel(0), channel(8), channel(4)


def oklab_channels(light: float, a: float, b: float) -> tuple[float, ...]:
    cone_l = (light + 0.3963377774 * a + 0.2158037573 * b) ** 3
    cone_m = (light - 0.1055613458 * a - 0.0638541728 * b) ** 3
    cone_s = (light - 0.0894841775 * a - 1.2914855480 * b) ** 3
    return (
        srgb_encode(
            4.0767416621 * cone_l - 3.3077115913 * cone_m + 0.2309699292 * cone_s
        ),
        srgb_encode(
            -1.2684380046 * cone_l + 2.6097574011 * cone_m - 0.3413193965 * cone_s
        ),
        srgb_encode(
            -0.0041960863 * cone_l - 0.7034186147 * cone_m + 1.7076147010 * cone_s
        ),
    )


def function_colour(name: str, arguments: str) -> str | None:
    words = [word for word in ARGUMENT_SPLIT.split(arguments.strip()) if word]
    if len(words) not in (3, 4):
        return None
    try:
        alpha = unit_value(words[3]) if len(words) == 4 else 1.0
        if name.startswith("hsl"):
            red, green, blue = hsl_channels(
                unit_value(words[0]) % 360, unit_value(words[1]), unit_value(words[2])
            )
        else:
            light = unit_value(words[0])
            if name == "oklch":
                chroma = unit_value(words[1], 0.4)
                angle = math.radians(unit_value(words[2]))
                red, green, blue = oklab_channels(
                    light, chroma * math.cos(angle), chroma * math.sin(angle)
                )
            else:
                red, green, blue = oklab_channels(
                    light, unit_value(words[1], 0.4), unit_value(words[2], 0.4)
                )
    except ValueError:
        return None
    return "".join(f"{clip_byte(v):02x}" for v in (red, green, blue, alpha))


def colours_in(text: str) -> set[str]:
    found: set[str] = set()
    for hit in CSS_HEX.finditer(text):
        digits = hit[1].lower()
        digits = "".join(c * 2 for c in digits) if len(digits) < 6 else digits
        found.add(digits if len(digits) == 8 else digits + "ff")
    for hit in CSS_RGB.finditer(text):
        alpha = hit[4] or "1"
        value = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
        found.add(
            rgba(
                channel_byte(hit[1]), channel_byte(hit[2]), channel_byte(hit[3]), value
            )
        )
    found |= {
        hit[1][2:].lower() + hit[1][:2].lower() for hit in DART_HEX.finditer(text)
    }
    found |= {
        rgba(int(hit[2]), int(hit[3]), int(hit[4]), int(hit[1]) / 255)
        for hit in DART_ARGB.finditer(text)
    }
    found |= {
        rgba(int(hit[1]), int(hit[2]), int(hit[3]), float(hit[4]))
        for hit in DART_RGBO.finditer(text)
    }
    found |= {
        colour
        for hit in CSS_FUNCTION.finditer(text)
        if (colour := function_colour(hit[1], hit[2]))
    }
    found |= {
        "".join(f"{half_up(float(hit[i]) * 255):02x}" for i in (2, 3, 4, 1))
        for hit in DART_FROM.finditer(text)
    }
    found |= {
        MATERIAL_COLOURS[hit[1]] + "ff"
        for hit in DART_NAMED_COLOUR.finditer(text)
        if hit[1] in MATERIAL_COLOURS
    }
    return {value for value in found if not value.endswith("00")}


def length_px(value: str) -> float | None:
    hit = CSS_LENGTH.fullmatch(value.strip().strip("\"'"))
    if hit:
        return float(hit[1]) * PX_PER_UNIT[hit[2]]
    try:
        return float(value)
    except ValueError:
        return None


def first_family(value: str) -> str:
    return value.split(",")[0].strip().strip("\"'")


def named_value(value: str) -> str:
    colours = colours_in(value)
    if colours:
        return "c" + min(colours)
    length = length_px(value.strip())
    return "" if length is None else f"l{length:g}"


def named_key(name: str, value: str) -> tuple[str, str] | None:
    """(group, name) of a token; a colour needs no group word, a length does."""
    plain = NOT_ALNUM.sub("", name.lower())
    word = GROUP_WORDS.match(plain)
    rest = plain[word.end() :] if word else plain
    if value.startswith("c"):
        return ("c", rest)
    if word and word.lastindex:
        return (GROUP_KINDS[word.lastindex - 1], rest)
    return None


def blank_facts() -> Facts:
    return Facts(set(), set(), set(), {})


def token_facts(texts: list[str]) -> Facts:
    colours, lengths, families, named = blank_facts()
    for source in texts:
        text = CSS_SHADOW.sub("", code_of(source))
        colours |= colours_in(text)
        lengths |= {
            length
            for hit in CSS_LENGTH.finditer(text)
            if (length := length_px(hit[0])) and length > 0
        }
        lengths |= {
            float(hit[0] or hit[1])
            for hit in DART_LENGTH.findall(text)
            if float(hit[0] or hit[1]) >= 1
        }
        families |= {
            family
            for hit in (*CSS_FAMILY.findall(text), *CSS_GENERIC_FAMILY.findall(text))
            if (family := first_family(hit))
            and family not in CSS_KEYWORDS
            and not family.startswith("var(")
            and not family[0].isdigit()
        }
        lengths |= {
            float(hit[0] or hit[1])
            for hit in DART_SPACING.findall(text)
            if float(hit[0] or hit[1]) > 0
        }
        families |= {hit[0] or hit[1] for hit in DART_FAMILY.findall(text)}
        for hit in (*CSS_NAMED.findall(text), *DART_NAMED.findall(text)):
            value = named_value(hit[1])
            if value and (key := named_key(hit[0], value)):
                named.setdefault(key, set()).add(value)
    return Facts(colours, lengths, families, named)


def plain_name(name: str) -> str:
    return NOT_ALNUM.sub("", name.lower())


def unit_lengths(value: object) -> set[float]:
    if isinstance(value, dict):
        return set().union(*(unit_lengths(member) for member in value.values()))
    hit = CSS_LENGTH.fullmatch(str(value).strip())
    return {length_px(str(value)) or 0.0} - {0.0} if hit else set()


def other_group_lengths(groups: dict[str, dict[object, object]]) -> set[float]:
    return {
        length
        for group, members in groups.items()
        if group not in ("colors", "spacing", "rounded", "typography")
        for value in members.values()
        if (length := length_px(str(value))) is not None
    }


def typography_facts(roles: dict[object, object], facts: Facts) -> None:
    for role, style in roles.items():
        if not isinstance(style, dict):
            continue
        if (size := length_px(str(style.get("fontSize", "")))) is not None:
            facts.lengths.add(size)
            facts.named.setdefault(("t", plain_name(str(role))), set()).add(
                f"l{size:g}"
            )
        if family := style.get("fontFamily"):
            facts.families.add(first_family(str(family)))


def design_facts(data: dict[str, object]) -> Facts:
    colours, lengths, families, named = blank_facts()
    groups = {key: value for key, value in data.items() if isinstance(value, dict)}
    for name, value in groups.get("colors", {}).items():
        found = colours_in(str(value))
        colours |= found
        if found:
            named[("c", plain_name(str(name)))] = {"c" + min(found)}
    for group in ("spacing", "rounded"):
        for name, value in groups.get(group, {}).items():
            if (length := length_px(str(value))) is not None:
                lengths.add(length)
                named.setdefault(
                    ("s" if group == "spacing" else "r", plain_name(str(name))), set()
                ).add(f"l{length:g}")
    lengths |= other_group_lengths(groups)
    lengths |= {
        length
        for group, members in groups.items()
        if group != "colors"
        for length in unit_lengths(members)
    }
    typography_facts(
        groups.get("typography", {}), Facts(colours, lengths, families, named)
    )
    return Facts(colours, lengths, families, named)


def token_findings(design: str | None, token_texts: list[str]) -> list[str]:
    import yaml

    if design is None:
        return [
            f"{DESIGN_NAME} is missing; add it with the front matter of the design tokens"
        ]
    front = FRONT_MATTER.match(design)
    if not front:
        return [
            f"{DESIGN_NAME} has no front matter; add the design tokens as YAML front matter"
        ]
    try:
        data = yaml.safe_load(front[1])
    except yaml.YAMLError:
        return [f"{DESIGN_NAME} front matter is not valid YAML; fix its syntax"]
    doc = design_facts(data if isinstance(data, dict) else {})
    code = token_facts(token_texts)
    doc.lengths.discard(0.0)
    found = [
        f"a token colour #{value[:6]}{value[6:] if value[6:] != 'ff' else ''} is missing from {DESIGN_NAME}"
        for value in sorted(code.colours - doc.colours)
    ]
    found += [
        f"the {DESIGN_NAME} colour #{value[:6]}{value[6:] if value[6:] != 'ff' else ''} is missing from the token files"
        for value in sorted(doc.colours - code.colours)
    ]
    found += [
        f"the {DESIGN_NAME} length {length_label(value, [front[1]])} is missing from the token files"
        for value in sorted(doc.lengths - code.lengths)
    ]
    found += [
        f"a token length {length_label(value, token_texts)} is missing from {DESIGN_NAME}"
        for value in sorted(code.lengths - doc.lengths)
    ]
    found += [
        f"the {DESIGN_NAME} font family {value} is missing from the token files"
        for value in sorted(doc.families - code.families)
    ]
    found += [
        f"a token font family {value} is missing from {DESIGN_NAME}"
        for value in sorted(code.families - doc.families)
    ]
    for key in sorted(doc.named.keys() & code.named.keys()):
        if not doc.named[key] & code.named[key]:
            found.append(
                f"the token {key[1]} is {describe(min(code.named[key]))} but {DESIGN_NAME} says {describe(min(doc.named[key]))}"
            )
    return found


def length_label(value: float, texts: list[str]) -> str:
    """The length as written with its px value after it (0.08em (1.28px)); a length written in px stays plain."""
    plain = f"{value:g}px"
    written = {
        hit[0]
        for text in texts
        for hit in CSS_LENGTH.finditer(code_of(text))
        if length_px(hit[0]) == value
    }
    if not written or plain in written:
        return plain
    return f"{min(written)} ({plain})"


def describe(value: str) -> str:
    if value.startswith("c"):
        digits = value[1:]
        return "#" + digits[:6] + (digits[6:] if digits[6:] != "ff" else "")
    return f"{value[1:]}px"

"""The measured facts of one image, by element: what the reviewer reads, and the checks that code decides."""

import re
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from ui_measure import LIMITS

FACT_BYTES = 1500
LENGTH = re.compile(r"(\d*\.?\d+)(px|rem)")


class Tokens(NamedTuple):
    colours: dict[str, str]
    spacing: list[str]
    rounded: list[str]


class Fact(NamedTuple):
    names: tuple[str, ...]
    ok: bool | None
    margin: float
    line: str
    why: str


def design_tokens(root: Path | None) -> Tokens:
    """The colour, spacing and rounded tokens of the DESIGN.md front matter, as written. A missing file, a python3 without PyYAML, a missing front matter or a missing group gives an empty list, which means no verdict."""
    from ui_tokens import FRONT_MATTER, colours_in

    none = Tokens({}, [], [])
    try:
        import yaml
    except ImportError:
        return none
    try:
        front = FRONT_MATTER.match((root / "DESIGN.md").read_text()) if root else None
        data = yaml.safe_load(front[1]) if front else None
    except (OSError, yaml.YAMLError):
        return none
    if not isinstance(data, dict):
        return none

    def group(name: str) -> dict[str, object]:
        found = data.get(name)
        return found if isinstance(found, dict) else {}

    return Tokens(
        {
            colour: name
            for name, value in group("colors").items()
            for colour in colours_in(str(value))
        },
        [str(value) for value in group("spacing").values()],
        [str(value) for value in group("rounded").values()],
    )


def length_scale(tokens: list[str], root_px: float) -> set[int] | None:
    """The token lengths in px, with rem set from the page's own root size; None when a token is any other form (em, clamp, calc, a variable), which the measure cannot hold exactly."""
    from ui_tokens import half_up

    scale: set[int] = set()
    for token in tokens:
        found = LENGTH.fullmatch(token.strip())
        if not found:
            return None
        scale.add(half_up(float(found[1]) * (1 if found[2] == "px" else root_px)))
    return scale


def _scale(tokens: list[str], measured: dict[str, object]) -> set[int] | None:
    base = measured.get("root_px")
    if not tokens or not isinstance(base, int | float) or isinstance(base, bool):
        return None
    return length_scale(tokens, float(base))


def _rows(measured: dict[str, object], key: str) -> list[dict[str, object]]:
    found = measured.get(key)
    return (
        [row for row in found if isinstance(row, dict)]
        if isinstance(found, list)
        else []
    )


def _controls(measured: dict[str, object]) -> list[dict[str, object]]:
    sizes = measured.get("sizes")
    found = sizes.get("controls") if isinstance(sizes, dict) else None
    return (
        [row for row in found if isinstance(row, dict)]
        if isinstance(found, list)
        else []
    )


def _num(value: object) -> float:
    return float(value) if isinstance(value, int | float) else 0.0


def _shown(value: float) -> str:
    return f"{value:g}"


def _token_name(tokens: Tokens, raw: str, blended: str) -> str:
    return tokens.colours.get(raw) or tokens.colours.get(blended + "ff") or ""


def _swatch(tokens: Tokens, raw: object, blended: object) -> str:
    plain = str(blended or "")
    name = _token_name(tokens, str(raw), plain.removeprefix("#"))
    return f"{plain or '#' + str(raw)[:6]} ({'token ' + name if name else 'no token'})"


def size_facts(measured: dict[str, object], tokens: Tokens) -> list[Fact]:
    floor = LIMITS["text_px"]
    found: list[Fact] = []
    for row in _rows(measured, "texts"):
        px = _num(row.get("px"))
        under = row.get("under") is True
        pair = ""
        if row.get("fg") and row.get("bg"):
            pair = (
                f", colour {_swatch(tokens, row.get('colour'), row.get('fg'))} on "
                f"{_swatch(tokens, row.get('fill'), row.get('bg'))}, contrast {row.get('ratio')}:1"
            )
        line = f"{row.get('at')}: {_shown(px)} px, weight {_shown(_num(row.get('weight')))}{pair}"
        found.append(
            Fact(
                (str(row.get("at")),),
                not under,
                px - floor,
                f"{line}, under the {floor} px floor" if under else line,
                f"text is {_shown(px)} px, {'under' if under else 'at or over'} the {floor} px floor",
            )
        )
    return found


def _opaque(blended: object) -> str:
    return str(blended or "").removeprefix("#") + "ff"


def colour_ok(row: dict[str, object], tokens: Tokens) -> bool | None:
    """True when the text colour and the fill are colour tokens, as raw or as blended on the page; None when DESIGN.md has no colour tokens or the row has no colour."""
    if not tokens.colours or not row.get("colour"):
        return None
    held = set(tokens.colours)
    fill = str(row.get("fill") or "")
    text = str(row["colour"]) in held or _opaque(row.get("fg")) in held
    return text and (not fill or fill in held or _opaque(row.get("bg")) in held)


def colour_facts(measured: dict[str, object], tokens: Tokens) -> list[Fact]:
    found: list[Fact] = []
    for row in _rows(measured, "texts"):
        ok = colour_ok(row, tokens)
        found.append(
            Fact(
                (str(row.get("at")),),
                ok,
                0 if ok is False else 1,
                "",
                f"text colour {_swatch(tokens, row.get('colour'), row.get('fg'))} on "
                f"{_swatch(tokens, row.get('fill'), row.get('bg'))} {'is' if ok else 'is not'} in the colour tokens",
            )
        )
    return found


def tap_facts(measured: dict[str, object], tokens: Tokens) -> list[Fact]:
    found: list[Fact] = []
    for row in _controls(measured):
        w, h, floor = _num(row.get("w")), _num(row.get("h")), _num(row.get("floor"))
        under = row.get("under") is True
        size = f"{_shown(w)}x{_shown(h)} px"
        found.append(
            Fact(
                (str(row.get("at")),),
                not under,
                min(w, h) - floor,
                f"{row.get('at')}: {size}"
                + (f", under {_shown(floor)} px" if under else ""),
                f"control is {size}, {'under' if under else 'at or over'} its {_shown(floor)} px floor",
            )
        )
    return found


def gap_facts(measured: dict[str, object], tokens: Tokens) -> list[Fact]:
    scale = _scale(tokens.spacing, measured)
    found: list[Fact] = []
    for row in _rows(measured, "gaps"):
        px = int(_num(row.get("px")))
        ok = None if scale is None else px in scale or px == 0
        pair = f"{row.get('at')} to {row.get('to')}"
        found.append(
            Fact(
                (
                    str(row.get("at")),
                    str(row.get("to")),
                    pair,
                    f"{row.get('at')} and {row.get('to')}",
                ),
                ok,
                0 if ok is False else px,
                f"{pair}: {px} px ({row.get('axis')})",
                f"gap {px} px {'is' if ok else 'is not'} a spacing token",
            )
        )
    return found


def radius_facts(measured: dict[str, object], tokens: Tokens) -> list[Fact]:
    scale = _scale(tokens.rounded, measured)
    found: list[Fact] = []
    for row in _rows(measured, "radii"):
        px = int(_num(row.get("px")))
        ok = None if scale is None or row.get("clamped") is not False else px in scale
        found.append(
            Fact(
                (str(row.get("at")),),
                ok,
                0 if ok is False else px,
                f"{row.get('at')}: {px} px"
                + (" (clamped by its box)" if row.get("clamped") else ""),
                f"corner radius {px} px {'is' if ok else 'is not'} a rounded token",
            )
        )
    return found


FACTS: dict[str, Callable[[dict[str, object], Tokens], list[Fact]]] = {
    "size": size_facts,
    "colour": colour_facts,
    "tap": tap_facts,
    "gap": gap_facts,
    "radius": radius_facts,
}


def _order(facts: list[Fact]) -> list[Fact]:
    return sorted(
        facts, key=lambda fact: (fact.ok is not False, fact.margin, fact.names)
    )


def _listed(facts: list[Fact], floor_note: str) -> list[str]:
    lines: list[str] = []
    used = 0
    ordered = _order(facts)
    for fact in ordered:
        used += len(fact.line.encode()) + 3
        if used > FACT_BYTES:
            break
        lines.append(f"- {fact.line}")
    rest = ordered[len(lines) :]
    if rest:
        why = f", {floor_note}" if all(fact.ok for fact in rest) else ""
        lines.append(f"{len(rest)} more not listed{why}")
    return lines


def _covered(
    kind: str, facts: list[Fact], tokens: Tokens, measured: dict[str, object]
) -> str:
    count, outside = len(facts), sum(fact.ok is False for fact in facts)
    floor = LIMITS["text_px"]
    if kind == "size":
        return f"text size: checked for all {count} text elements: {outside} under the {floor} px floor"
    if kind == "tap":
        return (
            f"tap size: checked for all {count} controls: {outside} under their floor "
            f"({LIMITS['control_px']} px; {LIMITS['link_px']} px for a link at {LIMITS['desktop_px']} px and wider)"
        )
    given = {
        "colour": (
            tokens.colours,
            "colour",
            "text elements",
            "colour tokens",
            "colour",
        ),
        "gap": (
            _scale(tokens.spacing, measured),
            "spacing",
            "gaps",
            "spacing tokens",
            "gaps",
        ),
        "radius": (
            _scale(tokens.rounded, measured),
            "rounded",
            "corner radii",
            "rounded tokens",
            "radii",
        ),
    }[kind]
    held, word, things, name, plural = given
    if not held:
        return (
            f"{kind}: no {word} tokens in DESIGN.md, so code does not decide {plural}"
        )
    return f"{kind}: checked for all {count} {things} against {len(held)} {name}: {outside} outside them"


NOTES = {
    "size": f"each at or over the {LIMITS['text_px']} px floor",
    "tap": "each at or over its floor",
    "gap": "each a spacing token",
    "radius": "each a rounded token",
}


def measured_text(measured: dict[str, object], tokens: Tokens) -> str:
    """The measured facts of one image, by element: for each check what it covered, then the facts nearest to its limit first, up to FACT_BYTES; the rest are counted."""
    lines: list[str] = []
    for kind, build in FACTS.items():
        facts = build(measured, tokens)
        lines.append(_covered(kind, facts, tokens, measured))
        if kind in NOTES:
            lines += _listed(facts, NOTES[kind])
    return "\n".join(lines)


ROLE_WORDS = frozenset(
    [
        "the",
        "button",
        "link",
        "text",
        "label",
        "icon",
        "badge",
        "chip",
        "tab",
        "field",
        "input",
        "heading",
        "control",
    ]
)


def plain(name: str) -> str:
    """The name as words, lowercase, with punctuation and the role words dropped, so `Save button` and `Save` are one name."""
    words = re.findall(r"\w+", name.lower())
    return " ".join(word for word in words if word not in ROLE_WORDS)


def verdict(
    kind: str, element: str, measured: dict[str, object], tokens: Tokens
) -> tuple[bool, str] | None:
    """Pass (True) or Fail (False) of an item with a measured kind, with the reason; None when code cannot decide it. The element must equal one recorded name of three letters or more once role words are dropped, and every fact of that name must give the same verdict; any other case is `not found`, which leaves the item to the reviewer."""
    wanted = plain(element)
    build = FACTS.get(kind)
    if build is None or len(wanted) < 3:
        return None
    hits = [
        fact for fact in build(measured, tokens) if wanted in map(plain, fact.names)
    ]
    if not hits or any(fact.ok is None for fact in hits):
        return None
    if len({fact.ok for fact in hits}) != 1:
        return None
    return bool(hits[0].ok), ", ".join(dict.fromkeys(fact.why for fact in hits))

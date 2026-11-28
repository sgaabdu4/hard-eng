"""The measured facts of one image, by element: what the reviewer reads, and the checks that code decides."""

import re
from collections import Counter
from collections.abc import Callable, Mapping
from typing import NamedTuple

from ui_measure import LIMITS

FACT_BYTES = 1500
UNSAFE_IN_KEY = re.compile(r"[;:\[\]`*\"\s]+")
NO_NAME = "no name"
TRIGGER = {
    "radius": re.compile(r"(?i)\b(?:square|squared|sharp)\b"),
    "align": re.compile(
        r"(?i)\b(?:not\s+cent(?:red|ered)|uncent(?:red|ered)|off[- ]cent(?:re|er)(?:d)?|cent(?:red|ered))\b"
    ),
    "gap": re.compile(r"(?i)\b(?:touch(?:es|ing)?|no gap)\b"),
    "tap": re.compile(
        r"(?i)\b(?:too\s+(?:small|tiny|narrow|short)\s+(?:to|for)\s+(?:tap|click|press)(?:ping)?|"
        r"(?:tap|touch)[- ](?:target|size)|hard\s+to\s+(?:tap|hit|press))\b"
    ),
}
LEAD = (
    r"(?:(?!(?:not|never|no|nor|off|but|than|rather|instead|should|must|needs?|do|does|don't|doesn't|"
    r"isn't|aren't|wasn't|weren't|can't|cannot|won't|would|could|may|might|without)\b)[\w'’-]+\s+){0,6}"
)
CLAIMS = {
    "radius": ("square", r"square|squared|sharp"),
    "align": ("centred", r"cent(?:red|ered)"),
    "gap": ("touch", r"touch(?:es|ing)?|no gap"),
}
CLAIM_FORMS = {
    kind: re.compile(rf"(?i)\s*{LEAD}(?:{words})\b")
    for kind, (_, words) in CLAIMS.items()
}


class Fact(NamedTuple):
    key: str
    ok: bool | None
    margin: float
    line: str
    why: str


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


def fact_key(name: object) -> str:
    """The recorded name of an element as the key that the reviewer copies: the characters that the answer form reads (a semicolon, a colon, a bracket, a backtick, an asterisk, a quote and any space run) become one space, so the key survives the form of a Fail line."""
    return UNSAFE_IN_KEY.sub(" ", str(name or "")).strip() or NO_NAME


def _named(
    rows: list[dict[str, object]], namer: Callable[[dict[str, object]], str]
) -> list[tuple[str, dict[str, object]]]:
    """Each row with its own key: the name of the element, and ` #1`, ` #2` in record order when several elements of one kind share a name, so a verdict never comes from another element."""
    names = [namer(row) for row in rows]
    totals = Counter(names)
    seen: Counter[str] = Counter()
    keyed: list[tuple[str, dict[str, object]]] = []
    for name, row in zip(names, rows, strict=True):
        seen[name] += 1
        keyed.append((f"{name} #{seen[name]}" if totals[name] > 1 else name, row))
    return keyed


def _at(row: dict[str, object]) -> str:
    return fact_key(row.get("at"))


def _pair(row: dict[str, object]) -> str:
    return f"{fact_key(row.get('at'))} to {fact_key(row.get('to'))}"


def size_facts(measured: dict[str, object]) -> list[Fact]:
    floor = LIMITS["text_px"]
    found: list[Fact] = []
    for key, row in _named(_rows(measured, "texts"), _at):
        px = _num(row.get("px"))
        under = row.get("under") is True
        pair = ""
        if row.get("fg") and row.get("bg"):
            pair = f", contrast {row.get('ratio')}:1"
        place = (
            f", align {row['align']}{' (centred)' if row.get('centred') else ''}"
            if row.get("align") and isinstance(row.get("centred"), bool)
            else ""
        )
        line = f"{key}: {_shown(px)} px, weight {_shown(_num(row.get('weight')))}{place}{pair}"
        found.append(
            Fact(
                key,
                not under,
                px - floor,
                f"{line}, under the {floor} px floor" if under else line,
                f"text is {_shown(px)} px, {'under' if under else 'at or over'} the {floor} px floor",
            )
        )
    return found


def colour_facts(measured: dict[str, object]) -> list[Fact]:
    return []


def tap_facts(measured: dict[str, object]) -> list[Fact]:
    found: list[Fact] = []
    for key, row in _named(_controls(measured), _at):
        if not isinstance(row.get("under"), bool) or "floor" not in row:
            continue
        w, h, floor = _num(row.get("w")), _num(row.get("h")), _num(row.get("floor"))
        under = row.get("under") is True
        exempt = row.get("exempt") is True
        size = f"{_shown(w)}x{_shown(h)} px"
        state = (
            f"inline link, exempt from the {_shown(floor)} px floor"
            if exempt
            else f"{'under' if under else 'at or over'} {_shown(floor)} px"
        )
        found.append(
            Fact(
                key,
                not under,
                min(w, h) - floor,
                f"{key}: {size}, {state}",
                f"control is {size}, exempt from its {_shown(floor)} px floor as a link in a sentence"
                if exempt
                else f"control is {size}, {'under' if under else 'at or over'} its {_shown(floor)} px floor",
            )
        )
    return found


def _weights(measured: dict[str, object]) -> dict[str, tuple[str, float]]:
    rows = [
        (own, row)
        for own, row in _named(_rows(measured, "texts"), _at)
        if "weight" in row and _at(row) != NO_NAME
    ]
    seen: Counter[str] = Counter()
    for _, row in rows:
        seen[fact_key(row.get("at"))] += max(1, int(_num(row.get("n"))))
    return {
        fact_key(row.get("at")): (own, _num(row.get("weight")))
        for own, row in rows
        if seen[fact_key(row.get("at"))] == 1
    }


def weight_facts(measured: dict[str, object]) -> list[Fact]:
    return [
        Fact(own, True, 1, "", f"weight {_shown(weight)}")
        for own, weight in _weights(measured).values()
    ]


def align_facts(measured: dict[str, object]) -> list[Fact]:
    return [
        Fact(
            key,
            row["centred"],
            0 if row["centred"] is False else 1,
            "",
            f"text-align {row.get('align')}, {'centred' if row['centred'] else 'not centred'} in its parent",
        )
        for key, row in _named(_rows(measured, "texts"), _at)
        if isinstance(row.get("centred"), bool)
    ]


def _gap_rows(measured: dict[str, object]) -> list[dict[str, object]]:
    return [row for row in _rows(measured, "gaps") if "to" in row and "px" in row]


def gap_facts(measured: dict[str, object]) -> list[Fact]:
    return [
        Fact(pair, True, px, "", f"gap {px} px")
        for pair, row in _named(_gap_rows(measured), _pair)
        for px in [max(0, int(_num(row.get("px"))))]
    ]


def corners_of(row: dict[str, object]) -> list[int]:
    """The four corner radii of a radius row; a row from an older record holds one radius for all four."""
    held = row.get("corners")
    if isinstance(held, list) and len(held) == 4:
        return [int(_num(corner)) for corner in held]
    return [int(_num(row.get("px")))] * 4


def radius_facts(measured: dict[str, object]) -> list[Fact]:
    return [
        Fact(key, True, px, "", f"corner radius {px} px")
        for key, row in _named(_rows(measured, "radii"), _at)
        if not key.startswith(NO_NAME)
        for px in [int(_num(row.get("px")))]
    ]


FACTS: dict[str, Callable[[dict[str, object]], list[Fact]]] = {
    "size": size_facts,
    "colour": colour_facts,
    "tap": tap_facts,
    "weight": weight_facts,
    "align": align_facts,
    "gap": gap_facts,
    "radius": radius_facts,
}


def _order(facts: list[Fact]) -> list[Fact]:
    return sorted(facts, key=lambda fact: (fact.ok is not False, fact.margin, fact.key))


def _keyed(facts: list[Fact]) -> frozenset[str]:
    oks: dict[str, set[bool | None]] = {}
    for fact in facts:
        oks.setdefault(fact.key, set()).add(fact.ok)
    return frozenset(
        key for key, found in oks.items() if len(found) == 1 and None not in found
    )


def _key_line(kind: str, facts: list[Fact]) -> str:
    keyed = _keyed(facts)
    keys = [key for key in dict.fromkeys(f.key for f in _order(facts)) if key in keyed]
    shown: list[str] = []
    used = 0
    for key in keys:
        used += len(key.encode()) + 3
        if kind in CLAIM_ONLY and used > FACT_BYTES:
            break
        shown.append(key)
    more = (
        f" | {len(keys) - len(shown)} more have no key listed"
        if len(shown) < len(keys)
        else ""
    )
    return f"{kind} keys: {' | '.join(shown)}{more}" if keys else ""


def _listed(facts: list[Fact], floor_note: str) -> list[str]:
    lines: list[str] = []
    used = 0
    ordered = _order(facts)
    keyed = _keyed(facts)
    for fact in ordered:
        shown = fact.line if fact.key in keyed else f"{fact.line} (no key: judgement)"
        used += len(shown.encode()) + 3
        if used > FACT_BYTES:
            break
        lines.append(f"- {shown}")
    rest = ordered[len(lines) :]
    if rest:
        why = f", {floor_note}" if all(fact.ok for fact in rest) else ""
        keys = " | ".join(dict.fromkeys(fact.key for fact in rest if fact.key in keyed))
        listing = f"their keys: {keys}" if keys else "none of them has a key"
        lines.append(f"{len(rest)} more not listed{why}; {listing}")
    return lines


def _covered(kind: str, facts: list[Fact]) -> str:
    count, outside = len(facts), sum(fact.ok is False for fact in facts)
    floor = LIMITS["text_px"]
    if kind == "size":
        return f"text size: checked for all {count} text elements: {outside} under the {floor} px floor"
    if kind == "tap":
        return (
            f"tap size: checked for all {count} controls: {outside} under their floor "
            f"({LIMITS['control_px']} px; {LIMITS['link_px']} px for a link at {LIMITS['desktop_px']} px and wider)"
        )
    if kind == "align":
        counted = sum(fact.ok is not None for fact in facts)
        if not counted:
            return "align: no align facts in this record, so code does not decide align"
        return f"align: checked for all {counted} text elements: {outside} not centred in their parent"
    return CLAIM_ONLY[kind].format(count=count)


NOTES = {
    "size": f"each at or over the {LIMITS['text_px']} px floor",
    "tap": "each at or over its floor",
}
CLAIM_ONLY = {
    "colour": "colour: code does not decide colours, so a colour item is judgement",
    "gap": "gap: code checks only a claim that two neighbours touch, for {count} neighbour pairs; a gap value is not checked against DESIGN.md, so any other gap item is judgement",
    "weight": "weight: code checks only a claim that one element is bolder or lighter than another named element, for {count} text elements; a different weight alone is no fault, so any other weight item is judgement",
    "radius": "radius: code checks only a claim that corners are square, for {count} elements; a corner radius is not checked against DESIGN.md, so any other radius item is judgement",
}


def measured_text(measured: dict[str, object]) -> str:
    """The measured facts of one image, by element: for each check what it covered, then the facts nearest to its limit first, up to FACT_BYTES; the rest are counted, with their keys, so every key that code can decide is shown. Each fact line starts with its key."""
    lines: list[str] = []
    for kind, build in FACTS.items():
        facts = build(measured)
        lines.append(_covered(kind, facts))
        if kind in NOTES:
            lines += _listed(facts, NOTES[kind])
        elif keys := _key_line(kind, facts):
            lines.append(keys)
    return "\n".join(lines)


def item_keys(measured: dict[str, object]) -> dict[str, frozenset[str]]:
    """The keys of one image for each measured kind: the exact texts that an item of that kind may name. A fact that code cannot decide has no key, so an item on it is a judgement item."""
    return {kind: _keyed(build(measured)) for kind, build in FACTS.items()}


def claim_word(kind: str, text: str) -> str:
    """The word of a claim form that the text holds for this kind, or an empty text: `square`, `squared` or `sharp` for a radius; `centred`, `not centred`, `uncentred` or `off-centre` for an alignment; `touch`, `touches`, `touching` or `no gap` for a gap; `too small to tap`, `tap target`, `touch size` or `hard to tap` for a tap size."""
    found = TRIGGER[kind].search(text) if kind in TRIGGER else None
    return found[0].lower() if found else ""


def claim_in(
    text: str, keys: Mapping[str, frozenset[str]]
) -> tuple[str, str, str] | None:
    """The kind, key and claim word of the first claim form in the text that names the exact key of a measured element of that kind."""
    for kind in TRIGGER:
        if word := claim_word(kind, text):
            for key in sorted(keys.get(kind, ()), key=len, reverse=True):
                if re.search(rf"(?<!\w){re.escape(key)}(?!\w)", text, re.IGNORECASE):
                    return kind, key, word
    return None


def claimed_state(kind: str, claim: str) -> str:
    """The state that an item of a measured kind claims: `square` for a radius, `centred` for an alignment and `touch` for a gap, when its note opens with that claim (up to six plain words, then the claim word: `chips touch`, `the header line is centred`). A negation or a `should` before the word, and any other note, keeps the old meaning of the kind, so a word inside a sentence never flips the direction of a claim."""
    state, _ = CLAIMS.get(kind, ("", ""))
    form = CLAIM_FORMS.get(kind)
    return state if state and form and form.match(claim.replace("’", "'")) else ""


def _held(
    measured: dict[str, object],
    name: str,
    namer: Callable[[dict[str, object]], str],
    element: str,
) -> list[dict[str, object]]:
    return [row for key, row in _named(_rows(measured, name), namer) if key == element]


def _square(element: str, measured: dict[str, object]) -> tuple[bool, str] | None:
    """A square claim is disproved by any corner of the element above 0; when every corner is 0 the claim is true and the item stays with the reviewer."""
    held = [corners_of(row) for row in _held(measured, "radii", _at, element)]
    squares = [not any(corners) for corners in held]
    if not held or (any(squares) and not all(squares)):
        return None
    if not all(squares):
        return True, f"corner radii {', '.join(map(str, held[0]))} px, not square"
    return None


def _centred(element: str, measured: dict[str, object]) -> tuple[bool, str] | None:
    """A centred claim is disproved by a text that is measured as not centred; a measured centred text leaves the item with the reviewer."""
    held = [
        row
        for row in _held(measured, "texts", _at, element)
        if isinstance(row.get("centred"), bool)
    ]
    if not held or any(row["centred"] for row in held):
        return None
    return True, f"text-align {held[0].get('align')}, not centred in its parent"


def _touch(element: str, measured: dict[str, object]) -> tuple[bool, str] | None:
    """A touch claim is disproved by a measured gap above 0; a measured gap of 0 leaves the item with the reviewer."""
    held = [
        max(0, int(_num(row.get("px"))))
        for key, row in _named(_gap_rows(measured), _pair)
        if key == element
    ]
    if not held or not all(held):
        return None
    return True, f"gap {held[0]} px, the neighbours do not touch"


STATES = {"square": _square, "centred": _centred, "touch": _touch}
NAME_JOIN = re.compile(
    r"\s*(?:,\s*(?:(?:and|or)\s+)?|&\s*|(?:and|or)\s+)", re.IGNORECASE
)
WEIGHT_CLAIM = re.compile(
    rf"(?i)\s*{LEAD}(bolder|heavier|lighter|thinner)\s+than\b(.*)"
)


def _weight_claim(
    element: str, measured: dict[str, object], claim: str
) -> tuple[bool, str] | None:
    """A claim that an element is bolder or lighter than the elements that open its note (a list joined by commas, `and` or `or`; the list ends at the first other word) is disproved by the first of them it does not beat; a true claim stays with the reviewer."""
    found = WEIGHT_CLAIM.match(claim.replace("’", "'"))
    weights = {key: weight for key, (_, weight) in _weights(measured).items()}
    if not found or element not in weights:
        return None
    heavier = found[1].lower() in ("bolder", "heavier")
    rest = found[2].strip()
    named: list[str] = []
    by_length = sorted(weights, key=len, reverse=True)
    while rest:
        key = next(
            (
                key
                for key in by_length
                if key != element
                and re.match(rf"{re.escape(key)}(?!\w)", rest, re.IGNORECASE)
            ),
            "",
        )
        if not key:
            break
        named.append(key)
        joined = NAME_JOIN.match(rest[len(key) :])
        if not joined:
            break
        rest = rest[len(key) + joined.end() :]
    for key in named:
        beats = (
            weights[element] > weights[key]
            if heavier
            else weights[element] < weights[key]
        )
        if not beats:
            word = "bolder" if heavier else "lighter"
            return (
                True,
                f"weight {_shown(weights[element])}, not {word} than {key} ({_shown(weights[key])})",
            )
    return None


def verdict(
    kind: str,
    element: str,
    measured: dict[str, object],
    claim: str = "",
) -> tuple[bool, str] | None:
    """Pass (True) or Fail (False) of an item with a measured kind, with the reason; None when code cannot decide it. The element must equal a key of that kind exactly, and every fact of that key must give the same verdict; any other case leaves the item to the reviewer. There is no loose name match, because a wrong match gives a false verdict. A note that states a claim (`square`, `centred`) is compared with the fact in the direction of the claim: a Pass means the claim is disproved."""
    if kind == "weight":
        return _weight_claim(element, measured, claim)
    if state := claimed_state(kind, claim):
        return STATES[state](element, measured)
    build = FACTS.get(kind)
    if build is None or kind in CLAIM_ONLY:
        return None
    hits = [fact for fact in build(measured) if fact.key == element]
    if not hits or any(fact.ok is None for fact in hits):
        return None
    if len({fact.ok for fact in hits}) != 1:
        return None
    return bool(hits[0].ok), ", ".join(dict.fromkeys(fact.why for fact in hits))

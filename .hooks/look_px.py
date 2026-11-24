"""A look Fail line that gives a text size or a corner radius in px that the measured values of the images do not hold."""

import re
from typing import cast

from plans import split_rule_line

NUMBER = r"(\d+(?:\.\d+)?)\s*px"
SOFT = r"(?:(?:is|of|at|only|just)\s+)*(?:(?:about|around|roughly|approximately|nearly|~)\s*)?"
TEXT = re.compile(
    rf"(?i)\b(?:text|font)(?:\s+size)?\s+{SOFT}{NUMBER}|{NUMBER}\s+(?:text|font)\b"
)
RADIUS = re.compile(
    rf"(?i)\b(?:corners?|radius|radii)(?:\s+radius)?\s+{SOFT}{NUMBER}|{NUMBER}\s+(?:corners?|radius|rounded)\b"
)
ELEMENTS = re.compile(
    r"(?i)\b(?:badge|chip|pill|tag|label|button|control|link|input|field|select)s?\b"
)
REQUIRED_BEFORE = re.compile(
    r"(?i)\b(?:sets?|requires?|required|minimum|maximum|min|max|at least|at most|under|below|above|over|should|must|expects?|token|guideline|target|not|instead|rather|versus|vs|DESIGN)\b"
)
REQUIRED_AFTER = re.compile(r"(?i)^\W*(?:minimum|maximum|min|max|token)\b")
TOLERANCE = 0.5


def _claims(
    pattern: re.Pattern[str], text: str, *, element: bool = False
) -> list[float]:
    """The px that the line gives for the image itself; a value in the same clause as a requirement word is a target, not a measure, and 0 px is never recorded."""
    line = text.replace("DESIGN.md", "DESIGN")
    claims = []
    for found in pattern.finditer(line):
        start = max(line.rfind(mark, 0, found.start()) for mark in ",;:.") + 1
        ends = [i for mark in ",;:." if (i := line.find(mark, found.end())) >= 0]
        clause = line[start : min(ends, default=len(line))]
        required = REQUIRED_BEFORE.search(line[start : found.start()]) or (
            REQUIRED_AFTER.search(line[found.end() :])
        )
        number = next((group for group in found.groups() if group), "")
        if (
            number
            and float(number)
            and not required
            and (ELEMENTS.search(clause) or not element)
        ):
            claims.append(float(number))
    return claims


def _held(measured: list[dict[str, object]]) -> dict[str, set[float]]:
    text: set[float] = set()
    radii: set[float] = set()
    for values in measured:
        sizes = cast(dict[str, object], values.get("sizes", {}))
        text |= {float(px) for px in cast(list[int], sizes.get("text_px", []))}
        radii |= {
            float(str(item["px"]))
            for item in cast(list[dict[str, object]], values.get("radii", []))
        }
    return {"text size": text, "corner radius": radii}


def px_problem(lines: list[str], measured: list[dict[str, object]]) -> str | None:
    """The refusal that names the claimed and the measured px of the first Fail line that guesses a size; None when every claim is held or nothing is measured."""
    held = _held(measured)
    patterns = {"text size": TEXT, "corner radius": RADIUS}
    for line in lines:
        if split_rule_line(line)[1] != "Fail":
            continue
        for kind, values in held.items():
            claims = _claims(patterns[kind], line, element=kind == "corner radius")
            for claim in claims if values else []:
                if all(abs(claim - value) > TOLERANCE for value in values):
                    shown = ", ".join(f"{value:g}" for value in sorted(values))
                    return (
                        f"not done: a Fail line says {kind} {claim:g} px, but the measured "
                        f"{kind} values are {shown} px; correct the number: {line}"
                    )
    return None

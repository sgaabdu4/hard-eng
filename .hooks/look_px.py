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
TOLERANCE = 0.5


def _claims(pattern: re.Pattern[str], line: str) -> list[float]:
    return [
        float(number) for found in pattern.findall(line) for number in found if number
    ]


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
            for claim in _claims(patterns[kind], line) if values else []:
                if all(abs(claim - value) > TOLERANCE for value in values):
                    shown = ", ".join(f"{value:g}" for value in sorted(values))
                    return (
                        f"not done: a Fail line says {kind} {claim:g} px, but the measured "
                        f"{kind} values are {shown} px; correct the number: {line}"
                    )
    return None

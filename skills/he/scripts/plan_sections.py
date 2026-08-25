"""Feature Brief section parsing and the frozen approval fingerprint."""

from __future__ import annotations

import hashlib
import re


class PlanError(ValueError):
    """Invalid Feature Brief or transition."""


SECTIONS = (
    "Outcome",
    "Non-goals",
    "Material decisions",
    "Acceptance examples",
    "Affected canonical areas",
    "Risk and rollback",
    "First vertical slice",
)
FROZEN_SECTIONS = SECTIONS[:4]


def token_for(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\n", text))
    headings = [match.group(1).strip() for match in matches]
    if headings != list(SECTIONS):
        raise PlanError(f"required section order is: {' -> '.join(SECTIONS)}")
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[headings[index]] = text[match.end() : end].strip()
    return sections


def risk_fields(section: str) -> tuple[str, str]:
    values: dict[str, str] = {}
    for key in ("risk_level", "critical_overlay", "rollback"):
        matches = re.findall(rf"(?m)^- {key} = (.+)$", section)
        if len(matches) != 1:
            raise PlanError(f"Risk and rollback requires exactly one `{key}` row")
        values[key] = matches[0].strip()
    if values["risk_level"] not in {"standard", "critical"}:
        raise PlanError("risk_level must be standard or critical")
    overlay = values["critical_overlay"]
    if values["risk_level"] == "standard" and overlay != "none":
        raise PlanError("standard risk requires critical_overlay = none")
    if values["risk_level"] == "critical" and overlay == "none":
        raise PlanError("critical risk requires a scoped critical_overlay")
    return values["risk_level"], overlay


def frozen_fingerprint(sections: dict[str, str]) -> str:
    risk_level, overlay = risk_fields(sections["Risk and rollback"])
    values = [f"{heading}\n{sections[heading].strip()}" for heading in FROZEN_SECTIONS]
    values.extend((f"risk_level\n{risk_level}", f"critical_overlay\n{overlay}"))
    return token_for("\n\n".join(values))

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
    "Vertical slices",
)
FROZEN_SECTIONS = SECTIONS[:4]
SLICES_SECTION = SECTIONS[-1]
LEGACY_SLICES_HEADING = "First vertical slice"
SLICE_ROW = re.compile(r"(?m)^- (S-[1-9][0-9]*) = (.+)$")
DEPENDS_ON = re.compile(r";\s*depends_on\s*=\s*([^;]+?)\s*$")
TICKET_CHOICES = ("none", "local", "github", "jira", "azdo")
EMPTY_WORDS = ("none", "n/a")
REASON_PLACEHOLDERS = frozenset({"tbd", "todo", "tba", "?", *EMPTY_WORDS})
REASON_ROWS = {
    "Material decisions": ("ux_reference", "ux_reference_sources"),
    "Risk and rollback": ("critical_overlay", "deferred", "blocked_on", "tickets"),
}


def empty_value(value: str) -> tuple[str, str] | None:
    stripped = value.strip()
    lowered = stripped.lower()
    for word in EMPTY_WORDS:
        if lowered == word:
            return word, ""
        if lowered.startswith(word + ":"):
            return word, stripped[len(word) + 1 :].strip()
    return None


def reason_error(key: str, value: str) -> str | None:
    empty = empty_value(value)
    if empty is None:
        return None
    word, reason = empty
    if not reason or reason.lower() in REASON_PLACEHOLDERS:
        return f"{key} = {word} needs a short reason: write `{word}: <why>`"
    return None


def brief_reason_error(sections: dict[str, str]) -> str | None:
    for heading, keys in REASON_ROWS.items():
        for key in keys:
            for value in re.findall(rf"(?m)^- {key} = (.+)$", sections[heading]):
                if error := reason_error(key, value):
                    return error
    for identifier, body in SLICE_ROW.findall(sections[SLICES_SECTION]):
        match = DEPENDS_ON.search(body)
        if match and (error := reason_error(f"{identifier} depends_on", match.group(1))):
            return error
    return None


def token_for(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def remaining_slice(sections: dict[str, str], completed: str) -> str:
    done = {item.strip() for item in completed.split(",")} if completed != "none" else set()
    for identifier, _body in SLICE_ROW.findall(sections[SLICES_SECTION]):
        if identifier not in done:
            return identifier
    return "none"


def parse_sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\n", text))
    headings = [
        SLICES_SECTION if match.group(1).strip() == LEGACY_SLICES_HEADING else match.group(1).strip()
        for match in matches
    ]
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
    overlay_empty = empty_value(overlay) is not None
    if values["risk_level"] == "standard" and not overlay_empty:
        raise PlanError("standard risk requires critical_overlay = none: <why>")
    if values["risk_level"] == "critical" and overlay_empty:
        raise PlanError("critical risk requires a scoped critical_overlay")
    return values["risk_level"], overlay


def frozen_fingerprint(sections: dict[str, str]) -> str:
    risk_level, overlay = risk_fields(sections["Risk and rollback"])
    values = [f"{heading}\n{sections[heading].strip()}" for heading in FROZEN_SECTIONS]
    values.extend((f"risk_level\n{risk_level}", f"critical_overlay\n{overlay}"))
    return token_for("\n\n".join(values))


def parse_slices(section: str) -> dict[str, tuple[str, ...]]:
    graph: dict[str, tuple[str, ...]] = {}
    for identifier, body in SLICE_ROW.findall(section):
        if identifier in graph:
            raise PlanError(f"duplicate slice row: {identifier}")
        match = DEPENDS_ON.search(body)
        raw = match.group(1).strip() if match else "none"
        graph[identifier] = () if empty_value(raw) else tuple(item.strip() for item in raw.split(",") if item.strip())
    if not graph:
        raise PlanError("Vertical slices requires at least one `- S-n = ...` row")
    expected = [f"S-{index}" for index in range(1, len(graph) + 1)]
    if list(graph) != expected:
        raise PlanError("Vertical slices must be numbered S-1..S-n in order without gaps")
    for identifier, dependencies in graph.items():
        for dependency in dependencies:
            if dependency not in graph or dependency == identifier:
                raise PlanError(f"{identifier} depends on unknown slice {dependency}")
    assert_acyclic(graph)
    return graph


def assert_acyclic(graph: dict[str, tuple[str, ...]]) -> None:
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(node: str, path: tuple[str, ...]) -> None:
        if node in done:
            return
        if node in visiting:
            raise PlanError("slice dependency loop: " + " -> ".join((*path, node)))
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency, (*path, node))
        visiting.discard(node)
        done.add(node)

    for node in graph:
        visit(node, ())


def closing_fields(section: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key in ("tickets", "tracker"):
        matches = re.findall(rf"(?m)^- {key} = (.+)$", section)
        if len(matches) > 1:
            raise PlanError(f"Risk and rollback allows at most one `{key}` row")
        if matches:
            values[key] = matches[0].strip()
    if "tickets" in values:
        empty = empty_value(values["tickets"])
        if (empty[0] if empty else values["tickets"]) not in TICKET_CHOICES:
            raise PlanError(f"tickets must be one of {', '.join(TICKET_CHOICES)}")
    return values


def with_closing_rows(text: str, tickets: str, tracker: str) -> str:
    sections = parse_sections(text)
    heading = "## Risk and rollback\n"
    if text.count(heading) != 1:
        raise PlanError("requires exactly one Risk and rollback heading")
    body = sections["Risk and rollback"]
    stripped = "\n".join(line for line in body.splitlines() if not re.match(r"^- (tickets|tracker) = ", line))
    replacement = f"{stripped}\n- tickets = {tickets}\n- tracker = {tracker}"
    start = text.index(heading) + len(heading)
    end = start + len(text[start:].split("\n## ", 1)[0])
    return text[:start] + replacement.strip() + "\n\n" + text[end:].lstrip("\n")

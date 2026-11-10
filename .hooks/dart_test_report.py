"""Read the machine-format report produced by a Dart test gate."""

import json
import re
from pathlib import Path
from typing import cast

from gate_config import JsonObject

WHITESPACE_RUN = re.compile(r"\s+")
FLUTTER_FAILURE = "Test failed. See exception logs above"
PRINT_LIMIT = 600


def dart_events(path: Path) -> list[JsonObject]:
    """Return reporter events, skipping raw test output that shares the stream."""
    events: list[JsonObject] = []
    for line in path.read_text().splitlines():
        try:
            value = json.loads(line)
        except ValueError:
            continue
        items = value if isinstance(value, list) else [value]
        if all(isinstance(item, dict) for item in items):
            events.extend(cast(JsonObject, item) for item in items)
    return events


def test_place(test: JsonObject) -> str:
    url = test.get("root_url") or test.get("url")
    line = test.get("root_line") if test.get("root_url") else test.get("line")
    return f"{url}:{line}"


def failure_summary(path: Path) -> str | None:
    """Return one bounded failing-test summary from a machine-format Dart report."""
    try:
        events = dart_events(path)
    except (OSError, ValueError):
        return None
    names: dict[int, str] = {}
    places: dict[int, str] = {}
    prints: dict[int, list[str]] = {}
    failures: list[int] = []
    errors: dict[int, str] = {}
    for event in events:
        if event.get("type") == "testStart" and isinstance(event.get("test"), dict):
            test = cast(JsonObject, event["test"])
            identifier, name = test.get("id"), test.get("name")
            if type(identifier) is int and isinstance(name, str):
                names[identifier] = name
                places[identifier] = test_place(test)
        identifier = event.get("testID")
        if type(identifier) is not int:
            continue
        if event.get("type") == "testDone" and event.get("result") in {
            "failure",
            "error",
        }:
            failures.append(identifier)
        if event.get("type") == "print" and isinstance(event.get("message"), str):
            prints.setdefault(identifier, []).append(event["message"])
        if event.get("type") == "error" and isinstance(event.get("error"), str):
            errors.setdefault(identifier, event["error"])
    if not failures:
        return None
    identifier = failures[0]
    name = names.get(identifier, f"test {identifier}")
    if (error := errors.get(identifier)) is None:
        return f"Dart test failure: {name}"
    detail = WHITESPACE_RUN.sub(" ", error).strip()
    if error.startswith(FLUTTER_FAILURE):
        printed = WHITESPACE_RUN.sub(" ", " ".join(prints.get(identifier, []))).strip()
        detail = (
            f"{printed[:PRINT_LIMIT]} ({places.get(identifier, 'no file')})".strip()
        )
        return f"Dart test failure: {name}: {detail}"
    return f"Dart test failure: {name}: {detail[:300]}"

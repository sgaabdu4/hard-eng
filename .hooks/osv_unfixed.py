"""Pass a reported vulnerability only when public data proves that no fixed release exists."""

import re
from collections.abc import Callable

from freshness import Fetch, npm_versions, pub_versions, pypi_releases
from gate_config import JsonObject

VERSION = re.compile(r"(\d+(?:\.\d+)*)(.*)", re.DOTALL)
NAME_GAPS = re.compile(r"[-_.]+")
Bound = tuple[int, ...]
READERS: dict[str, Callable[[str, Fetch], list[str]]] = {
    "npm": npm_versions,
    "PyPI": lambda name, fetch: list(pypi_releases(name, fetch)),
    "Pub": lambda name, fetch: [
        str(item["version"]) for item in pub_versions(name, fetch)
    ],
}


def release(version: object) -> tuple[Bound, str]:
    found = VERSION.fullmatch(str(version))
    if found is None:
        raise ValueError(f"the version {version} is unreadable")
    numbers = [int(part) for part in found[1].split(".")]
    while numbers and numbers[-1] == 0:
        numbers.pop()
    return tuple(numbers), found[2]


def above(version: str, bound: Bound) -> bool:
    """A suffix such as -rc.1 sorts below its release; .postN sorts above it."""
    core, rest = release(version)
    return core > bound or (core == bound and rest.lstrip(".-").startswith("post"))


def objects(value: object) -> list[JsonObject]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("the advisory record is unreadable")
    return value


def normal(ecosystem: str, name: object) -> str:
    return NAME_GAPS.sub("-", str(name)).lower() if ecosystem == "PyPI" else str(name)


def range_end(events: list[JsonObject]) -> Bound | None:
    ends = []
    for event in events:
        if "fixed" in event:
            raise ValueError("it has a fixed event")
        if set(event) - {"introduced", "last_affected"}:
            raise ValueError("it has an event that Hard Eng cannot read")
        ends += [event["last_affected"]] if "last_affected" in event else []
    if len(ends) > 1:
        raise ValueError("a range has two last_affected events")
    if not ends:
        return None
    core, rest = release(ends[0])
    if rest:
        raise ValueError(f"it ends at {ends[0]}, which is not a release")
    return core


def last_affected(advisory: JsonObject, ecosystem: str, name: str) -> Bound | None:
    """Where the advisory's ranges end; None when each range is open. Any fixed event is an error."""
    ranges = [
        found
        for entry in objects(advisory.get("affected"))
        if isinstance(entry.get("package"), dict)
        and entry["package"].get("ecosystem") == ecosystem
        and normal(ecosystem, entry["package"].get("name")) == normal(ecosystem, name)
        for found in objects(entry.get("ranges"))
    ]
    if not ranges:
        raise ValueError(f"it has no range for {name}")
    ends = [range_end(objects(found.get("events"))) for found in ranges]
    return min((end for end in ends if end is not None), default=None)


def bound_of(advisory: JsonObject, ecosystem: str, name: str) -> Bound | None:
    try:
        return last_affected(advisory, ecosystem, name)
    except ValueError as error:
        raise ValueError(f"{advisory.get('id')}: {error}") from error


def accept_unfixed(item: JsonObject, fetch: Fetch) -> None:
    """Print one line and return when the advisories of this package are proven unfixed, else raise ValueError."""
    package = item["package"]
    name, version, ecosystem = (
        str(package[key]) for key in ("name", "version", "ecosystem")
    )
    advisories = objects(item.get("vulnerabilities"))
    ids = [str(advisory.get("id")) for advisory in advisories]
    if not advisories or any(
        not set(group["ids"]) <= set(ids) for group in objects(item.get("groups") or [])
    ):
        raise ValueError("the report lacks the record of a vulnerability")
    if ecosystem not in READERS:
        raise ValueError(f"no registry reader for {ecosystem}")
    bounds = [bound_of(advisory, ecosystem, name) for advisory in advisories]
    if closed := [bound for bound in bounds if bound is not None]:
        if release(version)[0] > min(closed):
            raise ValueError(f"{version} is above the affected range")
        try:
            versions = READERS[ecosystem](name, fetch)
        except (OSError, TypeError, ValueError) as error:
            raise ValueError(f"the registry could not be read: {error}") from error
        for other in versions:
            if above(other, min(closed)):
                raise ValueError(f"the release {other} is above the affected range")
    print(
        f"OSV: {name}@{version} {', '.join(ids)}: no fixed release exists yet, so this passes; "
        "it will fail as soon as a fixed release exists"
    )

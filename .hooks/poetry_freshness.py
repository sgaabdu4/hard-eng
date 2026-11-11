"""Name the Poetry step for stale rows from the section of pyproject.toml that declares each one."""

import os
import re
import shlex
import subprocess
import tomllib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from freshness import Stale, newer
from tool_setup import managed_command

REQUIREMENT = re.compile(
    r"\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?P<extras>\[[^\]]*\])?"
    r"\s*(?P<spec>[^;]*?)\s*(?:;\s*(?P<marker>.*?))?\s*"
)
SEPARATORS = re.compile(r"[-_.]+")
OPERATION = re.compile(
    r"^\s*- (?:Installing|Updating|Downgrading) (?P<name>\S+) \((?P<versions>[^)]*)\)",
    re.MULTILINE,
)
STEP = "POETRY_SOLVER_MIN_RELEASE_AGE=2 uvx poetry add"
TABLE_FLAGS = {
    "markers": "--markers",
    "python": "--python",
    "platform": "--platform",
    "source": "--source",
}


class Declared(NamedTuple):
    options: tuple[str, ...]
    head: str
    tail: str
    unsupported: str = ""


def canonical(name: str) -> str:
    return SEPARATORS.sub("-", name).lower()


def table(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def sections(data: dict[str, object]) -> Iterator[tuple[tuple[str, ...], object]]:
    project = table(data.get("project"))
    yield (), project.get("dependencies", [])
    for extra, items in table(project.get("optional-dependencies")).items():
        yield ("--optional", extra), items
    for group, items in table(data.get("dependency-groups")).items():
        yield ("--group", group), items
    poetry = table(table(data.get("tool")).get("poetry"))
    yield (), poetry.get("dependencies", {})
    for group, body in table(poetry.get("group")).items():
        yield ("--group", group), table(body).get("dependencies", {})


def requirement(options: tuple[str, ...], text: str) -> tuple[str, Declared] | None:
    found = REQUIREMENT.fullmatch(text)
    if found is None:
        return None
    name, spec = found["name"], found["spec"]
    marker = f"; {found['marker']}" if found["marker"] else ""
    if spec.startswith("@"):
        return name, Declared(options, name, marker, "url")
    return name, Declared(options, name + (found["extras"] or ""), marker)


def poetry_entry(options: tuple[str, ...], name: str, value: object) -> Declared:
    if isinstance(value, str):
        return Declared(options, name, "")
    body = table(value)
    allowed = {"version", "extras", "allow-prereleases", *TABLE_FLAGS}
    other = sorted(set(body) - allowed) or ([] if "version" in body else ["version"])
    if other or not body:
        return Declared(options, name, "", other[0] if other else "version")
    flags = [
        item
        for key, flag in TABLE_FLAGS.items()
        if key in body
        for item in (flag, str(body[key]))
    ]
    if body.get("allow-prereleases"):
        flags.append("--allow-prereleases")
    listed = body.get("extras")
    extras = ",".join(map(str, listed)) if isinstance(listed, list) else ""
    return Declared((*options, *flags), f"{name}[{extras}]" if extras else name, "")


def declarations(directory: Path) -> dict[str, list[Declared]]:
    path = directory / "pyproject.toml"
    if not path.is_file():
        return {}
    found: dict[str, list[Declared]] = {}
    for options, items in sections(tomllib.loads(path.read_text())):
        if isinstance(items, list):
            parsed = [
                requirement(options, item) for item in items if isinstance(item, str)
            ]
            entries = [item for item in parsed if item]
        else:
            entries = [
                (name, poetry_entry(options, name, value))
                for name, value in table(items).items()
                if name != "python"
            ]
        for name, entry in entries:
            found.setdefault(canonical(name), []).append(entry)
    return found


def poetry_steps(directory: Path, stale: list[Stale]) -> list[str]:
    declared = declarations(directory)
    lines: dict[tuple[str, ...], list[str]] = {}
    for name, _, target in stale:
        for item in declared.get(canonical(name), [Declared((), name, "")]):
            if not item.unsupported:
                lines.setdefault(item.options, []).append(
                    f"{item.head}>={target}{item.tail}"
                )
    return [
        " ".join([STEP, *map(shlex.quote, options), *map(shlex.quote, entries)])
        for options, entries in lines.items()
    ]


def solver_versions(directory: Path, args: list[str]) -> dict[str, str]:
    """The version that Poetry's solver picks for each package that its dry run lists."""
    environment = {**os.environ, "POETRY_SOLVER_MIN_RELEASE_AGE": "2"}
    done = subprocess.run(
        managed_command(["poetry", *args]),
        cwd=directory,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    if done.returncode:
        shown = " ".join(shlex.quote(argument) for argument in args)
        raise ValueError(
            f"`uvx poetry {shown}` failed: {(done.stdout + done.stderr).strip()}"
        )
    return {
        canonical(found["name"]): found["versions"].rpartition("-> ")[2]
        for found in OPERATION.finditer(done.stdout)
    }


def poetry_targets(directory: Path, stale: list[Stale]) -> list[Stale]:
    """Replace each latest version by the newest one that installs with the project's pins."""
    declared = declarations(directory)
    plans: dict[tuple[str, ...], list[tuple[str, str, Declared]]] = {}
    first: dict[str, tuple[str, ...]] = {}
    for name, current, latest in stale:
        for item in declared.get(canonical(name), [Declared((), name, "")]):
            if item.unsupported:
                print(
                    f"{name} {latest}: Hard Eng cannot raise a {item.unsupported} entry; update it by hand"
                )
                continue
            plans.setdefault(item.options, []).append((name, current, item))
            first.setdefault(name, item.options)
    picked: dict[str, str] = {}
    for options, plan in plans.items():
        entries = [f"{item.head}>={current}{item.tail}" for _, current, item in plan]
        versions = solver_versions(
            directory, ["add", "--dry-run", "--no-ansi", "-n", *options, *entries]
        )
        for name, current, _ in plan:
            version = versions.get(canonical(name))
            if version is None:
                raise ValueError(f"Poetry's dry run named no version for {name}")
            if newer(version, picked.get(name, current)):
                picked[name] = version
    for name, current, latest in stale:
        if name in first and name not in picked:
            shown = " ".join(
                ["uvx poetry add --dry-run", *map(shlex.quote, first[name])]
                + [f"'{name}=={latest}'"]
            )
            print(
                f"{name} stays at {current}: {latest} does not install with this project's Python range or pins; `{shown}` shows why"
            )
    return [
        (name, current, picked[name]) for name, current, _ in stale if name in picked
    ]

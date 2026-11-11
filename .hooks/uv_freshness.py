"""Name the uv step for stale rows, one command for each package and section of the tree."""

import re
import shlex
import tomllib
from pathlib import Path

from freshness import UV_ROW, Stale

SECTION = re.compile(r"\((group|extra): ([^)]+)\)")
TREE_DRAWING = "├└│ "


def dynamic_packages(directory: Path) -> set[str]:
    """Names of the packages whose pyproject.toml leaves the runtime dependencies to a build hook."""
    from project_setup import workspace_members

    if not (directory / "pyproject.toml").is_file():
        return set()
    members = [
        found
        for pattern in workspace_members(directory, "python")
        if not pattern.startswith("!")
        for found in directory.glob(pattern)
    ]
    names = set()
    for folder in [directory, *members]:
        file = folder / "pyproject.toml"
        project = (
            tomllib.loads(file.read_text()).get("project", {}) if file.is_file() else {}
        )
        if "dependencies" in project.get("dynamic", []):
            names.add(str(project.get("name")))
    return names


def uv_steps(directory: Path, text: str, stale: list[Stale]) -> str:
    targets = {name: target for name, _, target in stale}
    roots: list[str] = []
    plans: dict[tuple[str, tuple[str, ...]], list[tuple[str, str]]] = {}
    for line in text.splitlines():
        found = UV_ROW.match(line)
        if line and line[0] not in TREE_DRAWING:
            roots.append(line.split()[0])
        elif found and (name := found["name"].partition("[")[0]) in targets:
            kind = SECTION.search(line)
            section = (
                ("--group" if kind[1] == "group" else "--optional", kind[2])
                if kind
                else ()
            )
            plans.setdefault((roots[-1], section), []).append(
                (found["name"], targets[name])
            )
    dynamic = dynamic_packages(directory) if any(not s for _, s in plans) else set()
    commands: list[str] = []
    by_hand: list[str] = []
    for (package, section), entries in plans.items():
        if section or package not in dynamic:
            scope = ["--package", package] if len(roots) > 1 else []
            options = [*scope, *section]
            quoted = [shlex.quote(f"{name}>={target}") for name, target in entries]
            commands.append(" ".join(["uv add", *map(shlex.quote, options), *quoted]))
        else:
            raised = " and ".join(f"{name} to {target}" for name, target in entries)
            by_hand.append(
                f"Raise {raised} by hand where {package} declares its dynamic dependencies, then run `uv lock`."
            )
    parts = [
        f"Run `{'`, then `'.join(commands)}` in a separate PR first (baseline repair)."
    ] * bool(commands)
    return " ".join([*parts, *by_hand])

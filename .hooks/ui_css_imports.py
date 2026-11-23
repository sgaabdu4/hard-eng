"""CSS @import graph of one app: each entrypoint expanded in exact import order."""

import re
from pathlib import Path

CSS_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?["']([^"']+)["']""")


def local_imports(text: str) -> list[tuple[int, str, list[Path]]]:
    """Each non-URL @import as (offset, target, file names to try)."""
    return [
        (match.start(), match[1], [Path(match[1]), Path(match[1] + ".css")])
        for match in CSS_IMPORT.finditer(text)
        if not match[1].startswith(("http://", "https://", "//"))
    ]


def css_import_targets(
    path: Path, text: str, by_resolved: dict[Path, Path]
) -> list[Path]:
    found: list[Path] = []
    for _, _, names in local_imports(text):
        for name in names:
            candidate = (path.parent / name).resolve()
            if candidate in by_resolved:
                found.append(by_resolved[candidate])
                break
    return found


def css_entrypoint_orders(
    files: list[Path], texts: dict[Path, str]
) -> list[list[Path]]:
    """Expand each CSS entrypoint independently in exact @import order so separate builds do not reset one another."""
    by_resolved = {path.resolve(): path for path in files}
    edges = {path: css_import_targets(path, texts[path], by_resolved) for path in files}
    imported = {target.resolve() for targets in edges.values() for target in targets}
    reached: set[Path] = set()
    groups: list[list[Path]] = []
    limit = max(64, len(files) * 8)

    def collect(root_path: Path) -> list[Path]:
        ordered: list[Path] = []
        visiting: set[Path] = set()

        def visit(path: Path) -> None:
            resolved = path.resolve()
            if resolved in visiting or len(ordered) >= limit:
                return
            visiting.add(resolved)
            for target in edges[path]:
                visit(target)
            visiting.remove(resolved)
            reached.add(resolved)
            ordered.append(path)

        visit(root_path)
        return ordered

    for path in files:
        if path.resolve() not in imported:
            groups.append(collect(path))
    for path in files:
        if path.resolve() not in reached:
            groups.append(collect(path))
    return groups

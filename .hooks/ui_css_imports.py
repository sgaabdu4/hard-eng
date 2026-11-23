"""CSS @import graph of one app: each entrypoint expanded in exact import order."""

import re
from pathlib import Path, PurePosixPath

OUTSIDE_STEP = "Keep the app's design tokens inside the app's folder"
BUILD_FOLDERS = frozenset(("dist", "build", ".next", "out", "coverage", "node_modules"))
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CSS_IMPORT = re.compile(r"""@import\s+(?:url\(\s*)?["']([^"']+)["']""")


def local_imports(text: str) -> list[tuple[int, str]]:
    """Each non-URL @import as (offset, target)."""
    return [
        (match.start(), match[1])
        for match in CSS_IMPORT.finditer(text)
        if not match[1].startswith(("http://", "https://", "//"))
    ]


def css_import_targets(
    path: Path, text: str, by_resolved: dict[Path, Path]
) -> list[Path]:
    found: list[Path] = []
    for _, target in local_imports(text):
        for suffix in ("", ".css"):
            candidate = (path.parent / (target + suffix)).resolve()
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


def package_dir(root: Path, name: str) -> Path:
    for parent in PurePosixPath(name).parents:
        candidate = root / parent
        if (candidate / "package.json").is_file():
            return candidate
    return root


def outside_target(root: Path, package: Path, path: Path, target: str) -> bool:
    for suffix in ("", ".css"):
        candidate = (path.parent / (target + suffix)).resolve()
        if candidate.suffix == ".css" and candidate.is_file():
            base = root.resolve()
            if not candidate.is_relative_to(base):
                return True
            rel = candidate.relative_to(base)
            return (
                not BUILD_FOLDERS.intersection(rel.parts)
                and package_dir(root, rel.as_posix()) != package
            )
    return False


def in_comment(text: str, offset: int) -> bool:
    return any(hit.start() <= offset < hit.end() for hit in CSS_COMMENT.finditer(text))


def outside_text(rel: str, line: int, target: str) -> str:
    return f"{rel}:{line}: imports {target} from outside this app. {OUTSIDE_STEP}"


def outside_imports(
    root: Path, package: Path, texts: dict[Path, str]
) -> list[tuple[str, int, str]]:
    """Each @import in the app's CSS that names an existing CSS file outside the app, as (file, line, target)."""
    found: list[tuple[str, int, str]] = []
    for path, text in texts.items():
        if "@import" not in text or ".." not in text:
            continue
        rel = path.relative_to(root).as_posix()
        for offset, target in local_imports(text):
            if (
                ".." in target
                and outside_target(root, package, path, target)
                and not in_comment(text, offset)
            ):
                found.append((rel, text.count("\n", 0, offset) + 1, target))
    return found

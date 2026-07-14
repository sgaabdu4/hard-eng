#!/usr/bin/env python3
"""Bounded current and related context for final audit."""

from __future__ import annotations

import ast
import re
import stat
import subprocess
from pathlib import Path

from js_import_context import JsImportError, default_import_owners


MAX_SECTIONS = 96
MAX_BYTES = 128 * 1024
CONTEXT_RADIUS = 1
MAX_OWNER_SCAN_LINES = 200
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".dart", ".go", ".java", ".js", ".jsx", ".kt", ".py", ".rs", ".swift", ".ts", ".tsx"}
PACKAGE_MANIFESTS = {"Cargo.toml", "go.mod", "package.json", "pubspec.yaml", "pyproject.toml"}
LANGUAGE_FAMILY = {
    ".c": "cpp", ".cc": "cpp", ".cpp": "cpp",
    ".java": "jvm", ".kt": "jvm",
    ".js": "js", ".jsx": "js", ".ts": "js", ".tsx": "js",
}
DEFINITION = re.compile(
    r"\b(?:class|def|fn|function)\s+([A-Za-z_$][A-Za-z0-9_$]*)|"
    r"\b(?:const|final|let|var)\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=.*(?:=>|function\b)"
)
GO_FUNCTION = re.compile(r"^\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")
FUN_FUNCTION = re.compile(r"^\s*(?:[A-Za-z_][A-Za-z0-9_]*\s+)*fun(?:\s*<[^>]+>)?\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
SWIFT_FUNCTION = re.compile(r"^\s*(?:(?:public|private|fileprivate|internal|open|static|class|mutating|nonmutating|override|final)\s+)*func\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
TYPED_FUNCTION = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|static|final|abstract|async|external|override|"
    r"virtual|inline|constexpr|const|synchronized|native|operator)\s+)*"
    r"(?:[A-Za-z_$][A-Za-z0-9_$.:<>?,\[\]]*\s+)+(?:[*&]\s*)*"
    r"([A-Za-z_$][A-Za-z0-9_$]*)\s*\("
)
DART_CONSTRUCTOR = re.compile(r"^\s*([A-Z][A-Za-z0-9_$]*)(?:\.[A-Za-z_$][A-Za-z0-9_$]*)?\s*\([^;]*\)\s*(?:[:{]|=>)")
CALL = re.compile(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\s*\(")
CALL_KEYWORDS = {"assert", "catch", "class", "def", "for", "function", "if", "return", "switch", "while"}
ASSIGNMENT = re.compile(r"^\s*(?:(?:const|final|let|var)\s+)?([A-Za-z_$][A-Za-z0-9_$]*)\s*[:=]")
CONSTANT = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b")
KEY = re.compile(r"[\"']([A-Za-z_$][A-Za-z0-9_.$:-]{1,63})[\"']\s*(?=\])")
ROUTE = re.compile(r"[\"'](/[^\"'\r\n]*)[\"']")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


class RelatedContextError(RuntimeError):
    pass


def command(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode in {0, 1} else ""


def required_git(root: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False
    )
    if result.returncode != 0:
        raise RelatedContextError(f"git {' '.join(args[:2])} failed during related-context indexing")
    return result.stdout


def numbered(lines: list[str], start: int, end: int) -> str:
    return "\n".join(f"{index + 1}: {lines[index]}" for index in range(start, end))


def changed_ranges(root: Path, relative: str, base: str) -> tuple[tuple[int, int], ...]:
    tracked = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--error-unmatch", "--", relative],
        capture_output=True,
        check=False,
    ).returncode == 0
    if not tracked:
        try:
            line_count = len((root / relative).read_text(encoding="utf-8").splitlines())
        except (OSError, UnicodeError):
            return ()
        return ((1, max(1, line_count)),)
    ranges = set()
    for revisions in ((base,), ("--cached",), ()):
        for line in command(root, "diff", "--unified=0", *revisions, "--", relative).splitlines():
            match = HUNK.match(line)
            if match:
                start = int(match.group(1))
                count = int(match.group(2) or "1")
                ranges.add((start, max(start, start + count - 1)))
    return tuple(sorted(ranges))


def context_slice(root: Path, relative: str, line: int) -> str:
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        if path.is_symlink() or not resolved.is_file():
            raise OSError
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise RelatedContextError(f"unsafe related-context path: {relative}") from exc
    start = max(0, line - 1 - CONTEXT_RADIUS)
    end = min(len(lines), line + CONTEXT_RADIUS)
    return numbered(lines, start, end)


def context_slices(
    root: Path, relative: str, line_numbers: set[int], radius: int = CONTEXT_RADIUS
) -> str:
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root.resolve())
        if path.is_symlink() or not resolved.is_file():
            raise OSError
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError, ValueError) as exc:
        raise RelatedContextError(f"unsafe related-context path: {relative}") from exc
    windows = sorted(
        (max(0, line - 1 - radius), min(len(lines), line + radius))
        for line in line_numbers
    )
    merged: list[tuple[int, int]] = []
    for start, end in windows:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return "\n...\n".join(numbered(lines, start, end) for start, end in merged)


def definition_names(line: str, suffix: str = "") -> tuple[str, ...]:
    names = [next(group for group in match.groups() if group) for match in DEFINITION.finditer(line)]
    pattern = {
        ".go": GO_FUNCTION,
        ".kt": FUN_FUNCTION,
        ".swift": SWIFT_FUNCTION,
        ".c": TYPED_FUNCTION,
        ".cc": TYPED_FUNCTION,
        ".cpp": TYPED_FUNCTION,
        ".dart": TYPED_FUNCTION,
        ".java": TYPED_FUNCTION,
    }.get(suffix)
    typed_control = suffix in {".c", ".cc", ".cpp", ".dart", ".java"} and re.match(
        r"^\s*(?:return|if|for|while|switch|throw|new)\b", line
    )
    if pattern and not typed_control and (match := pattern.search(line)):
        names.append(match.group(1))
    if suffix == ".dart" and (match := DART_CONSTRUCTOR.search(line)):
        names.append(match.group(1))
    return tuple(dict.fromkeys(names))


def call_names(line: str) -> tuple[str, ...]:
    return tuple(name for name in CALL.findall(line) if name not in CALL_KEYWORDS)


def imported_names(lines: list[str], suffix: str) -> dict[str, str] | None:
    text = "\n".join(lines)
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            raise RelatedContextError("cannot parse changed Python imports") from exc
        direct = {
            (alias.asname or alias.name): alias.name
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        imported_bindings = {
            alias.asname or alias.name.split(".", 1)[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        } | set(direct)
        qualified = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            root = node.func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in imported_bindings:
                qualified[node.func.attr] = node.func.attr
        return direct | qualified
    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        names: dict[str, str] = {}
        for group in re.findall(r"import\s+(?:type\s+)?\{([^}]+)\}\s+from", text, re.DOTALL):
            for part in group.split(","):
                value = re.sub(r"/\*.*?\*/", "", part, flags=re.DOTALL).strip()
                if value:
                    original, separator, alias = value.partition(" as ")
                    names[alias.strip() if separator else original.strip()] = original.strip()
        namespaces = set(re.findall(r"import\s+\*\s+as\s+([A-Za-z_$][A-Za-z0-9_$]*)\s+from", text))
        for namespace, name in re.findall(r"\b([A-Za-z_$][A-Za-z0-9_$]*)\.([A-Za-z_$][A-Za-z0-9_$]*)\s*\(", text):
            if namespace in namespaces:
                names[name] = name
        for group in re.findall(r"(?:const|let|var)\s*\{([^}]+)\}\s*=\s*require\s*\(", text, re.DOTALL):
            for part in group.split(","):
                original, separator, alias = part.strip().partition(":")
                names[(alias if separator else original).strip()] = original.strip()
        return {local: source for local, source in names.items() if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", local)}
    return None
def local_imported_symbols(root: Path, relative: str, lines: list[str], suffix: str) -> set[str]:
    text = "\n".join(lines)
    base = root / package_scope(root, relative)
    def local(specifier: str, level: int = 0) -> bool:
        parent = (root / relative).parent
        origin = parent.parents[level - 2] if level > 1 else parent
        candidates = (origin,) if level else (base, root)
        parts = specifier.replace(".", "/")
        return any((candidate / f"{parts}.py").is_file() or (candidate / parts / "__init__.py").is_file()
                   for candidate in candidates)
    if suffix == ".py":
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            raise RelatedContextError("cannot parse changed Python imports") from exc
        names = set()
        local_namespaces = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and local(node.module or "", node.level):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                local_namespaces.update(alias.asname or alias.name.split(".", 1)[0]
                                        for alias in node.names if local(alias.name))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                value = node.func.value
                while isinstance(value, ast.Attribute): value = value.value
                if isinstance(value, ast.Name) and value.id in local_namespaces:
                    names.add(node.func.attr)
        return names
    if suffix not in {".js", ".jsx", ".ts", ".tsx"}: return set()
    names = set()
    for group, specifier in re.findall(r"import\s+(?:type\s+)?\{([^}]+)\}\s+from\s+[\"']([^\"']+)", text, re.DOTALL):
        if specifier.startswith("."): names.update(
            part.strip().partition(" as ")[0] for part in group.split(",") if part.strip())
    return names
def exported_names(lines: list[str], suffix: str) -> set[str] | None:
    if suffix not in {".js", ".jsx", ".ts", ".tsx"}:
        return None
    text = "\n".join(lines)
    names = set(re.findall(
        r"\bexport\s+(?:default\s+)?(?:(?:async\s+)?function|class|const|let|var)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)",
        text,
    ))
    for group in re.findall(r"\bexport\s*\{([^}]+)\}", text, re.DOTALL):
        names.update(part.strip().partition(" as ")[0] for part in group.split(",") if part.strip())
    names.update(re.findall(r"\bexport\s+default\s+([A-Za-z_$][A-Za-z0-9_$]*)\b", text))
    return names
def assignment_names(line: str) -> tuple[str, ...]:
    match = ASSIGNMENT.search(line)
    return (match.group(1),) if match else ()
def relationship_kind(relative: str, is_owner: bool) -> str:
    if is_owner:
        return "owner"
    return "test" if re.search(
        r"(?:^|/)(?:test|tests|spec)(?:/|_)|[._](?:test|spec)\.", relative
    ) else "caller"
def searchable_owner(relative: str, name: str, exports: set[str] | None) -> bool:
    if relationship_kind(relative, False) == "test" or name == "main" or name.startswith("_"):
        return False
    return exports is None or name in exports
def bounded_references(candidates: list[tuple[str, int, bool]]) -> list[tuple[str, int, bool]]:
    selected = []
    for kind in ("owner", "caller", "test"):
        match = next((candidate for candidate in candidates if relationship_kind(candidate[0], candidate[2]) == kind), None)
        if match is not None:
            selected.append(match)
    return list(dict.fromkeys(selected))
def dependency_tokens(
    line: str, allowed_calls: dict[str, str] | None = None, suffix: str = ""
) -> tuple[tuple[str, str], ...]:
    calls = set(call_names(line))
    if allowed_calls is not None:
        calls = {allowed_calls[name] for name in calls if name in allowed_calls}
    constants = {allowed_calls.get(name, name) if allowed_calls else name for name in CONSTANT.findall(line)}
    symbols = set(definition_names(line, suffix)) | calls | constants
    literals = set(KEY.findall(line)) | set(ROUTE.findall(line))
    return tuple(sorted({*(("symbol", value) for value in symbols), *(("literal", value) for value in literals)}))
def language_family(relative: str) -> str:
    suffix = Path(relative).suffix.lower()
    return LANGUAGE_FAMILY.get(suffix, suffix)
def package_scope(root: Path, relative: str) -> str:
    current = (root / relative).parent
    while current != root:
        if any((current / manifest).is_file() for manifest in PACKAGE_MANIFESTS):
            return current.relative_to(root).as_posix()
        current = current.parent
    return "."
def repository_matches(
    root: Path,
    token_families: dict[tuple[str, str], set[str]],
    token_scopes: dict[tuple[str, str], set[str]],
) -> dict[tuple[str, str], tuple[tuple[str, int, str], ...]]:
    by_family: dict[str, dict[str, set[str]]] = {}
    for (kind, value), families in token_families.items():
        for family in families:
            by_family.setdefault(family, {}).setdefault(kind, set()).add(value)
    patterns = {
        family: {
            kind: re.compile(
                (r"(?<![A-Za-z0-9_$])(?:" if kind == "symbol" else r"(?:")
                + "|".join(re.escape(value) for value in sorted(values, key=lambda item: (-len(item), item)))
                + (r")(?![A-Za-z0-9_$])" if kind == "symbol" else r")")
            )
            for kind, values in kinds.items() if values
        }
        for family, kinds in by_family.items()
    }
    matches: dict[tuple[str, str], list[tuple[str, int, str]]] = {}
    entries = required_git(root, "ls-files", "--stage", "-z").split(b"\0")
    for entry in entries:
        if not entry:
            continue
        try:
            metadata, raw_relative = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.decode("ascii").split()
            relative = raw_relative.decode("utf-8", "surrogateescape")
        except (UnicodeError, ValueError) as exc:
            raise RelatedContextError("cannot parse tracked source index") from exc
        family = language_family(relative)
        if not relative or family not in patterns or Path(relative).suffix.lower() not in SOURCE_SUFFIXES:
            continue
        if stage != "0":
            raise RelatedContextError(f"unmerged tracked source blocks related context: {relative}")
        if mode == "120000":
            raise RelatedContextError(f"tracked source symlink blocks related context: {relative}")
        if mode not in {"100644", "100755"}:
            raise RelatedContextError(f"unsupported tracked source mode blocks related context: {relative}")
        path = root / relative
        try:
            worktree_mode = path.lstat().st_mode
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise RelatedContextError(f"cannot inspect tracked source: {relative}") from exc
        if stat.S_ISLNK(worktree_mode):
            raise RelatedContextError(f"worktree source symlink blocks related context: {relative}")
        if not stat.S_ISREG(worktree_mode):
            raise RelatedContextError(f"non-file tracked source blocks related context: {relative}")
        try:
            lines = required_git(root, "cat-file", "blob", object_id).decode("utf-8").splitlines()
        except UnicodeError as exc:
            raise RelatedContextError(f"tracked source is not UTF-8: {relative}") from exc
        for line_number, source_line in enumerate(lines, 1):
            for kind, pattern in patterns[family].items():
                for match in pattern.finditer(source_line):
                    token = (kind, match.group())
                    scopes = token_scopes.get(token, {"."})
                    if "." in scopes or any(relative == scope or relative.startswith(scope + "/") for scope in scopes):
                        matches.setdefault(token, []).append((relative, line_number, source_line))
    return {token: tuple(values) for token, values in matches.items()}
def current_plan_intent(text: str) -> str:
    projected: list[str] = []
    excluded = False
    stage_review = False
    for line in text.splitlines():
        if line.strip() in {"## State", "## Active items", "## Learning Candidates", "## Build Progress"}:
            excluded = True
            continue
        if excluded and line.startswith("## "):
            excluded = False
        if excluded:
            continue
        if line.startswith("### Stage Review:"):
            stage_review = True
            continue
        if stage_review and line.startswith("## "):
            stage_review = False
        if stage_review:
            continue
        projected.append(line)
    return "\n".join(projected) + ("\n" if text.endswith("\n") else "")
def enclosing_owner(lines: list[str], first: int, suffix: str) -> tuple[str, int] | None:
    start = min(len(lines) - 1, max(0, first - 1))
    stop = max(-1, start - MAX_OWNER_SCAN_LINES)
    for index in range(start, stop, -1):
        names = definition_names(lines[index], suffix)
        if names:
            return names[0], index + 1
    return None
def owner_end(lines: list[str], owner_line: int, suffix: str) -> int:
    start = owner_line - 1
    if suffix == ".py":
        indentation = len(lines[start]) - len(lines[start].lstrip())
        for index in range(start + 1, len(lines)):
            text = lines[index]
            if text.strip() and len(text) - len(text.lstrip()) <= indentation:
                return index
        return len(lines)
    depth = 0
    started = False
    for index in range(start, len(lines)):
        depth += lines[index].count("{") - lines[index].count("}")
        started = started or "{" in lines[index]
        if started and depth <= 0:
            return index + 1
        if not started and "=>" in lines[index] and ";" in lines[index]:
            return index + 1
    return min(len(lines), start + MAX_OWNER_SCAN_LINES)
def owner_requires_context(
    lines: list[str], owner_line: int, ranges: tuple[tuple[int, int], ...], suffix: str
) -> bool:
    end = owner_end(lines, owner_line, suffix)
    return any(not any(first <= line <= last for first, last in ranges) for line in range(owner_line, end + 1))
def owner_slices(
    lines: list[str], hits: set[tuple[str, int, int, int]], suffix: str
) -> str:
    changed = tuple((first, last) for _, _, first, last in hits)
    windows = [
        (owner_line - 1, owner_end(lines, owner_line, suffix))
        for _, owner_line, _, _ in hits
    ]
    merged: list[tuple[int, int]] = []
    for start, end in sorted(windows):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    runs: list[tuple[int, int]] = []
    for start, end in merged:
        run_start: int | None = None
        for index in range(start, end):
            line_number = index + 1
            covered = any(first <= line_number <= last for first, last in changed)
            if not covered and run_start is None:
                run_start = index
            if covered and run_start is not None:
                runs.append((run_start, index))
                run_start = None
        if run_start is not None:
            runs.append((run_start, end))
    return "\n...\n".join(numbered(lines, start, end) for start, end in runs)
def related_context(
    root: Path,
    changed: tuple[str, ...],
    base: str = "HEAD",
    *,
    max_sections: int = MAX_SECTIONS,
    max_bytes: int = MAX_BYTES,
) -> tuple[tuple[str, str, str], ...]:
    owner_hits: dict[str, set[tuple[str, int, int, int]]] = {}
    source_lines: dict[str, list[str]] = {}
    identifiers: set[str] = set()
    reference_identifiers: set[str] = set()
    reference_literals: set[str] = set()
    coverage: dict[str, set[tuple[str, str]]] = {}
    token_families: dict[tuple[str, str], set[str]] = {}
    token_scopes: dict[tuple[str, str], set[str]] = {}
    related_hits: dict[tuple[str, str], set[tuple[int, str]]] = {}
    required_by: dict[tuple[str, str], set[str]] = {}
    direct_owners: dict[tuple[str, str], set[tuple[str, int]]] = {}

    call_filters: dict[str, dict[str, str] | None] = {}
    file_exports: dict[str, set[str] | None] = {}
    local_symbols: dict[str, set[str]] = {}
    same_file_owners: dict[str, dict[str, int]] = {}
    changed_file_ranges: dict[str, tuple[tuple[int, int], ...]] = {}

    def record(relative: str, line: str) -> None:
        suffix = Path(relative).suffix.lower()
        tokens = set(dependency_tokens(line, call_filters.get(relative), suffix))
        tokens.difference_update(
            ("symbol", name) for name in definition_names(line, suffix)
            if not searchable_owner(relative, name, file_exports.get(relative))
        )
        coverage.setdefault(relative, set()).update(tokens)
        for token in tokens:
            token_families.setdefault(token, set()).add(language_family(relative))
            token_scopes.setdefault(token, set()).add(package_scope(root, relative))
            if token[0] == "symbol" and token[1] in local_symbols.get(relative, set()):
                required_by.setdefault(token, set()).add(relative)
                owner_line = same_file_owners.get(relative, {}).get(token[1])
                if owner_line and owner_requires_context(
                    source_lines[relative], owner_line, changed_file_ranges[relative], suffix
                ):
                    for first, last in changed_file_ranges[relative]:
                        owner_hits.setdefault(relative, set()).add((token[1], owner_line, first, last))
        reference_identifiers.update(value for kind, value in tokens if kind == "symbol")
        reference_literals.update(value for kind, value in tokens if kind == "literal")

    def prepare(relative: str, lines: list[str], ranges: tuple[tuple[int, int], ...]) -> None:
        suffix = Path(relative).suffix.lower()
        definitions = {name: number for number, line in enumerate(lines, 1)
                       for name in definition_names(line, suffix)}
        call_filters[relative] = imported_names(lines, suffix)
        try:
            defaults, owners = default_import_owners(root, relative, lines) if suffix in {".js", ".jsx", ".ts", ".tsx"} else ({}, ())
        except JsImportError as exc:
            raise RelatedContextError(str(exc)) from exc
        if call_filters[relative] is not None:
            call_filters[relative].update(defaults)
            call_filters[relative].update({name: name for name in definitions})
        local_symbols[relative] = local_imported_symbols(root, relative, lines, suffix) | set(definitions) | set(defaults.values())
        for target, owner, line, target_lines in owners:
            token = ("symbol", owner)
            required_by.setdefault(token, set()).add(relative)
            direct_owners.setdefault(token, set()).add((target, line))
            source_lines[target] = target_lines
            owner_hits.setdefault(target, set()).add((owner, line, 0, 0))
        same_file_owners[relative] = definitions
        file_exports[relative] = exported_names(lines, suffix)
        changed_file_ranges[relative] = ranges
        source_lines[relative] = lines

    for relative in changed:
        path = root / relative
        if path.suffix.lower() not in SOURCE_SUFFIXES or path.is_symlink():
            continue
        if path.is_file():
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeError):
                continue
            ranges = changed_ranges(root, relative, base)
            prepare(relative, lines, ranges)
            for revisions in ((f"{base}...HEAD",), ("--cached",), ()):
                diff = command(root, "diff", "--unified=0", *revisions, "--", relative)
                identifiers.update(
                    name for line in diff.splitlines() if line[:1] in {"+", "-"} and not line.startswith(("+++", "---"))
                    for name in definition_names(line[1:], path.suffix.lower())
                    if searchable_owner(relative, name, file_exports[relative])
                )
                for line in diff.splitlines():
                    if line[:1] in {"+", "-"} and not line.startswith(("+++", "---")):
                        record(relative, line[1:])
        else:
            lines = command(root, "show", f"{base}:{relative}").splitlines()
            ranges = ((1, max(1, len(lines))),) if lines else ()
            prepare(relative, lines, ranges)
        for first, last in ranges:
            found = False
            for line_number, line in enumerate(
                lines[max(0, first - 1) : min(len(lines), last)], max(1, first)
            ):
                names = definition_names(line, path.suffix.lower())
                identifiers.update(
                    name for name in names if searchable_owner(relative, name, file_exports[relative])
                )
                record(relative, line)
                for name in names:
                    if owner_requires_context(lines, line_number, ranges, path.suffix.lower()):
                        owner_hits.setdefault(relative, set()).add((name, line_number, first, last))
                found = found or bool(names)
            if not found and (owner := enclosing_owner(lines, first, path.suffix.lower())):
                owner_name, owner_line = owner
                owner_searchable = searchable_owner(relative, owner_name, file_exports[relative])
                if owner_searchable:
                    identifiers.add(owner_name)
                coverage.setdefault(relative, set()).add(("symbol", owner_name))
                token_families.setdefault(("symbol", owner_name), set()).add(language_family(relative))
                token_scopes.setdefault(("symbol", owner_name), set()).add(package_scope(root, relative))
                if owner_requires_context(lines, owner_line, ranges, path.suffix.lower()):
                    owner_hits.setdefault(relative, set()).add((owner_name, owner_line, first, last))
    sections: list[tuple[str, str, str]] = []
    for relative, hits in sorted(owner_hits.items()):
        owners = sorted({(name, line) for name, line, _, _ in hits}, key=lambda item: item[1])
        if len(owners) == 1:
            name, line = owners[0]
            label = f"## Nearby owner: {relative}:{line} ({name})"
        else:
            labels = ",".join(f"{name}@{line}" for name, line in owners)
            label = f"## Nearby owners: {relative} ({labels})"
        sections.append((
            relative,
            label,
            owner_slices(source_lines[relative], hits, Path(relative).suffix.lower()),
        ))
    coverage_counts: dict[tuple[str, str], int] = {}
    coverage_shown: dict[tuple[str, str], int] = {}
    indexed_matches = repository_matches(root, token_families, token_scopes)
    for identifier in sorted(identifiers | reference_identifiers):
        candidates: list[tuple[str, int, bool]] = [
            (relative, line, True) for relative, line in sorted(direct_owners.get(("symbol", identifier), set()))
        ]
        for relative, line_number, source_line in indexed_matches.get(("symbol", identifier), ()):
            if (
                relative in changed or Path(relative).suffix.lower() not in SOURCE_SUFFIXES
            ):
                continue
            candidates.append((
                relative,
                line_number,
                identifier in (*definition_names(source_line, Path(relative).suffix.lower()), *assignment_names(source_line)),
            ))
        changed_owner = any(identifier in owners for owners in same_file_owners.values())
        if (
            ("symbol", identifier) not in required_by
            and identifier in reference_identifiers
            and identifier not in identifiers
            and not any(is_owner for _, _, is_owner in candidates)
        ):
            coverage_counts[("symbol", identifier)] = 0
            coverage_shown[("symbol", identifier)] = 0
            continue
        coverage_counts[("symbol", identifier)] = len(candidates) + int(changed_owner)
        if ("symbol", identifier) in required_by and not any(is_owner for _, _, is_owner in candidates):
            if not changed_owner:
                source = sorted(required_by[("symbol", identifier)])[0]
                raise RelatedContextError(f"unresolved required local import: {identifier} from {source}")
        selected = candidates if identifier in identifiers else bounded_references(candidates)
        coverage_shown[("symbol", identifier)] = len(selected) + int(changed_owner)
        for relative, line, is_owner in selected:
            if (relative, line) in direct_owners.get(("symbol", identifier), set()):
                continue
            kind = relationship_kind(relative, is_owner)
            related_hits.setdefault((relative, kind), set()).add((line, identifier))

    for literal in sorted(reference_literals):
        candidates: list[tuple[str, int, bool]] = []
        for relative, line_number, source_line in indexed_matches.get(("literal", literal), ()):
            if (
                relative in changed or Path(relative).suffix.lower() not in SOURCE_SUFFIXES
            ):
                continue
            candidates.append((relative, line_number, bool(assignment_names(source_line))))
        coverage_counts[("literal", literal)] = len(candidates)
        selected = bounded_references(candidates)
        coverage_shown[("literal", literal)] = len(selected)
        for relative, line, is_owner in selected:
            kind = relationship_kind(relative, is_owner)
            related_hits.setdefault((relative, kind), set()).add((line, literal))

    for (relative, kind), hits in sorted(related_hits.items()):
        line_numbers = {line for line, _ in hits}
        labels = ",".join(sorted({label for _, label in hits}))
        sections.append((
            relative,
            f"## Related {kind}: {relative}:{min(line_numbers)} ({labels})",
            context_slices(root, relative, line_numbers),
        ))

    manifest = []
    for relative in sorted(coverage):
        matched = [
            f"{kind}:{value}={coverage_shown.get((kind, value), 0)}/{coverage_counts[(kind, value)]}"
            for kind, value in sorted(coverage[relative])
            if coverage_counts.get((kind, value), 0)
        ]
        required_unresolved = sum(token in required_by and not coverage_counts.get(token, 0)
                                  for token in coverage[relative])
        optional_unresolved = sum(token not in required_by and not coverage_counts.get(token, 0)
                                  for token in coverage[relative])
        values = ",".join((*matched, f"required-unresolved={required_unresolved}",
                           f"optional-unresolved={optional_unresolved}"))
        manifest.append(f"{relative} | {values}")
    sections.append(("<coverage>", "## Related coverage", "\n".join(manifest)))

    if len(sections) > max_sections:
        fixed = [
            entry for entry in sections
            if entry[1] == "## Related coverage" or not entry[1].startswith("## Related ")
        ]
        collapsed = []
        for kind in ("owner", "caller", "test"):
            chunks = []
            paths = []
            for (relative, hit_kind), hits in sorted(related_hits.items()):
                if hit_kind != kind:
                    continue
                line_numbers = {line for line, _ in hits}
                chunks.append(
                    f"### {relative}\n"
                    + context_slices(root, relative, line_numbers, radius=0)
                )
                paths.append(relative)
            if chunks:
                collapsed.append((
                    ",".join(paths),
                    f"## Related {kind} exact-line index",
                    "\n...\n".join(chunks),
                ))
        sections = [*fixed, *collapsed]

    prioritized: list[tuple[str, str, str]] = []
    remaining = list(sections)
    for marker in ("## Related coverage", "## Nearby owner:", "## Related owner:", "## Related caller:", "## Related test:"):
        if index := next((i + 1 for i, entry in enumerate(remaining) if entry[1].startswith(marker)), 0):
            prioritized.append(remaining.pop(index - 1))
    prioritized.extend(remaining)
    if len(prioritized) > max_sections:
        raise RelatedContextError(
            f"required related context exceeds {max_sections} sections: {prioritized[max_sections][1]}"
        )
    size = 0
    for entry in prioritized:
        entry_size = sum(len(value.encode("utf-8")) for value in entry)
        if size + entry_size > max_bytes:
            raise RelatedContextError(
                f"required related context exceeds {max_bytes} bytes: {entry[1]}"
            )
        size += entry_size
    return tuple(prioritized)

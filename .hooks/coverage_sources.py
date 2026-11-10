"""Prove omitted TypeScript and Swift files have no runtime content without executing them."""

import json
import re
import subprocess
from pathlib import Path

from gate_config import Group, nonproduction_source

IF_DIRECTIVE = re.compile(r"(?m)^\s*#if\b")


def erased_typescript(files: set[Path]) -> set[Path]:
    candidates = sorted(
        file for file in files if file.suffix in {".ts", ".tsx", ".mts", ".cts"}
    )
    if not candidates:
        return set()
    script = """
const sources = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
console.log(JSON.stringify(sources.map(([loader, source]) => {
  try { return new Bun.Transpiler({ loader }).transformSync(source); }
  catch { return null; }
})));
"""
    result = subprocess.run(
        ["bun", "-e", script],
        input=json.dumps(
            [
                ["tsx" if file.suffix == ".tsx" else "ts", file.read_text()]
                for file in candidates
            ]
        ),
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    outputs = json.loads(result.stdout)
    if not isinstance(outputs, list) or len(outputs) != len(candidates):
        raise ValueError("Invalid native TypeScript stripping result")
    # Only whitespace, comments, empty statements and an empty export remain.
    empty = (
        r"(?:\s|;|//[^\r\n\u2028\u2029]*|"
        r"/\*(?:[^*]|\*(?!/))*\*/|export\s*\{\s*\})*"
    )
    return {
        file
        for file, output in zip(candidates, outputs, strict=True)
        if isinstance(output, str) and re.fullmatch(empty, output)
    }


COUNTER_NODES = ("brace_stmt", "closure_expr", "original_init", "top_level_code_decl")


def erased_swift(files: set[Path]) -> set[Path]:
    """Parse-only proof: no body, closure or initial value, so Xcode lists no counters."""
    erased = set()
    for file in sorted(files):
        if IF_DIRECTIVE.search(file.read_text()):
            continue  # The parse drops code inside conditional compilation.
        parsed = subprocess.run(
            ["swiftc", "-frontend", "-dump-parse", str(file)],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if parsed.returncode == 0 and not any(
            f"({node}" in parsed.stdout for node in COUNTER_NODES
        ):
            erased.add(file)
    return erased


def source_roots(directory: Path, language: str, files: list[Path]) -> set[str]:
    """Top-level names that hold a package's production code."""
    extensions = {
        "python": {".py"},
        "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"},
        "dart": {".dart"},
    }
    sources = set()
    for path in files:
        if (
            not path.is_relative_to(directory)
            or path.suffix not in extensions[language]
        ):
            continue
        relative = path.relative_to(directory)
        if nonproduction_source(relative) or {".hooks", ".agents"} & set(
            relative.parts
        ):
            continue
        sources.add(relative.parts[0])
    return sources


def owned_files(
    root: Path, packages: list[Group], files: list[Path]
) -> dict[Path, list[Path]]:
    """Each file belongs to the package nearest to it."""
    owned: dict[Path, list[Path]] = {root / package["path"]: [] for package in packages}
    for path in files:
        owner = next((parent for parent in path.parents if parent in owned), None)
        if owner is not None:
            owned[owner].append(path)
    return owned


def require_listed_sources(
    root: Path, packages: list[Group], files: list[Path]
) -> None:
    """Code added after setup is checked only once its package lists it."""
    owned = owned_files(root, packages, files)
    for group in packages:
        language = group.get("language", "")
        if language not in {"python", "javascript", "dart"}:
            continue
        directory = root / group["path"]
        if missing := sorted(
            source_roots(directory, language, owned[directory])
            - set(group.get("sources", []))
        ):
            label = {"javascript": "JavaScript"}.get(language, language.title())
            checks = (
                " and to every check that names them (tests --cov=, annotations, dead-code, duplicates)"
                if language == "python"
                else ""
            )
            raise ValueError(
                f"{group['path']}: {label} code is outside its sources: {', '.join(missing)}; "
                f"add each to that package's `sources` list in hard-eng.gates.json{checks}"
            )

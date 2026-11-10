"""Prove omitted TypeScript and Swift files have no runtime content without executing them."""

import json
import os
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
    # Text prefixes, longest first: building each file's parents made large projects slow.
    prefixes = sorted(
        ((f"{directory}{os.sep}", paths) for directory, paths in owned.items()),
        key=lambda item: -len(item[0]),
    )
    for path in files:
        text = str(path)
        for prefix, paths in prefixes:
            if text.startswith(prefix):
                paths.append(path)
                break
    return owned


def require_listed_sources(
    root: Path, packages: list[Group], files: list[Path], python_only: bool
) -> None:
    """Code added after setup is checked only once its package lists it."""
    languages = {"python"} if python_only else {"python", "javascript", "dart"}
    groups = [group for group in packages if group.get("language") in languages]
    if not groups:
        return
    owned = owned_files(root, packages, files)
    for group in groups:
        language = group["language"]
        directory = root / group["path"]
        listed = tuple(os.path.normpath(source) for source in group.get("sources", []))
        if "." in listed:
            continue
        inside = tuple(f"{source}{os.sep}" for source in listed)
        start = len(str(directory)) + 1
        unlisted = [
            path
            for path in owned[directory]
            if (name := str(path)[start:]) not in listed and not name.startswith(inside)
        ]
        if missing := sorted(source_roots(directory, language, unlisted)):
            label = {"javascript": "JavaScript"}.get(language, language.title())
            add = "add each to that package's `sources` list in hard-eng.gates.json"
            tests = "Test-only code belongs in test/, tests/ or __tests__/."
            first = missing[0]
            steps = {
                "python": f"{add} and to every check that names them (tests --cov=, annotations, dead-code, duplicates)",
                "javascript": f"{add}. TypeScript also needs each in the `include` list of the package's TypeScript configuration. Tests must then cover that code. {tests}",
                "dart": f"move each under lib/ (for example {first} to lib/{first}) and test it there. Or {add}. Tests must then cover that code, and those tests need `test` as a dev dependency and a setup rerun. {tests}",
            }[language]
            raise ValueError(
                f"{group['path']}: {label} code is outside its sources: {', '.join(missing)}; {steps}"
            )

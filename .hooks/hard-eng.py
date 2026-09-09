#!/usr/bin/env python3
"""Run native gate commands and handle the three agreed hook events."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import tomllib
import xml.etree.ElementTree as ET
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import TypedDict, cast
from urllib.parse import unquote, urljoin, urlparse

from gate_config import Gate, Group, JsonObject, Report, nonproduction_source
from tool_setup import managed_command, provision_tools

DartAnalyzer = TypedDict(
    "DartAnalyzer",
    {"exclude": list[str], "errors": dict[str, str], "language": dict[str, bool]},
    total=False,
)
DartLinter = TypedDict(
    "DartLinter", {"rules": dict[str, bool] | list[str]}, total=False
)
DartOptions = TypedDict(
    "DartOptions",
    {"include": str | list[str], "analyzer": DartAnalyzer, "linter": DartLinter},
    total=False,
)


ROOT = Path(__file__).resolve().parents[1]
DART_TYPING: dict[str, dict[str, dict[str, bool] | list[str]]] = {
    "analyzer": {
        "exclude": [],
        "language": {
            "strict-casts": True,
            "strict-inference": True,
            "strict-raw-types": True,
        },
    },
    "linter": {
        "rules": {
            "avoid_annotating_with_dynamic": True,
            "avoid_dynamic_calls": True,
            "strict_top_level_inference": True,
            "unawaited_futures": True,
        }
    },
}


def dart_options(path: Path) -> DartOptions:
    try:
        import yaml
    except ImportError as error:
        raise ValueError(
            "Dart configuration checks require PyYAML in the Python environment"
        ) from error
    try:
        options = yaml.safe_load(path.read_text())
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid Dart analysis settings: {path}") from error
    if not isinstance(options, dict):
        raise TypeError(f"Dart analysis settings must be a mapping: {path}")
    return cast(DartOptions, options)


def validate_dart_includes(
    path: Path, directory: Path, seen: set[Path] | None = None
) -> None:
    seen = set() if seen is None else seen
    path = path.resolve()
    if path in seen:
        raise ValueError(f"Recursive Dart analysis include: {path}")
    seen.add(path)
    options = dart_options(path)
    analyzer = options.get("analyzer", {})
    if analyzer.get("exclude") or any(
        value == "ignore" for value in analyzer.get("errors", {}).values()
    ):
        raise ValueError(
            f"Dart strict analysis cannot exclude files or ignore diagnostics: {path}"
        )
    includes = options.get("include", [])
    for include in [includes] if isinstance(includes, str) else includes:
        if include.startswith("package:"):
            name, relative = include.removeprefix("package:").split("/", 1)
            registry = directory / ".dart_tool/package_config.json"
            packages = json.loads(registry.read_text())["packages"]
            package = next((item for item in packages if item["name"] == name), None)
            if package is None:
                raise ValueError(f"Unresolved Dart analysis include: {include}")
            uri = urljoin(
                urljoin(registry.as_uri(), package["rootUri"]),
                package.get("packageUri", "lib/"),
            )
            uri = urlparse(urljoin(uri, relative))
            if uri.scheme != "file":
                raise ValueError(f"Unsupported Dart analysis include: {include}")
            included = Path(unquote(uri.path))
        else:
            included = path.parent / include
        validate_dart_includes(included, directory, seen.copy())


def validate_typing(
    directory: Path,
    language: str | None,
    sources: list[str] | tuple[str, ...] = (),
    package_root: Path | None = None,
) -> None:
    if language == "python":
        native = directory / "pyrefly.toml"
        options = (
            tomllib.loads(native.read_text())
            if native.exists()
            else tomllib.loads((directory / "pyproject.toml").read_text())
            .get("tool", {})
            .get("pyrefly", {})
        )
        if (
            options.get("preset") not in {"strict", "all"}
            or options.get("check-unannotated-defs", True) is not True
            or any(
                value in (False, "ignore")
                for value in options.get("errors", {}).values()
            )
            or options.get("ignore-missing-imports")
            or options.get("replace-imports-with-any")
            or options.get("replace-untyped-imports-with-any")
            or options.get("sub-config")
        ):
            raise ValueError(
                "Pyrefly requires strict checking without disabled diagnostics or Any import substitutions"
            )
    elif language == "dart":
        validate_dart_typing(directory, sources, package_root)


def validate_dart_typing(
    directory: Path, sources: list[str] | tuple[str, ...], package_root: Path | None
) -> None:
    options = dart_options(directory / "analysis_options.yaml")
    for section, groups in DART_TYPING.items():
        for group, settings in groups.items():
            section_options = cast(JsonObject, options).get(section)
            if not isinstance(section_options, dict):
                raise TypeError(f"Dart requires {section} settings")
            actual = section_options.get(group)
            if isinstance(settings, list):
                if actual != settings:
                    raise ValueError(
                        "Dart strict analysis cannot exclude project files"
                    )
                continue
            if not isinstance(actual, dict) or any(
                actual.get(key) != value for key, value in settings.items()
            ):
                raise ValueError(f"Dart requires strict {section}.{group} settings")
    validate_dart_includes(
        directory / "analysis_options.yaml", package_root or directory
    )
    for source in {*sources, "test", "tests"}:
        for nested in (directory / source).rglob("analysis_options.yaml"):
            if nested.parent != directory:
                validate_typing(
                    nested.parent, "dart", package_root=package_root or directory
                )


def test_arguments(command: list[str], directory: Path) -> list[str]:
    arguments = list(command)
    scripts_seen = set()
    while (
        Path(arguments[0]).name == "npm"
        and len(arguments) > 2
        and arguments[1] in {"run", "run-script"}
    ):
        if arguments[2] in scripts_seen:
            raise ValueError("Recursive npm test script")
        scripts_seen.add(arguments[2])
        package = json.loads((directory / "package.json").read_text())
        script = package.get("scripts", {}).get(arguments[2])
        if not isinstance(script, str):
            raise TypeError("Configured npm test script is missing")
        arguments = shlex.split(script) + arguments[3:]
        if not arguments:
            raise ValueError("Configured npm test script is empty")
    return arguments


def reject_test_filters(
    command: list[str], directory: Path, language: str | None
) -> None:
    arguments = test_arguments(command, directory)
    if language == "python":
        short_flags = ()
        for index, argument in enumerate(arguments):
            if Path(argument).name in {"pytest", "py.test"}:
                arguments = arguments[index + 1 :]
                arguments += shlex.split(os.environ.get("PYTEST_ADDOPTS", ""))
                short_flags = ("-k", "-m")
                break
        long_flags = {"--lf", "--last-failed", "--deselect", "--stepwise", "--sw"}
    elif language == "javascript":
        long_flags = {
            "--test-only",
            "--test-name-pattern",
            "--test-skip-pattern",
            "--testNamePattern",
            "--testPathPattern",
            "--testPathPatterns",
            "--testPathIgnorePatterns",
            "--grep",
            "--fgrep",
            "--changed",
            "--onlyChanged",
            "--findRelatedTests",
            "--related",
            "--onlyFailures",
        }
        short_flags = ("-t", "-g", "-f")
    else:
        long_flags = {"--name", "--plain-name", "--tags", "--exclude-tags"}
        short_flags = ("-n", "-N", "-t", "-x")
    for argument in arguments:
        if (
            argument.split("=", 1)[0] in long_flags
            or argument.startswith(short_flags)
            or (language == "python" and "::" in argument)
        ):
            raise ValueError(
                f"Focused test selection is not allowed in the full-suite gate: {argument}"
            )


def production_files(
    directory: Path, group: Group, *, include_tests: bool = False
) -> set[Path]:
    extensions = {
        "python": {".py"},
        "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"},
        "dart": {".dart"},
    }
    language, sources = group.get("language"), group.get("sources")
    if language not in extensions or not isinstance(sources, list) or not sources:
        raise ValueError(
            "Test packages must declare their language and production sources"
        )
    files = set()
    for source in sources:
        if not isinstance(source, str) or not source:
            raise ValueError("Production sources must be nonempty paths")
        root = (directory / source).resolve()
        if not root.is_relative_to(directory) or not root.exists():
            raise ValueError(
                f"Production source must exist inside its package: {source}"
            )
        for file in [root] if root.is_file() else root.rglob("*"):
            if file.is_file() and file.suffix in extensions[language]:
                if file.name.endswith((".d.ts", ".d.mts", ".d.cts")) or (
                    not include_tests
                    and nonproduction_source(file.relative_to(directory))
                ):
                    continue
                resolved = file.resolve()
                if not resolved.is_relative_to(directory):
                    raise ValueError(
                        f"Production source points outside its package: {file}"
                    )
                files.add(resolved)
    if not files:
        raise ValueError("Production sources contain no supported source files")
    return files


def prepare_command(group: Group, gate: Gate, timeout: float) -> list[str]:
    command = gate["command"]
    if gate.get("role") == "types":
        directory = ROOT / group["path"]
        language = group.get("language")
        validate_typing(directory, language, group.get("sources", []))
        if language == "python":
            native = (
                "pyrefly.toml"
                if (directory / "pyrefly.toml").exists()
                else "pyproject.toml"
            )
            scope: Group = {
                **group,
                "sources": [
                    *group.get("sources", []),
                    *(
                        name
                        for name in ("test", "tests")
                        if (directory / name).is_dir()
                    ),
                ],
            }
            command = [
                *command,
                "--config",
                native,
                *map(
                    str, sorted(production_files(directory, scope, include_tests=True))
                ),
            ]
        elif language == "javascript":
            validate_typescript(command, directory, group, timeout)
    return managed_command(command)


def validate_typescript(
    command: list[str], directory: Path, group: Group, timeout: float
) -> None:
    result = subprocess.run(
        [*command, "--showConfig"],
        cwd=directory,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=True,
    )
    actual = json.loads(result.stdout)
    options = actual.get("compilerOptions", {})
    strict = (
        "noImplicitAny",
        "noImplicitThis",
        "strictNullChecks",
        "strictFunctionTypes",
        "strictBindCallApply",
        "strictPropertyInitialization",
        "strictBuiltinIteratorReturn",
        "useUnknownInCatchVariables",
        "alwaysStrict",
    )
    if (
        options.get("strict") is not True
        or any(options.get(name, True) is not True for name in strict)
        or options.get("checkJs") is not True
        or options.get("noCheck", False) is not False
    ):
        raise ValueError(
            "TypeScript requires all strict checks and JavaScript checking without noCheck"
        )
    files = {(directory / name).resolve() for name in actual.get("files", [])}
    expected = production_files(directory, group)
    if not {(directory / name).resolve() for name in expected} <= files:
        raise ValueError("TypeScript configuration omits declared production files")


def prepare_reports(
    group: Group,
    report: Report,
    kind: str | None,
    tests: bool,
    scanner: str | None,
    command: list[str],
) -> tuple[Path, Path | None, Path, set[Path]]:
    coverage_path = None
    expected_sources = set()
    supported = {"python-tests", "lcov-tests", "dart-tests"} if tests else {scanner}
    names = ("tests", "coverage") if tests else ("path",)
    if kind not in supported or any(
        not isinstance(report.get(name), str) or not report[name] for name in names
    ):
        raise ValueError("Check must declare complete supported reports")
    directory = (ROOT / group["path"]).resolve()
    paths = [(directory / report[name]).resolve() for name in names]
    if len(set(paths)) != len(paths) or any(
        not path.is_relative_to(directory) or path == directory for path in paths
    ):
        raise ValueError("Reports must be separate package files")
    report_path = paths[0]
    if tests:
        coverage_path = paths[1]
        expected_sources = production_files(directory, group)
        reject_test_filters(command, directory, group["language"])
    elif scanner == "import-linter" and any(
        argument.split("=", 1)[0] == "--contract" for argument in command
    ):
        raise ValueError("Import Linter must run all configured contracts")
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
    return report_path, coverage_path, directory, expected_sources


def run_gate(
    group: Group,
    gate: Gate,
    timeout: float,
    output_lock: AbstractContextManager[object],
) -> bool:
    failed = False
    print(f"CHECK {group['path']}/{gate['name']}", flush=True)
    try:
        report_path = coverage_path = None
        directory = ROOT / group["path"]
        expected_sources: set[Path] = set()
        command = prepare_command(group, gate, timeout)
        from reports import SCANNER_LOGS, SCANNERS

        report = gate.get("report", {})
        kind = report.get("type", "")
        tests = gate.get("role") == "tests"
        scanner = {
            "secrets-files": "gitleaks",
            "secrets-history": "gitleaks",
            "security": "semgrep",
            "vulnerabilities": "osv",
            "container-vulnerabilities": "osv-image",
            "react": "react-doctor",
            "deployment": "trivy",
        }.get(gate.get("role", ""), kind if kind in SCANNERS else None)
        scanner = {
            ("python", "imports"): "import-linter",
            ("python", "dependencies"): "deptry",
            ("python", "duplicates"): "jscpd",
            ("dart", "dead-code-duplicates"): "dart-decimate",
            ("javascript", "dead-code-duplicates"): "fallow",
        }.get((group.get("language", ""), gate.get("role", "")), scanner)
        if tests or scanner:
            report_path, coverage_path, directory, expected_sources = prepare_reports(
                group, report, kind, tests, scanner, command
            )
        capture = (tests and kind == "dart-tests" and report.get("stdout", True)) or (
            scanner and report.get("stdout") is True
        )
        with tempfile.TemporaryFile(
            mode="w+", encoding="utf-8", errors="replace"
        ) as log:
            try:
                with (
                    report_path.open("w")
                    if capture and report_path is not None
                    else nullcontext() as output
                ):
                    result = subprocess.run(
                        command,
                        cwd=ROOT / group["path"],
                        check=False,
                        timeout=timeout,
                        stdout=output if capture else log,
                        stderr=log,
                    )
            finally:
                with output_lock:
                    print(f"OUTPUT {group['path']}/{gate['name']}", flush=True)
                    log.seek(0)
                    shutil.copyfileobj(log, sys.stdout)
            if scanner in SCANNER_LOGS:
                SCANNER_LOGS[scanner](log)
        if result.returncode == 0 and scanner and report_path is not None:
            SCANNERS[scanner](report_path)
        from reports import completed_tests, line_coverage

        if (
            result.returncode == 0
            and tests
            and report_path is not None
            and not completed_tests(report_path, kind)
        ):
            raise ValueError("No tests actually ran (empty or entirely skipped report)")
        if result.returncode == 0 and coverage_path is not None:
            covered, total = line_coverage(
                coverage_path, kind, directory, expected_sources
            )
            print(
                f"Line coverage: {covered}/{total} ({100 * covered / total:.2f}%; minimum 70%)"
            )
            if covered * 100 < total * 70:
                raise ValueError("Line coverage is below the required 70%")
        print(
            f"{'PASS' if result.returncode == 0 else 'FAIL'} {gate['name']} (exit {result.returncode})",
            flush=True,
        )
        failed |= result.returncode != 0
    except (
        ImportError,
        OSError,
        TypeError,
        ValueError,
        ET.ParseError,
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
    ) as error:
        print(f"FAIL {gate['name']}: {error}")
        failed = True
    return failed


def check(timeout: float = 600, base: str | None = None) -> int:
    from gate_config import load_groups
    from update import check_scaffold_update

    if base is not None and check_scaffold_update(ROOT, base):
        return 0

    groups = load_groups(ROOT, base)
    provision_tools(ROOT, groups, timeout)
    output_lock = threading.Lock()

    failed = False
    pending: set[Future[bool]] = set()
    checks = [(group, gate) for group in groups for gate in group["checks"]]
    ordered = [item for item in checks if item[1].get("role") == "lockfiles"]
    ordered += [item for item in checks if item[1].get("role") != "lockfiles"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for group, gate in ordered:
            if gate.get("parallel", False) and gate.get("role") != "lockfiles":
                if len(pending) == 2:
                    done, pending = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        failed |= future.result()
                pending.add(pool.submit(run_gate, group, gate, timeout, output_lock))
            else:
                for future in pending:
                    failed |= future.result()
                pending.clear()
                result = run_gate(group, gate, timeout, output_lock)
                failed |= result
                if result and gate.get("role") == "lockfiles":
                    print("Dependency setup failed; remaining checks were not run.")
                    return 1
        for future in pending:
            failed |= future.result()
    return int(failed)


def pre_push() -> int:
    for line in sys.stdin:
        fields = line.split()
        if len(fields) != 4:
            raise ValueError("Invalid pre-push input")
        revision = fields[1]
        if set(revision) == {"0"}:
            continue
        with tempfile.TemporaryDirectory(prefix="hard-eng-push-") as temporary:
            checkout = Path(temporary) / "project"
            subprocess.run(
                ["git", "worktree", "add", "--detach", str(checkout), revision],
                cwd=ROOT,
                check=True,
            )
            try:
                result = subprocess.run(
                    [
                        sys.executable,
                        str(checkout / ".hooks/hard-eng.py"),
                        "check",
                        "--base",
                        fields[3],
                    ],
                    cwd=checkout,
                    check=False,
                )
                if result.returncode:
                    return result.returncode
            finally:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", str(checkout)],
                    cwd=ROOT,
                    check=True,
                )
    return 0


def agent_hook(event: str, agent: str) -> int:
    from agent_hooks import handle_event

    return handle_event(ROOT, event, agent)


def main() -> int:
    import argparse

    if Path(sys.argv[0]).name == "pre-push":
        return pre_push()
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    checks = commands.add_parser("check", help="Run applicable native checks")
    checks.add_argument(
        "--base", help="Git comparison base; unknown impact runs all checks"
    )
    commands.add_parser("pre-push", help="Verify the actual commits being pushed")
    for event in ("session", "stop"):
        hook = commands.add_parser(event, help=f"Handle a native {event} hook")
        hook.add_argument("agent", choices=("claude", "codex", "copilot"))
    args = parser.parse_args()
    if args.command == "check":
        return check(base=args.base)
    if args.command == "pre-push":
        return pre_push()
    return agent_hook(args.command, args.agent)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (
        ImportError,
        OSError,
        TypeError,
        ValueError,
        KeyError,
        subprocess.SubprocessError,
    ) as error:
        print(f"Hard Eng: {error}", file=sys.stderr)
        raise SystemExit(1) from error

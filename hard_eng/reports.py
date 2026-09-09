"""Validate native reports; an exit code alone cannot prove a complete scan."""

from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from hard_eng.common import GateError, Json, array, object_value, read_json, relative_path
from hard_eng.config import Check, Package

EXTENSIONS = {
    "python": {".py"},
    "javascript": {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"},
    "dart": {".dart"},
}


def generated(path: Path) -> bool:
    if not path.is_file():
        return False
    header = "\n".join(path.read_text().splitlines()[:12])
    return bool(
        re.search(
            r"(?im)^\s*(?://|#|/\*|\*)\s*(?:.*\b(?:GENERATED CODE|CODE GENERATED|AUTO[- ]?GENERATED)\b|@generated\b)",
            header,
        )
    )


def production_source(path: Path) -> bool:
    if any(part in {"vendor", "node_modules", ".venv", "__tests__", "tests", "test"} for part in path.parts):
        return False
    if re.search(r"(?:\.(?:test|spec|d)\.[cm]?[jt]sx?$|^test_.*\.py$|_test\.dart$)", path.name):
        return False
    return not generated(path)


def production_files(package: Package) -> set[Path]:
    files: set[Path] = set()
    for source in package.sources:
        path = relative_path(package.path, source)
        candidates = path.rglob("*") if path.is_dir() else [path]
        files.update(
            item.resolve()
            for item in candidates
            if item.is_file() and item.suffix in EXTENSIONS[package.language] and production_source(item)
        )
    if not files:
        raise GateError(f"{package.name}: no production source files found")
    return files


def number(value: object, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
        or not math.isfinite(value)
    ):
        raise GateError(f"{label}: expected a nonnegative number")
    return float(value)


def report_path(check: Check, key: str) -> Path:
    value = check.report.get(key)
    if not isinstance(value, str) or not value:
        raise GateError(f"{check.name}: missing report {key}")
    return relative_path(check.cwd, value)


def expected_reports(check: Check) -> list[Path]:
    kind = check.report.get("type")
    if kind in {"python-tests", "lcov-tests", "dart-tests"}:
        return [report_path(check, "tests"), report_path(check, "coverage")]
    if kind == "junit":
        return [report_path(check, "tests")]
    if kind is not None:
        return [report_path(check, "path")]
    return []


def tests(path: Path, minimum: float) -> int:
    try:
        tree = ET.parse(path)
        cases = list(tree.iter("testcase"))
    except (OSError, ET.ParseError) as error:
        raise GateError("Missing or invalid JUnit test report") from error
    completed = [case for case in cases if case.find("skipped") is None]
    if len(completed) < minimum:
        raise GateError(
            f"Unexpectedly empty/incomplete test run: {len(completed)} executed; require {minimum:g}"
        )
    if any(case.find("failure") is not None or case.find("error") is not None for case in cases):
        raise GateError("Test report contains failures/errors despite successful command exit")
    return len(completed)


def dart_events(path: Path) -> list[Json]:
    events: list[Json] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        value: object = json.loads(line)
        if isinstance(value, list):
            for frame in array(value, "Flutter daemon frames"):
                if object_value(frame, "Flutter daemon event").get("event") != "test.startedProcess":
                    raise GateError("Unexpected Flutter machine frame")
        else:
            events.append(object_value(value, "Dart test event"))
    return events


def dart_tests(path: Path, minimum: float) -> int:
    events = dart_events(path)
    completed = [
        event
        for event in events
        if event.get("type") == "testDone" and not event.get("hidden") and not event.get("skipped")
    ]
    done = [event for event in events if event.get("type") == "done"]
    if not done or done[-1].get("success") is not True:
        raise GateError("Dart test run did not finish successfully")
    if any(event.get("result") != "success" for event in completed) or any(
        event.get("type") == "error" for event in events
    ):
        raise GateError("Dart test report contains failures/errors")
    if len(completed) < minimum:
        raise GateError("Unexpectedly empty/incomplete Dart test run")
    return len(completed)


def coverage_totals(files: Json, root: Path) -> tuple[set[Path], float, float, float, float]:
    seen: set[Path] = set()
    covered = statements = branches = covered_branches = 0.0
    for name, value in files.items():
        if not production_source(relative_path(root, name)):
            continue
        item = object_value(value, "coverage file")
        summary = object_value(item.get("summary"), "coverage summary")
        seen.add(relative_path(root, name).resolve())
        covered += number(summary.get("covered_lines"), "covered lines")
        statements += number(summary.get("num_statements"), "executable lines")
        branches += number(summary.get("num_branches", 0), "branches")
        covered_branches += number(summary.get("covered_branches", 0), "covered branches")
    return seen, covered, statements, covered_branches, branches


def require_coverage(
    seen: set[Path], expected: set[Path], covered: float, total: float, threshold: float
) -> float:
    if seen != expected:
        missing, extra = len(expected - seen), len(seen - expected)
        raise GateError(
            f"Coverage scope mismatch: {missing} production files missing; {extra} unexpected files"
        )
    if not total or covered > total:
        raise GateError("Coverage has no executable lines or invalid counts")
    percent = 100 * covered / total
    if percent < threshold:
        raise GateError(f"Executable-line coverage {percent:.2f}% is below {threshold:g}%")
    return percent


def python_coverage(check: Check, package: Package, threshold: float) -> str:
    data = read_json(report_path(check, "coverage"))
    values = coverage_totals(object_value(data.get("files"), "coverage files"), check.cwd)
    seen, covered, total, covered_branches, branches = values
    percent = require_coverage(seen, production_files(package), covered, total, threshold)
    branch_text = f"; branches {100 * covered_branches / branches:.2f}%" if branches else ""
    return f"lines {percent:.2f}%{branch_text}"


def lcov_counts(lines: list[str]) -> tuple[int, int, int, int]:
    covered = total = covered_branches = branches = 0
    for line in lines:
        if line.startswith("DA:"):
            fields = line[3:].split(",")
            if len(fields) < 2 or not fields[0].isdigit() or not fields[1].isdigit():
                raise GateError("Invalid LCOV line counts")
            total += 1
            covered += int(fields[1]) > 0
        elif line.startswith("BRDA:"):
            fields = line[5:].split(",")
            if len(fields) != 4 or (fields[3] != "-" and not fields[3].isdigit()):
                raise GateError("Invalid LCOV branch counts")
            branches += 1
            covered_branches += fields[3] != "-" and int(fields[3]) > 0
    return covered, total, covered_branches, branches


def lcov_coverage(check: Check, package: Package, threshold: float) -> str:
    try:
        text = report_path(check, "coverage").read_text()
    except OSError as error:
        raise GateError("Missing LCOV report") from error
    seen: set[Path] = set()
    covered = total = 0
    covered_branches = branches = 0
    for record in text.split("end_of_record"):
        lines = record.strip().splitlines()
        sources = [line[3:] for line in lines if line.startswith("SF:")]
        if not sources:
            continue
        if len(sources) != 1:
            raise GateError("Invalid LCOV source record")
        source = Path(sources[0])
        source = source.resolve() if source.is_absolute() else relative_path(check.cwd, str(source)).resolve()
        if not production_source(source):
            continue
        if source in seen:
            raise GateError("Duplicate LCOV source record")
        seen.add(source)
        hits, count, branch_hits, branch_count = lcov_counts(lines)
        covered += hits
        total += count
        covered_branches += branch_hits
        branches += branch_count
    percent = require_coverage(seen, production_files(package), covered, total, threshold)
    branch_text = f"; branches {100 * covered_branches / branches:.2f}%" if branches else ""
    return f"lines {percent:.2f}%{branch_text}"


def security(data: Json) -> None:
    if array(data.get("errors"), "Semgrep errors") or array(data.get("results"), "Semgrep findings"):
        raise GateError("Semgrep reported findings or scan errors")
    paths = object_value(data.get("paths"), "Semgrep paths")
    if not array(paths.get("scanned"), "Semgrep scanned files"):
        raise GateError("Semgrep scanned no files")
    if paths.get("skipped"):
        raise GateError("Semgrep skipped files; resolve unsupported/excluded production scope")


def vulnerabilities(data: Json) -> None:
    results = array(data.get("results"), "OSV results")
    packages = 0
    for result in results:
        for value in array(object_value(result, "OSV result").get("packages"), "OSV packages"):
            package = object_value(value, "OSV package")
            packages += 1
            if package.get("vulnerabilities"):
                raise GateError("OSV reported vulnerabilities")
    if not packages:
        raise GateError("OSV scanned no packages")


def fallow(data: Json) -> None:
    if data.get("kind") != "combined":
        raise GateError("Fallow must report both dead code and duplication")
    check = object_value(data.get("check"), "Fallow dead-code report")
    entries = object_value(check.get("entry_points"), "Fallow entry points")
    if not number(entries.get("total"), "Fallow entry points"):
        raise GateError("Fallow found no entry points; resolve its package scope")
    duplicates = object_value(data.get("dupes"), "Fallow duplication report")
    statistics = object_value(duplicates.get("stats"), "Fallow duplication statistics")
    if number(check.get("total_issues"), "Fallow findings") or number(
        statistics.get("duplicated_lines"), "duplicated lines"
    ):
        raise GateError("Fallow reported dead-code/dependency or duplicate-code findings")


def dart_decimate(data: Json) -> None:
    summary = object_value(data.get("summary"), "Dart Decimate summary")
    if data.get("kind") != "combined" or not number(summary.get("files"), "Dart files"):
        raise GateError("Dart Decimate did not complete the expected analyses")
    if (
        data.get("verdict") != "pass"
        or number(summary.get("findings"), "Dart findings")
        or number(summary.get("duplicated_lines"), "Dart duplicate lines")
    ):
        raise GateError("Dart Decimate reported findings")


def react_doctor(data: Json) -> None:
    summary = object_value(data.get("summary"), "React Doctor summary")
    if (
        data.get("mode") != "full"
        or data.get("reactDetected") is not True
        or not array(data.get("projects"), "React projects")
    ):
        raise GateError("React Doctor did not complete a full React project scan")
    if (
        data.get("ok") is not True
        or data.get("error")
        or number(summary.get("totalDiagnosticCount"), "React findings")
    ):
        raise GateError("React Doctor reported findings or an error")


def deployment(data: Json) -> None:
    results = array(data.get("Results"), "Trivy results")
    if not results:
        raise GateError("Trivy scanned no deployment configuration")
    for value in results:
        result = object_value(value, "Trivy result")
        summary = object_value(result.get("MisconfSummary"), "Trivy scan summary")
        if result.get("Class") != "config" or not number(summary.get("Successes"), "Trivy checks"):
            raise GateError("Trivy did not complete configuration checks")
        if number(summary.get("Failures"), "Trivy failures") or result.get("Misconfigurations"):
            raise GateError("Trivy reported deployment findings")


def validate(check: Check, package: Package | None) -> str:
    kind = check.report.get("type")
    if kind in {"python-tests", "lcov-tests", "dart-tests"}:
        if package is None:
            raise GateError("Tests must belong to a package")
        minimum = max(1.0, number(check.report.get("minimum_tests", 1), "minimum tests"))
        threshold = max(70.0, number(check.report.get("minimum_coverage", 70), "minimum coverage"))
        counter = dart_tests if kind == "dart-tests" else tests
        count = counter(report_path(check, "tests"), minimum)
        coverage = python_coverage if kind == "python-tests" else lcov_coverage
        return f"{count} tests; {coverage(check, package, threshold)}"
    if kind is None:
        return "command passed"
    if kind == "junit":
        minimum = max(1.0, number(check.report.get("minimum_tests", 1), "minimum tests"))
        return f"{tests(report_path(check, 'tests'), minimum)} tests"
    data = read_json(report_path(check, "path"))
    validate_json(kind, data)
    return "report complete"


def validate_json(kind: object, data: Json) -> None:
    if kind == "semgrep":
        security(data)
    elif kind == "osv":
        vulnerabilities(data)
    elif kind == "fallow":
        fallow(data)
    elif kind == "dart-decimate":
        dart_decimate(data)
    elif kind == "react-doctor":
        react_doctor(data)
    elif kind == "trivy":
        deployment(data)
    elif kind == "jscpd":
        statistics = object_value(data.get("statistics"), "jscpd statistics")
        totals = object_value(statistics.get("total"), "jscpd totals")
        if not number(totals.get("sources"), "jscpd sources"):
            raise GateError("jscpd scanned no files")
        if number(totals.get("duplicatedLines"), "duplicated lines"):
            raise GateError("jscpd reported duplicate code")
    else:
        raise GateError(f"Unknown report type: {kind}")


FOCUSED = re.compile(r"\b(?:it|test|describe)\s*\.\s*only\s*\(|\b(?:fit|fdescribe)\s*\(")


def focused_tests(path: Path) -> bool:
    return bool(FOCUSED.search(path.read_text()))

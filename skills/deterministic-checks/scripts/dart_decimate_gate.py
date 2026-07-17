#!/usr/bin/env python3
"""Run Dart Decimate at Git root while validating a nested Dart package."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def error(message: str) -> int:
    print(f"Dart Decimate gate: {message}", file=sys.stderr)
    return 2


def git(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(package), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def repository_root(package: Path) -> Path | None:
    result = git(package, "rev-parse", "--show-toplevel")
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def current_changed_lines(
    root: Path, base: str, relative: str
) -> tuple[set[int], int] | None:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return None
    absolute = (root / path).resolve()
    try:
        absolute.relative_to(root)
    except ValueError:
        return None
    if not absolute.is_file():
        return None
    try:
        line_count = len(absolute.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeError):
        return None
    tracked = git(root, "ls-files", "--error-unmatch", "--", relative)
    if tracked.returncode:
        return set(range(1, line_count + 1)), line_count
    diff = git(
        root,
        "diff",
        "--unified=0",
        "--no-ext-diff",
        "--no-color",
        base,
        "--",
        relative,
    )
    if diff.returncode:
        return None
    changed: set[int] = set()
    for line in diff.stdout.splitlines():
        match = HUNK.match(line)
        if not match:
            continue
        start = int(match.group(1))
        count = int(match.group(2) or "1")
        changed.update(range(start, start + count))
    return changed, line_count


def fail_receipt(reason: str) -> dict:
    return {
        "schema_version": "1",
        "result": "fail",
        "reason": reason,
        "upstream_exit": 1,
    }


def new_only_receipt(report: object, root: Path, base: str) -> dict:
    if not isinstance(report, dict) or report.get("command") != "audit":
        return fail_receipt("INVALID_AUDIT_REPORT")
    try:
        attribution = report["summary"]["attribution"]
        introduced = attribution["introduced"]
        pre_existing = attribution["pre_existing"]
        findings = report["findings"]
        candidates = report["security_candidates"]
    except (KeyError, TypeError):
        return fail_receipt("INVALID_ATTRIBUTION_SHAPE")
    try:
        counts = tuple(
            bucket[key]
            for bucket in (introduced, pre_existing)
            for key in ("findings", "error_findings", "warning_findings")
        )
    except (KeyError, TypeError):
        return fail_receipt("INVALID_ATTRIBUTION_SHAPE")
    for count in counts:
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            return fail_receipt("INVALID_ATTRIBUTION_COUNT")
    introduced_total, introduced_errors, introduced_warnings = counts[:3]
    pre_existing_total, pre_existing_errors, pre_existing_warnings = counts[3:]
    if introduced_total != introduced_errors + introduced_warnings or (
        pre_existing_total != pre_existing_errors + pre_existing_warnings
    ):
        return fail_receipt("INVALID_ATTRIBUTION_ROLLUP")
    if introduced_errors == 0:
        return fail_receipt("NO_INTRODUCED_ERROR_TO_CORRECT")
    if not isinstance(findings, list) or not isinstance(candidates, list):
        return fail_receipt("INVALID_FINDING_COLLECTION")
    if any(not isinstance(finding, dict) for finding in findings):
        return fail_receipt("INVALID_FINDING")
    if any(finding.get("severity") not in {"error", "warning"} for finding in findings):
        return fail_receipt("INVALID_FINDING_SEVERITY")
    errors = [
        finding
        for finding in findings
        if isinstance(finding, dict) and finding.get("severity") == "error"
    ]
    if len(errors) != introduced_errors + pre_existing_errors:
        return fail_receipt("ATTRIBUTION_TOTAL_MISMATCH")
    if len(findings) != introduced_total + pre_existing_total:
        return fail_receipt("ATTRIBUTION_TOTAL_MISMATCH")
    security_errors = [
        finding for finding in errors if finding.get("kind") == "security-candidate"
    ]
    non_security_errors = [
        finding for finding in errors if finding.get("kind") != "security-candidate"
    ]
    if len(security_errors) != introduced_errors or (
        len(non_security_errors) != pre_existing_errors
    ):
        return fail_receipt("AMBIGUOUS_INTRODUCED_ERROR")
    if len(candidates) != introduced_errors:
        return fail_receipt("AMBIGUOUS_SECURITY_CANDIDATE_COUNT")
    by_fingerprint: dict[str, dict] = {}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            return fail_receipt("INVALID_SECURITY_CANDIDATE")
        fingerprint = candidate.get("fingerprint")
        if (
            not isinstance(fingerprint, str)
            or candidate.get("finding_id") != fingerprint
            or candidate.get("severity") != "error"
            or fingerprint in by_fingerprint
        ):
            return fail_receipt("AMBIGUOUS_SECURITY_FINGERPRINT")
        by_fingerprint[fingerprint] = candidate
    corrected: list[str] = []
    for finding in security_errors:
        fingerprint = finding.get("fingerprint")
        if not isinstance(fingerprint, str):
            return fail_receipt("INVALID_SECURITY_FINGERPRINT")
        candidate = by_fingerprint.get(fingerprint)
        occurrences = None if candidate is None else candidate.get("occurrences")
        if not isinstance(occurrences, list) or not occurrences:
            return fail_receipt("MISSING_SECURITY_OCCURRENCES")
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                return fail_receipt("INVALID_SECURITY_OCCURRENCE")
            relative = occurrence.get("path")
            line = occurrence.get("line")
            if (
                not isinstance(relative, str)
                or not isinstance(line, int)
                or isinstance(line, bool)
                or line < 1
            ):
                return fail_receipt("INVALID_SECURITY_LOCATION")
            line_state = current_changed_lines(root, base, relative)
            if line_state is None:
                return fail_receipt("SECURITY_LOCATION_PROOF_FAILED")
            changed_lines, line_count = line_state
            if line > line_count or line in changed_lines:
                return fail_receipt("CHANGED_SECURITY_OCCURRENCE")
        if fingerprint in corrected:
            return fail_receipt("DUPLICATE_SECURITY_FINDING")
        corrected.append(fingerprint)
    if len(corrected) != introduced_errors:
        return fail_receipt("AMBIGUOUS_INTRODUCED_ERROR")
    return {
        "schema_version": "1",
        "result": "pass",
        "basis": "security error count uniquely fills introduced errors and occurrences are unchanged",
        "upstream_exit": 1,
        "introduced_error_findings": 0,
        "retained_pre_existing_error_findings": pre_existing_errors,
        "inherited_security_fingerprints": sorted(corrected),
    }


def run_new_only(command: list[str], root: Path, base: str) -> int:
    result = subprocess.run(
        command, cwd=root, capture_output=True, text=True, check=False
    )
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 1:
        sys.stdout.write(result.stdout)
        return result.returncode
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.stdout.write(result.stdout)
        return result.returncode
    receipt = new_only_receipt(report, root, base)
    if not isinstance(report, dict):
        sys.stdout.write(result.stdout)
        return result.returncode
    report["hard_eng_gate"] = receipt
    print(json.dumps(report, separators=(",", ":")))
    return 0 if receipt["result"] == "pass" else result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package", default=".", help="Dart package containing pubspec.yaml"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--base", help="Git base ref for new-only audit")
    mode.add_argument("--full", action="store_true", help="Run full JSON gate")
    args = parser.parse_args()

    package = Path(args.package).expanduser().resolve()
    if not package.is_dir() or not (package / "pubspec.yaml").is_file():
        return error("--package must be a Dart package directory")
    root = repository_root(package)
    if root is None:
        return error("package is not inside a Git repository")
    try:
        package.relative_to(root)
    except ValueError:
        return error("package resolves outside the Git repository")
    if shutil.which("npx") is None:
        return error("npx is required")

    if args.base:
        if args.base.startswith("-"):
            return error("invalid base ref")
        verified = git(
            root, "rev-parse", "--verify", "--quiet", f"{args.base}^{{commit}}"
        )
        if verified.returncode:
            return error(f"base ref is not a commit: {args.base}")
        command = [
            "npx",
            "--yes",
            "dart-decimate",
            "audit",
            str(root),
            "--base",
            args.base,
            "--format",
            "json",
            "--summary",
            "--gate",
            "new-only",
        ]
    else:
        command = ["npx", "--yes", "dart-decimate", "json", str(root)]
    if args.base:
        return run_new_only(command, root, args.base)
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

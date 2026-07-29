#!/usr/bin/env python3
"""Run repository-owned deterministic gate commands without caller-supplied shell text."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from git_env import git_env

SCRIPT_DIR = Path(__file__).resolve().parent
BOUNDED = SCRIPT_DIR / "bounded_run.py"

MANIFEST_NAME = "hard-eng.gates.json"
FAMILY_PATTERNS = {
    "targeted": re.compile(r"\S"),
    "typecheck": re.compile(r"\btsc\b|typecheck|vue-tsc"),
    "format": re.compile(r"\bbiome\b.*\bformat\b|\bformat(?::check)?\b"),
    "lint": re.compile(r"\beslint\b|\boxlint\b|\bbiome\b.*\blint\b|\blint\b"),
    "tests": re.compile(r"\bvitest\b|\bjest\b|\bplaywright\b|--test\b|\btests?\b"),
    "fallow": re.compile(r"\bfallow\b"),
    "react-doctor": re.compile(r"\breact-doctor\b"),
    "dart-analyze": re.compile(r"\b(dart|flutter)\b.*\banalyze\b"),
    "dart-test": re.compile(r"\b(dart|flutter)\b.*\btest\b"),
    "dart-decimate": re.compile(r"\bdart[-_]decimate\b"),
}
NO_OP_EXECUTABLES = {
    "bash", "cmd", "echo", "false", "fish", "powershell", "printf", "pwsh",
    "sh", "true", "zsh",
}
PACKAGE_SPEC = re.compile(
    r"^(?:@[^/@]+/[^/@]+|[^@/]+)@(?:latest|\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$"
)
LATEST_TOOL_PACKAGE = {
    "fallow": "fallow@latest",
    "react-doctor": "react-doctor@latest",
    "dart-decimate": "dart-decimate@latest",
}
SCOPED_QUALITY_FLAGS = {
    "fallow": {
        "--audit",
        "--base",
        "--baseline",
        "--changed-since",
        "--changed-workspaces",
        "--diff-file",
        "--diff-stdin",
        "--file",
        "--regression-baseline",
        "--save-baseline",
        "--save-regression-baseline",
        "--workspace",
    },
    "react-doctor": {
        "--base",
        "--category",
        "--max-duration",
        "--no-parallel",
        "--project",
        "--staged",
    },
    "dart-decimate": {
        "--audit",
        "--baseline",
        "--changed-since",
        "--changed-workspaces",
        "--compare",
        "--fail-on-regression",
        "--file",
        "--regression-baseline",
        "--save-baseline",
        "--save-regression-baseline",
    },
}


class ProjectGateError(ValueError):
    """Invalid project gate manifest or execution."""


def load_manifest(repo: Path) -> dict[str, tuple[str, ...]]:
    path = repo / MANIFEST_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectGateError(f"{MANIFEST_NAME} is missing or invalid: {error}") from error
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ProjectGateError(f"{MANIFEST_NAME} requires schema_version 1")
    families = raw.get("families")
    if not isinstance(families, dict) or not families:
        raise ProjectGateError(f"{MANIFEST_NAME} requires a non-empty families object")
    validated: dict[str, tuple[str, ...]] = {}
    for family, command in families.items():
        if family not in FAMILY_PATTERNS:
            raise ProjectGateError(f"unknown check family: {family}")
        if (
            not isinstance(command, list)
            or not command
            or any(not isinstance(argument, str) or not argument for argument in command)
        ):
            raise ProjectGateError(f"{family} command must be a non-empty argv string array")
        executable = Path(command[0]).name.lower()
        if executable in NO_OP_EXECUTABLES:
            raise ProjectGateError(f"{family} command uses forbidden no-op/shell executable: {command[0]}")
        rendered = " ".join(command)
        if not FAMILY_PATTERNS[family].search(rendered):
            raise ProjectGateError(f"command does not look like a {family} check: {rendered}")
        if executable in {"npx", "npx.cmd"}:
            _validate_npx(family, command)
        _validate_quality_scope(family, command)
        validated[family] = tuple(command)
    return validated


def _validate_npx(family: str, command: list[str]) -> None:
    packages: list[str] = []
    direct_package: str | None = None
    index = 1
    while index < len(command):
        argument = command[index]
        if argument in {"--package", "-p"}:
            if index + 1 >= len(command):
                break
            packages.append(command[index + 1])
            index += 2
            continue
        if argument == "--yes" or argument.startswith("-"):
            index += 1
            continue
        if not packages:
            direct_package = argument
        break
    specs = [*packages, *([direct_package] if direct_package else [])]
    if not specs or any(not PACKAGE_SPEC.fullmatch(package) for package in specs):
        raise ProjectGateError(
            f"{family} npx command requires an exact semver or @latest package"
        )
    required = LATEST_TOOL_PACKAGE.get(family)
    if required and specs != [required]:
        raise ProjectGateError(f"{family} npx command requires {required}")
    if packages:
        if index >= len(command):
            raise ProjectGateError(f"{family} npx command has no package binary")
        binary = Path(command[index]).name.lower()
        if binary in NO_OP_EXECUTABLES or "@" in binary:
            raise ProjectGateError(
                f"{family} npx command uses forbidden package binary: {command[index]}"
            )


def _validate_quality_scope(family: str, command: list[str]) -> None:
    if family not in LATEST_TOOL_PACKAGE:
        return
    if Path(command[0]).name.lower() not in {"npx", "npx.cmd"}:
        raise ProjectGateError(
            f"{family} requires direct npx --yes {LATEST_TOOL_PACKAGE[family]}"
        )
    forbidden = sorted(set(command) & SCOPED_QUALITY_FLAGS[family])
    if forbidden:
        raise ProjectGateError(
            f"{family} must be a full clean scan; scoped/baseline flags are forbidden: "
            + ", ".join(forbidden)
        )
    if family == "fallow":
        if (
            "--fail-on-issues" not in command
            or "audit" in command
            or "--format" not in command
            or command[command.index("--format") + 1 : command.index("--format") + 2]
            != ["json"]
        ):
            raise ProjectGateError(
                "fallow requires full combined JSON mode with --fail-on-issues"
            )
    elif family == "react-doctor":
        try:
            scope = command[command.index("--scope") + 1]
            blocking = command[command.index("--blocking") + 1]
        except (ValueError, IndexError) as error:
            raise ProjectGateError(
                "react-doctor requires --scope full --blocking warning "
                "--no-respect-inline-disables"
            ) from error
        if (
            scope != "full"
            or blocking != "warning"
            or "--no-respect-inline-disables" not in command
        ):
            raise ProjectGateError(
                "react-doctor requires --scope full --blocking warning "
                "--no-respect-inline-disables"
            )
    elif family == "dart-decimate":
        if "audit" in command:
            raise ProjectGateError("dart-decimate audit mode is not a full clean scan")
        if not ({"json", "check"} & set(command)):
            raise ProjectGateError(
                "dart-decimate requires full check/json mode"
            )


def validate_quality_report(family: str, output: str) -> None:
    if family != "fallow":
        return
    try:
        report = json.loads(output)
    except ValueError as error:
        raise ProjectGateError("fallow did not emit one valid JSON report") from error
    if not isinstance(report, dict) or report.get("kind") != "combined":
        raise ProjectGateError("fallow report is not a full combined scan")
    check = report.get("check")
    dupes = report.get("dupes")
    health = report.get("health")
    if not isinstance(check, dict) or not isinstance(dupes, dict) or not isinstance(health, dict):
        raise ProjectGateError("fallow combined report is missing check/dupes/health")
    total_issues = check.get("total_issues")
    clone_groups = dupes.get("clone_groups")
    clone_families = dupes.get("clone_families")
    findings = health.get("findings")
    styling_findings = health.get("styling_findings", [])
    if (
        not isinstance(total_issues, int)
        or not isinstance(clone_groups, list)
        or not isinstance(clone_families, list)
        or not isinstance(findings, list)
        or not isinstance(styling_findings, list)
    ):
        raise ProjectGateError("fallow combined report has an invalid finding shape")
    if total_issues or clone_groups or clone_families or findings or styling_findings:
        first = findings[0] if findings else None
        first_label = ""
        if isinstance(first, dict):
            first_label = (
                f"; first={first.get('path', '?')}:{first.get('line', '?')}"
                f" {first.get('name', '?')} severity={first.get('severity', '?')}"
            )
        raise ProjectGateError(
            "fallow report contains findings: "
            f"check={total_issues} duplicate_groups={len(clone_groups)} "
            f"duplicate_families={len(clone_families)} health={len(findings)} "
            f"styling={len(styling_findings)}{first_label}"
        )


def command_for(repo: Path, family: str) -> tuple[str, ...]:
    commands = load_manifest(repo)
    try:
        return commands[family]
    except KeyError as error:
        raise ProjectGateError(f"{MANIFEST_NAME} has no command for required family: {family}") from error


def tree_fingerprint(repo: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "-z", "-c", "-o", "--exclude-standard"],
        check=False,
        capture_output=True,
        env=git_env(),
    )
    if result.returncode != 0:
        raise ProjectGateError("cannot snapshot repository files")
    paths = {path for path in result.stdout.split(b"\0") if path}
    include = repo / ".worktreeinclude"
    if include.is_file():
        for entry in include.read_text(encoding="utf-8").splitlines():
            entry = entry.strip()
            if not entry or entry.startswith("#"):
                continue
            ignored = subprocess.run(
                [
                    "git", "-C", str(repo), "ls-files", "-z", "--others", "--ignored",
                    "--exclude-standard", "--", entry,
                ],
                check=False,
                capture_output=True,
                env=git_env(),
            )
            if ignored.returncode != 0:
                raise ProjectGateError(f"cannot snapshot .worktreeinclude entry: {entry}")
            paths.update(path for path in ignored.stdout.split(b"\0") if path)
    digest = hashlib.sha256()
    for raw in sorted(paths):
        relative = os.fsdecode(raw)
        path = repo / relative
        digest.update(raw)
        digest.update(b"\0")
        if not path.exists() and not path.is_symlink():
            digest.update(b"<deleted>")
            digest.update(b"\0")
            continue
        try:
            digest.update(os.readlink(path).encode() if path.is_symlink() else path.read_bytes())
        except OSError as error:
            raise ProjectGateError(f"cannot snapshot {relative}: {error}") from error
        digest.update(b"\0")
    return digest.hexdigest()


def run_families(repo: Path, families: list[str], timeout: float) -> list[dict[str, object]]:
    hygiene = SCRIPT_DIR.parents[2] / "scripts/git-env-hygiene-contract.py"
    checked = subprocess.run(
        [sys.executable, str(hygiene), "--root", str(repo)],
        check=False,
        capture_output=True,
        text=True,
        env=git_env(),
    )
    if checked.returncode:
        detail = (checked.stderr or checked.stdout).strip()
        raise ProjectGateError(detail or "Git environment hygiene preflight failed")
    commands = load_manifest(repo)
    missing = [family for family in families if family not in commands]
    if missing:
        raise ProjectGateError(
            f"{MANIFEST_NAME} has no command for required families: {', '.join(missing)}"
        )
    before = tree_fingerprint(repo)
    deadline = time.monotonic() + timeout
    results: list[dict[str, object]] = []
    report_error: ProjectGateError | None = None
    for family in families:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProjectGateError("whole-run timeout exhausted before every check ran")
        command = commands[family]
        capture = family in LATEST_TOOL_PACKAGE
        completed = subprocess.run(
            [
                sys.executable, str(BOUNDED), "--timeout", str(max(1, int(remaining))),
                "--cwd", str(repo), "--", *command,
            ],
            check=False,
            capture_output=capture,
            text=capture,
        )
        if completed.returncode == 0 and capture:
            try:
                validate_quality_report(family, completed.stdout)
            except ProjectGateError as error:
                report_error = error
        results.append({
            "family": family,
            "command": list(command),
            "exit": 4 if report_error else completed.returncode,
        })
        if completed.returncode != 0 and capture:
            detail = (completed.stderr or completed.stdout).strip()
            if detail:
                print(detail[-4000:], file=sys.stderr)
        if completed.returncode != 0 or report_error:
            break
    if tree_fingerprint(repo) != before:
        raise ProjectGateError("project gate commands mutated the repository tree")
    if report_error:
        raise report_error
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", choices=("run",))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--family", action="append", required=True)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        results = run_families(repo, args.family, args.timeout)
    except (OSError, subprocess.SubprocessError, ProjectGateError) as error:
        print(f"project-gate: FAIL: {error}", file=sys.stderr)
        return 4
    for result in results:
        print(f"project-gate: {result['family']} {'PASS' if result['exit'] == 0 else 'FAIL'}")
    return 0 if all(result["exit"] == 0 for result in results) else 4


if __name__ == "__main__":
    raise SystemExit(main())

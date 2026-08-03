#!/usr/bin/env python3
"""Run repository-owned deterministic gate commands without caller-supplied shell text."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from git_env import git_env
from source_tree_coordination import (
    CoordinationError,
    begin_react_doctor,
    clear_react_doctor_quarantine,
    consume_terminal_receipt,
    remaining,
    rollback_react_doctor_launch,
    source_tree_lock,
    terminal_receipt_spec,
    tree_fingerprint,
    validate_external_npx,
)

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


def _run_bounded(
    command: list[str],
    *,
    capture: bool,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=False,
        capture_output=capture,
        text=capture,
    )


def load_manifest(
    repo: Path,
    *,
    deadline: float | None = None,
) -> dict[str, tuple[str, ...]]:
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
        executable = command[0].lower()
        executable_name = Path(command[0]).name.lower()
        if executable_name in NO_OP_EXECUTABLES:
            raise ProjectGateError(f"{family} command uses forbidden no-op/shell executable: {command[0]}")
        rendered = " ".join(command)
        if not FAMILY_PATTERNS[family].search(rendered):
            raise ProjectGateError(f"command does not look like a {family} check: {rendered}")
        if executable_name in {"npx", "npx.cmd"} and executable not in {
            "npx",
            "npx.cmd",
        }:
            raise ProjectGateError(
                f"{family} npx command requires literal npx or npx.cmd"
            )
        if executable in {"npx", "npx.cmd"}:
            _validate_npx(family, command)
        _validate_quality_scope(family, command)
        validated[family] = tuple(command)
    if any(family in LATEST_TOOL_PACKAGE for family in validated):
        try:
            validate_external_npx(repo, deadline=deadline)
        except CoordinationError as error:
            raise ProjectGateError(str(error)) from error
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


def _option_value(command: list[str], option: str) -> str | None:
    for index, argument in enumerate(command):
        if argument == option:
            if index + 1 < len(command):
                return command[index + 1]
            return None
        prefix = f"{option}="
        if argument.startswith(prefix):
            return argument[len(prefix) :]
    return None


def _validate_quality_scope(family: str, command: list[str]) -> None:
    if family not in LATEST_TOOL_PACKAGE:
        return
    if command[0].lower() not in {"npx", "npx.cmd"}:
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
        scope = _option_value(command, "--scope")
        blocking = _option_value(command, "--blocking") or _option_value(
            command, "--fail-on"
        )
        if (
            not (scope == "full" or "--full" in command)
            or blocking != "warning"
            or "--no-respect-inline-disables" not in command
        ):
            raise ProjectGateError(
                "react-doctor requires a full scan with warning blocking "
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


def run_families(repo: Path, families: list[str], timeout: float) -> list[dict[str, object]]:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ProjectGateError("whole-run timeout must be finite and positive")
    deadline = time.monotonic() + timeout
    hygiene = SCRIPT_DIR.parents[2] / "scripts/git-env-hygiene-contract.py"
    with source_tree_lock(repo, exclusive=False, deadline=deadline):
        try:
            checked = subprocess.run(
                [sys.executable, str(hygiene), "--root", str(repo)],
                check=False,
                capture_output=True,
                text=True,
                env=git_env(),
                timeout=remaining(deadline, "during Git environment preflight"),
            )
        except subprocess.TimeoutExpired as error:
            raise ProjectGateError(
                "whole-run timeout exhausted during Git environment preflight"
            ) from error
        if checked.returncode:
            detail = (checked.stderr or checked.stdout).strip()
            raise ProjectGateError(detail or "Git environment hygiene preflight failed")
        remaining(deadline, "before manifest validation")
        commands = load_manifest(repo, deadline=deadline)
        missing = [family for family in families if family not in commands]
        if missing:
            raise ProjectGateError(
                f"{MANIFEST_NAME} has no command for required families: {', '.join(missing)}"
            )
        fingerprint_started = time.monotonic()
        before = tree_fingerprint(repo, deadline=deadline)
        fingerprint_headroom = max(
            0.05, (time.monotonic() - fingerprint_started) * 2
        )
    results: list[dict[str, object]] = []
    report_error: ProjectGateError | None = None
    for family in families:
        remaining(deadline, "before every check ran")
        command = commands[family]
        capture = family in LATEST_TOOL_PACKAGE
        exclusive = family == "react-doctor"
        with source_tree_lock(
            repo,
            exclusive=exclusive,
            deadline=deadline,
        ) as lock_path:
            family_before = (
                tree_fingerprint(repo, deadline=deadline) if exclusive else None
            )
            remaining_budget = remaining(deadline, "before every check ran")
            grace = min(2.0, max(0.1, remaining_budget * 0.02))
            proof_count = 2 if exclusive else 1
            launch_headroom = min(
                1.0, max(0.1, remaining_budget * 0.01)
            )
            command_timeout = (
                remaining_budget
                - (2 * grace)
                - (proof_count * fingerprint_headroom)
                - launch_headroom
            )
            if command_timeout <= 0:
                raise ProjectGateError(
                    "whole-run timeout has no command and shutdown headroom"
                )
            receipt_path, receipt_token = terminal_receipt_spec(repo)
            if exclusive:
                begin_react_doctor(
                    lock_path,
                    family_before,
                    receipt_path,
                    receipt_token,
                )
            bounded_command = [
                sys.executable,
                str(BOUNDED),
                "--timeout",
                str(command_timeout),
                "--grace",
                str(grace),
                "--terminal-receipt",
                str(receipt_path),
                "--terminal-token",
                receipt_token,
                "--cwd",
                str(repo),
                "--",
                *command,
            ]
            try:
                completed = _run_bounded(
                    bounded_command,
                    capture=capture,
                )
            except OSError:
                if exclusive:
                    rollback_react_doctor_launch(
                        repo,
                        lock_path,
                        expected=family_before,
                        receipt_path=receipt_path,
                        receipt_token=receipt_token,
                        deadline=deadline,
                    )
                raise
            if exclusive:
                clear_react_doctor_quarantine(
                    repo,
                    lock_path,
                    expected=family_before,
                    receipt_path=receipt_path,
                    receipt_token=receipt_token,
                    deadline=deadline,
                )
            else:
                consume_terminal_receipt(receipt_path, receipt_token)
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
            detail = "\n".join(
                part for part in (completed.stdout, completed.stderr) if part
            ).strip()
            if detail:
                print(detail[-4000:], file=sys.stderr)
        if completed.returncode != 0 or report_error:
            break
    with source_tree_lock(repo, exclusive=False, deadline=deadline):
        after = tree_fingerprint(repo, deadline=deadline)
    if after != before:
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
    except (
        CoordinationError,
        OSError,
        subprocess.SubprocessError,
        ProjectGateError,
    ) as error:
        print(f"project-gate: FAIL: {error}", file=sys.stderr)
        return 4
    for result in results:
        print(f"project-gate: {result['family']} {'PASS' if result['exit'] == 0 else 'FAIL'}")
    return 0 if all(result["exit"] == 0 for result in results) else 4


if __name__ == "__main__":
    raise SystemExit(main())

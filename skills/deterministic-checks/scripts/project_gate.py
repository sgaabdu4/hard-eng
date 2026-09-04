#!/usr/bin/env python3
"""Run repository-owned deterministic gate commands without caller-supplied shell text."""

# Size exception: one focused gate runner; its regression script proves every command path.

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from bounded_run import run as run_bounded_process
from bounded_run import run_captured
from clones_family import ClonesFamilyError, validate_clones
from dirty_tree_note import _dirty_paths_note
from enforcement_benchmark import benchmark
from git_env import git_env
from source_tree_coordination import (
    AUDIT_FLAG,
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
    validate_react_doctor_flags,
)

SCRIPT_DIR = Path(__file__).resolve().parent
BOUNDED = SCRIPT_DIR / "bounded_run.py"

MANIFEST_NAME = "hard-eng.gates.json"
FAMILY_PATTERNS = {
    "targeted": re.compile(r"\S"),
    "typecheck": re.compile(r"\btsc\b|typecheck|vue-tsc"),
    "staged": re.compile(r"\bbiome\b.*\bcheck\b.*--staged"),
    "format": re.compile(r"\bbiome\b.*\bformat\b|\bformat(?::check)?\b"),
    "lint": re.compile(r"\beslint\b|\boxlint\b|\bbiome\b.*\blint\b|\blint\b"),
    "tests": re.compile(r"\bvitest\b|\bjest\b|\bplaywright\b|--test\b|\btests?\b"),
    "fallow": re.compile(r"\bfallow\b"),
    "clones": re.compile(r"\bjscpd\b|\bcpd\b"),
    "python-types": re.compile(r"\bpyright\b"),
    "skill-contracts": re.compile(r"check-skill-contracts\.py"),
    "managed-skills": re.compile(r"check-managed-skills\.js"),
    "design": re.compile(r"check-design-md\.js"),
    "file-size": re.compile(r"check-file-size\.py"),
    "enforcement": re.compile(r"enforcement_policy\.pl"),
    "react-doctor": re.compile(r"\breact-doctor\b"),
    "dart-analyze": re.compile(r"\b(dart|flutter)\b.*\banalyze\b"),
    "dart-test": re.compile(r"\b(dart|flutter)\b.*\btest\b"),
    "dart-decimate": re.compile(r"\bdart[-_]decimate\b"),
    "boundary-contracts": re.compile(r"\b(boundary|contract|schema|zod|openapi|validation)\b"),
    "python-format": re.compile(r"\bruff\b.*\bformat\b|\bblack\b"),
    "python-lint": re.compile(r"\bruff\b.*\bcheck\b|\bflake8\b|\bpylint\b"),
    "python-tests": re.compile(r"\bpytest\b"),
    "secrets": re.compile(r"\bgitleaks\b|\btrufflehog\b"),
    "sast": re.compile(r"\bbandit\b|\bsemgrep\b"),
    "deps-audit": re.compile(r"\bpip-audit\b|\bnpm audit\b|\bosv-scanner\b"),
}
NO_OP_EXECUTABLES = {"bash", "cmd", "echo", "false", "fish", "powershell", "printf", "pwsh", "sh", "true", "zsh"}
PACKAGE_SPEC = re.compile(r"^(?:@[^/@]+/[^/@]+|[^@/]+)@(?:latest|\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)$")
LATEST_TOOL_PACKAGE = {"react-doctor": "react-doctor@latest", "dart-decimate": "dart-decimate@latest"}
QUALITY_REPORT_FAMILIES = frozenset({"fallow", "react-doctor", "dart-decimate"})
CAPTURED_FAMILIES = QUALITY_REPORT_FAMILIES | {"enforcement"}
MAX_PARALLEL_FAMILIES = 4
EXCLUSIVE_FAMILIES = frozenset({"react-doctor"})
SECURITY_FAMILIES = frozenset({"secrets", "sast", "deps-audit"})
REACT_DOCTOR_OPTIONS = ("--scope", "full", "--blocking", "warning", AUDIT_FLAG, "--no-telemetry", "--json", "-y")
REACT_DOCTOR_COMMAND = ("npx", "--yes", "react-doctor@latest", ".", *REACT_DOCTOR_OPTIONS)
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
        "--changed-files-from",
        "--diff",
        "--json-out",
        "--max-duration",
        "--no-dead-code",
        "--no-lint",
        "--no-supply-chain",
        "--no-warnings",
        "--output-dir",
        "--project",
        "--score",
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


def _run_bounded(command: list[str], *, capture: bool, timeout: float) -> subprocess.CompletedProcess[str]:
    environment = git_env()
    environment["HARD_ENG_PYTHON"] = sys.executable
    if capture:
        result = run_captured(command, timeout, grace=2, env=environment)
        return subprocess.CompletedProcess(
            command,
            result.returncode,
            result.stdout.decode("utf-8", "replace"),
            result.stderr.decode("utf-8", "replace"),
        )
    result = run_bounded_process(command, timeout, grace=2, env=environment)
    return subprocess.CompletedProcess(command, result.returncode)


def load_manifest(
    repo: Path, *, deadline: float | None = None, validate_external: bool = True
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
        if executable_name in {"npx", "npx.cmd"} and executable not in {"npx", "npx.cmd"}:
            raise ProjectGateError(f"{family} npx command requires literal npx or npx.cmd")
        if executable in {"npx", "npx.cmd"}:
            _validate_npx(family, command)
        _validate_quality_scope(family, command)
        try:
            validate_clones(repo, family, command)
        except ClonesFamilyError as error:
            raise ProjectGateError(str(error)) from error
        _validate_python_security(family, command)
        validated[family] = tuple(command)
    if validate_external and any(command[0].lower() in {"npx", "npx.cmd"} for command in validated.values()):
        try:
            validate_external_npx(repo, deadline=deadline)
        except CoordinationError as error:
            raise ProjectGateError(str(error)) from error
    return validated


def load_phase(repo: Path, phase: str) -> list[str]:
    path = repo / MANIFEST_NAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProjectGateError(f"{MANIFEST_NAME} is missing or invalid: {error}") from error
    enforcement = raw.get("enforcement") if isinstance(raw, dict) else None
    if not isinstance(enforcement, dict) or enforcement.get("schema_version") != 1:
        raise ProjectGateError(f"{MANIFEST_NAME} enforcement requires schema_version 1")
    required_paths = enforcement.get("required_paths")
    if (
        not isinstance(required_paths, list)
        or not required_paths
        or any(not isinstance(item, str) or not item for item in required_paths)
        or len(set(required_paths)) != len(required_paths)
    ):
        raise ProjectGateError(f"{MANIFEST_NAME} enforcement requires unique required_paths")
    for item in required_paths:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts:
            raise ProjectGateError(f"invalid enforcement path: {item}")
        target = repo / relative
        if target.is_symlink() or not target.is_file():
            raise ProjectGateError(f"required enforcement file is missing or not regular: {item}")
    phases = raw.get("phases")
    if not isinstance(phases, dict):
        raise ProjectGateError(f"{MANIFEST_NAME} requires a phases object")
    missing_phases = [name for name in ("commit", "push", "ci") if name not in phases]
    if missing_phases:
        raise ProjectGateError(f"{MANIFEST_NAME} is missing phases: {', '.join(missing_phases)}")
    if phases["push"] != phases["ci"]:
        raise ProjectGateError(f"{MANIFEST_NAME} push and ci phases must match exactly")
    commit_families = phases.get("commit")
    banned = SECURITY_FAMILIES.intersection(commit_families if isinstance(commit_families, list) else ())
    if banned:
        raise ProjectGateError(
            f"{MANIFEST_NAME} commit phase cannot run security families: " + ", ".join(sorted(banned))
        )
    families = phases.get(phase)
    if (
        not isinstance(families, list)
        or not families
        or any(not isinstance(family, str) or not family for family in families)
    ):
        raise ProjectGateError(f"{MANIFEST_NAME} phase {phase!r} must be a non-empty family list")
    if len(set(families)) != len(families):
        raise ProjectGateError(f"{MANIFEST_NAME} phase {phase!r} repeats a family")
    commands = load_manifest(repo, validate_external=False)
    missing = [family for family in families if family not in commands]
    if missing:
        raise ProjectGateError(f"{MANIFEST_NAME} phase {phase!r} names missing families: {', '.join(missing)}")
    return families


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
        raise ProjectGateError(f"{family} npx command requires an exact semver or @latest package")
    required = LATEST_TOOL_PACKAGE.get(family)
    if required and specs != [required]:
        raise ProjectGateError(f"{family} npx command requires {required}")
    if packages:
        if index >= len(command):
            raise ProjectGateError(f"{family} npx command has no package binary")
        binary = Path(command[index]).name.lower()
        if binary in NO_OP_EXECUTABLES or "@" in binary:
            raise ProjectGateError(f"{family} npx command uses forbidden package binary: {command[index]}")


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
    if family not in QUALITY_REPORT_FAMILIES:
        return
    if family in LATEST_TOOL_PACKAGE and command[0].lower() not in {"npx", "npx.cmd"}:
        raise ProjectGateError(f"{family} requires direct npx --yes {LATEST_TOOL_PACKAGE[family]}")
    forbidden = sorted({argument.split("=", 1)[0] for argument in command} & SCOPED_QUALITY_FLAGS[family])
    if forbidden:
        raise ProjectGateError(
            f"{family} must be a full clean scan; scoped/baseline flags are forbidden: " + ", ".join(forbidden)
        )
    if family == "fallow":
        if (
            "audit" not in command
            or _option_value(command, "--format") != "json"
            or _option_value(command, "--max-crap") is None
        ):
            raise ProjectGateError("fallow requires audit mode with --format json and --max-crap <N>")
    elif family == "react-doctor":
        if (
            len(command) < 4
            or command[0].lower() not in {"npx", "npx.cmd"}
            or command[1:3] != ["--yes", "react-doctor@latest"]
            or command[3].startswith("-")
            or command[4:] != list(REACT_DOCTOR_OPTIONS)
        ):
            raise ProjectGateError(
                "react-doctor requires --scope full; command must be: "
                "npx --yes react-doctor@latest <target> " + " ".join(REACT_DOCTOR_OPTIONS)
            )
    elif family == "dart-decimate":
        if "audit" in command:
            raise ProjectGateError("dart-decimate audit mode is not a full clean scan")
        if not ({"json", "check"} & set(command)):
            raise ProjectGateError("dart-decimate requires full check/json mode")


def _validate_python_security(family: str, command: list[str]) -> None:
    rendered = " ".join(command)
    if family == "python-format" and "--check" not in command:
        raise ProjectGateError("python-format must verify without rewriting; add --check")
    if family == "python-lint" and {"--fix", "--unsafe-fixes"} & set(command):
        raise ProjectGateError("python-lint must not rewrite the tree; remove --fix/--unsafe-fixes")
    is_ruff = family in {"python-format", "python-lint"} and Path(command[0]).name.lower() == "ruff"
    if is_ruff and "--no-cache" not in command:
        raise ProjectGateError(f"{family} ruff command must run cache-write-free; add --no-cache")
    if family == "python-tests" and "pytest" in rendered and "-p no:cacheprovider" not in rendered:
        raise ProjectGateError("python-tests pytest command must run cache-write-free; add -p no:cacheprovider")
    if family != "secrets":
        return
    if "--redact" not in command:
        raise ProjectGateError("secrets scan must redact findings; add --redact")
    if any(argument == "--baseline-path" or argument.startswith("--baseline-path=") for argument in command):
        raise ProjectGateError("secrets scan must not suppress findings with a baseline")
    if _option_value(command, "--exit-code") == "0":
        raise ProjectGateError("secrets scan must fail on findings; --exit-code 0 is forbidden")


def _validate_react_doctor_report(output: str) -> None:
    """Gate on what the scan reported, because argv proves nothing about it.

    A silenced analyzer exits zero with an empty diagnostic list, so completeness
    is asserted per project rather than inferred from the exit code.
    """
    try:
        report = json.loads(output)
    except ValueError as error:
        raise ProjectGateError("react-doctor did not emit one valid JSON report") from error
    if not isinstance(report, dict) or report.get("schemaVersion") != 3:
        raise ProjectGateError("react-doctor report is not schemaVersion 3")
    if report.get("ok") is not True or report.get("error") is not None:
        raise ProjectGateError(f"react-doctor reported a tool error: {report.get('error')}")
    if report.get("mode") != "full":
        raise ProjectGateError(f"react-doctor report is not a full scan: mode={report.get('mode')}")
    # Absent means nothing was scanned, which is a wrong gate target, not a pass.
    if report.get("reactDetected") is not True:
        raise ProjectGateError("react-doctor scanned no React project; the gate target is wrong")
    projects = report.get("projects")
    diagnostics = report.get("diagnostics")
    summary = report.get("summary")
    if (
        not isinstance(projects, list)
        or not projects
        or not isinstance(diagnostics, list)
        or not isinstance(summary, dict)
    ):
        raise ProjectGateError("react-doctor report has an invalid scan shape")
    if report.get("skippedProjects"):
        raise ProjectGateError(f"react-doctor skipped {len(report['skippedProjects'])} project(s)")
    for project in projects:
        if not isinstance(project, dict):
            raise ProjectGateError("react-doctor report has an invalid project entry")
        if project.get("complete") is not True or project.get("skippedChecks"):
            raise ProjectGateError(
                "react-doctor scan is incomplete: "
                f"{project.get('directory', '?')} "
                f"skipped={project.get('skippedChecks')} "
                f"reasons={project.get('skippedCheckReasons')}"
            )
    counts = [summary.get(key) for key in ("errorCount", "warningCount", "totalDiagnosticCount")]
    if any(not isinstance(count, int) for count in counts):
        raise ProjectGateError("react-doctor summary has an invalid count shape")
    if diagnostics or any(counts):
        first = diagnostics[0] if diagnostics else None
        first_label = ""
        if isinstance(first, dict):
            first_label = (
                f"; first={first.get('filePath', '?')}:{first.get('line', '?')}"
                f" {first.get('plugin', '?')}/{first.get('rule', '?')}"
                f" severity={first.get('severity', '?')}"
            )
        raise ProjectGateError(
            "react-doctor report contains findings: "
            f"errors={counts[0]} warnings={counts[1]} total={counts[2]}"
            f"{first_label}"
        )


def validate_quality_report(family: str, output: str) -> None:
    if family == "enforcement":
        try:
            report = json.loads(output)
        except ValueError as error:
            raise ProjectGateError("enforcement policy did not emit valid JSON") from error
        rules = report.get("rules") if isinstance(report, dict) else None
        allowed = {"advise", "block", "checkpoint check", "guidance", "unsupported"}
        if (
            not isinstance(report, dict)
            or report.get("schema_version") != 1
            or not isinstance(rules, dict)
            or not rules
            or any(not isinstance(name, str) or verdict not in allowed for name, verdict in rules.items())
        ):
            raise ProjectGateError("enforcement policy coverage report is invalid")
        return
    if family == "react-doctor":
        _validate_react_doctor_report(output)
        return
    if family != "fallow":
        return
    try:
        report = json.loads(output)
    except ValueError as error:
        raise ProjectGateError("fallow did not emit one valid JSON report") from error
    if not isinstance(report, dict) or report.get("kind") != "audit":
        raise ProjectGateError("fallow report is not an audit report")
    verdict = report.get("verdict")
    summary = report.get("summary")
    attribution = report.get("attribution")
    if verdict not in {"pass", "warn", "fail"} or not isinstance(summary, dict) or not isinstance(attribution, dict):
        raise ProjectGateError("fallow audit report is missing verdict/summary/attribution")
    if verdict == "fail":
        counts = ", ".join(f"{key}={value}" for key, value in sorted(attribution.items()) if isinstance(value, int))
        first = _first_audit_finding(report)
        raise ProjectGateError(f"fallow audit verdict=fail: {counts}{first}")


def _first_audit_finding(report: dict) -> str:
    for section in ("health", "complexity", "dead_code", "duplication"):
        block = report.get(section)
        findings = block.get("findings") if isinstance(block, dict) else None
        if not isinstance(findings, list):
            continue
        for finding in findings:
            if isinstance(finding, dict) and finding.get("introduced", True):
                where = f"{finding.get('path', finding.get('file', '?'))}:{finding.get('line', '?')}"
                return f"; first={where} {finding.get('name', finding.get('rule', '?'))}"
    return ""


def _run_family(
    repo: Path, family: str, command: tuple[str, ...], deadline: float, fingerprint_headroom: float
) -> tuple[dict[str, object], ProjectGateError | None, str]:
    capture = family in CAPTURED_FAMILIES
    exclusive = family in EXCLUSIVE_FAMILIES
    if exclusive:
        validate_react_doctor_flags(repo, LATEST_TOOL_PACKAGE[family], command, deadline=deadline)
    with source_tree_lock(repo, exclusive=exclusive, deadline=deadline) as lock_path:
        family_before = tree_fingerprint(repo, deadline=deadline) if exclusive else None
        remaining_budget = remaining(deadline, "before every check ran")
        grace = min(2.0, max(0.1, remaining_budget * 0.02))
        proof_count = 2 if exclusive else 1
        launch_headroom = min(1.0, max(0.1, remaining_budget * 0.01))
        command_timeout = remaining_budget - (2 * grace) - (proof_count * fingerprint_headroom) - launch_headroom
        if command_timeout <= 0:
            raise ProjectGateError("whole-run timeout has no command and shutdown headroom")
        receipt_path, receipt_token = terminal_receipt_spec(repo)
        if family_before is not None:
            begin_react_doctor(lock_path, family, family_before, receipt_path, receipt_token)
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
            completed = _run_bounded(bounded_command, capture=capture, timeout=command_timeout + (2 * grace) + 5)
        except OSError:
            if family_before is not None:
                rollback_react_doctor_launch(
                    repo,
                    lock_path,
                    family=family,
                    expected=family_before,
                    receipt_path=receipt_path,
                    receipt_token=receipt_token,
                    deadline=deadline,
                )
            raise
        if family_before is not None:
            clear_react_doctor_quarantine(
                repo,
                lock_path,
                family=family,
                expected=family_before,
                receipt_path=receipt_path,
                receipt_token=receipt_token,
                deadline=deadline,
            )
        else:
            consume_terminal_receipt(receipt_path, receipt_token)
    report_error: ProjectGateError | None = None
    if completed.returncode == 0 and capture:
        try:
            validate_quality_report(family, completed.stdout)
        except ProjectGateError as error:
            report_error = error
    detail = ""
    if completed.returncode != 0:
        detail = "\n".join(part for part in (completed.stdout, completed.stderr) if part).strip()
    return (
        {"family": family, "command": list(command), "exit": 4 if report_error else completed.returncode},
        report_error,
        detail,
    )


def require_staged_worktree_alignment(repo: Path, timeout: float) -> None:
    listings: list[set[str]] = []
    for options in (("--cached",), ()):
        result = _run_bounded(
            ["git", "-C", str(repo), "diff", *options, "--name-only", "-z"], capture=True, timeout=timeout
        )
        if result.returncode != 0:
            raise ProjectGateError(
                "cannot compare staged and worktree content: " + (result.stderr.strip() or "git diff failed")
            )
        listings.append({name for name in result.stdout.split("\0") if name})
    diverged = sorted(listings[0] & listings[1])
    if diverged:
        raise ProjectGateError(
            "staged content differs from the worktree for: "
            + ", ".join(diverged)
            + "; the commit gate scans the worktree, so stage the current state before committing"
        )


def run_families(repo: Path, families: list[str], timeout: float) -> list[dict[str, object]]:
    if not math.isfinite(timeout) or timeout <= 0:
        raise ProjectGateError("whole-run timeout must be finite and positive")
    deadline = time.monotonic() + timeout
    hygiene = SCRIPT_DIR.parents[2] / "scripts/git-env-hygiene-contract.py"
    with source_tree_lock(repo, exclusive=False, deadline=deadline):
        checked_result = run_captured(
            [sys.executable, str(hygiene), "--root", str(repo)],
            remaining(deadline, "during Git environment preflight"),
            env=git_env(),
        )
        checked = subprocess.CompletedProcess(
            [sys.executable, str(hygiene), "--root", str(repo)],
            checked_result.returncode,
            checked_result.stdout.decode("utf-8", "replace"),
            checked_result.stderr.decode("utf-8", "replace"),
        )
        if checked.returncode:
            detail = (checked.stderr or checked.stdout).strip()
            raise ProjectGateError(detail or "Git environment hygiene preflight failed")
        remaining(deadline, "before manifest validation")
        commands = load_manifest(repo, deadline=deadline, validate_external=False)
        missing = [family for family in families if family not in commands]
        if missing:
            raise ProjectGateError(f"{MANIFEST_NAME} has no command for required families: {', '.join(missing)}")
        if any(commands[family][0].lower() in {"npx", "npx.cmd"} for family in families):
            try:
                validate_external_npx(repo, deadline=deadline)
            except CoordinationError as error:
                raise ProjectGateError(str(error)) from error
        fingerprint_started = time.monotonic()
        before = tree_fingerprint(repo, deadline=deadline)
        fingerprint_headroom = max(0.05, (time.monotonic() - fingerprint_started) * 2)
    results: dict[int, dict[str, object]] = {}
    report_errors: dict[int, ProjectGateError] = {}
    execution_errors: dict[int, Exception] = {}
    details: dict[int, str] = {}

    def collect(index: int, outcome: tuple[dict[str, object], ProjectGateError | None, str]) -> None:
        result, report_error, detail = outcome
        results[index] = result
        details[index] = detail
        if report_error is not None:
            report_errors[index] = report_error

    shared = [(index, family) for index, family in enumerate(families) if family not in EXCLUSIVE_FAMILIES]
    exclusive = [(index, family) for index, family in enumerate(families) if family in EXCLUSIVE_FAMILIES]
    if shared:
        with ThreadPoolExecutor(max_workers=min(MAX_PARALLEL_FAMILIES, len(shared))) as pool:
            futures = {
                index: pool.submit(_run_family, repo, family, commands[family], deadline, fingerprint_headroom)
                for index, family in shared
            }
            for index, _family in shared:
                try:
                    collect(index, futures[index].result())
                except Exception as error:
                    execution_errors[index] = error
    for index, family in exclusive:
        try:
            collect(index, _run_family(repo, family, commands[family], deadline, fingerprint_headroom))
        except Exception as error:
            execution_errors[index] = error
    if execution_errors:
        if len(execution_errors) == 1:
            raise next(iter(execution_errors.values()))
        raise ProjectGateError(
            "; ".join(f"{families[index]}: {execution_errors[index]}" for index in sorted(execution_errors))
        )
    with source_tree_lock(repo, exclusive=False, deadline=deadline):
        after = tree_fingerprint(repo, deadline=deadline)
    if after != before:
        raise ProjectGateError("project gate commands mutated the repository tree" + _dirty_paths_note(repo, deadline))
    for index in range(len(families)):
        result = results.get(index)
        detail = details.get(index, "")
        if result is not None and result["exit"] != 0 and detail:
            print(detail[-4000:], file=sys.stderr)
    if report_errors:
        raise ProjectGateError(
            "; ".join(f"{families[index]}: {report_errors[index]}" for index in sorted(report_errors))
        )
    return [results[index] for index in range(len(families))]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("run", "phase", "benchmark"))
    parser.add_argument("--repo", required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--family", action="append")
    parser.add_argument("--phase", choices=("commit", "push", "ci"))
    parser.add_argument("--samples", type=int, default=3)
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        if args.command == "benchmark":
            if args.family or args.phase:
                raise ProjectGateError("benchmark does not accept --family or --phase")
            digest = tree_fingerprint(repo, deadline=time.monotonic() + args.timeout)
            receipt = benchmark(repo, args.samples, args.timeout, digest)
            print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
            return 0 if receipt["verdict"] == "PASS" else 4
        if args.command == "run":
            if not args.family or args.phase:
                raise ProjectGateError("run requires --family and does not accept --phase")
            families = args.family
        else:
            if not args.phase or args.family:
                raise ProjectGateError("phase requires --phase and does not accept --family")
            families = load_phase(repo, args.phase)
            if args.phase == "commit":
                require_staged_worktree_alignment(repo, args.timeout)
        results = run_families(repo, families, args.timeout)
    except (
        CoordinationError,
        OSError,
        subprocess.SubprocessError,
        ProjectGateError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"project-gate: FAIL: {error}", file=sys.stderr)
        return 4
    for result in results:
        print(f"project-gate: {result['family']} {'PASS' if result['exit'] == 0 else 'FAIL'}")
    return 0 if all(result["exit"] == 0 for result in results) else 4


if __name__ == "__main__":
    raise SystemExit(main())

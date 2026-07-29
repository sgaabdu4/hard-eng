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
    "fallow": re.compile(r"\bfallow\b.*\baudit\b"),
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
    commands = load_manifest(repo)
    missing = [family for family in families if family not in commands]
    if missing:
        raise ProjectGateError(
            f"{MANIFEST_NAME} has no command for required families: {', '.join(missing)}"
        )
    before = tree_fingerprint(repo)
    deadline = time.monotonic() + timeout
    results: list[dict[str, object]] = []
    for family in families:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ProjectGateError("whole-run timeout exhausted before every check ran")
        command = commands[family]
        completed = subprocess.run(
            [
                sys.executable, str(BOUNDED), "--timeout", str(max(1, int(remaining))),
                "--cwd", str(repo), "--", *command,
            ],
            check=False,
        )
        results.append({
            "family": family,
            "command": list(command),
            "exit": completed.returncode,
        })
        if completed.returncode != 0:
            break
    if tree_fingerprint(repo) != before:
        raise ProjectGateError("project gate commands mutated the repository tree")
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

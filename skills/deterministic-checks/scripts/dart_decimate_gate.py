#!/usr/bin/env python3
"""Run Dart Decimate at Git root while validating a nested Dart package."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


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
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())

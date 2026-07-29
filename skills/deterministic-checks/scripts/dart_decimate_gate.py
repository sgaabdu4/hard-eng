#!/usr/bin/env python3
"""Run one full Dart Decimate gate for an exact Dart package owner."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from git_env import git_env


def error(message: str) -> int:
    print(f"Dart Decimate gate: {message}", file=sys.stderr)
    return 2


def git(package: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(package), *args],
        capture_output=True,
        text=True,
        check=False,
        env=git_env(),
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
    args = parser.parse_args()

    package = Path(args.package).expanduser().resolve()
    if not package.is_dir() or not (package / "pubspec.yaml").is_file():
        return error("--package must be a Dart package directory")
    root = repository_root(package)
    if root is None:
        return error("package is not inside a Git repository")
    try:
        relative_package = package.relative_to(root)
    except ValueError:
        return error("package resolves outside the Git repository")
    if shutil.which("npx") is None:
        return error("npx is required")

    command = ["npx", "--yes", "dart-decimate@latest", "json", str(root)]
    if relative_package != Path("."):
        command.extend(["--workspace", relative_package.as_posix()])
    return subprocess.run(
        command,
        cwd=root,
        check=False,
        env=git_env(),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())

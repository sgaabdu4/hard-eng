#!/usr/bin/env python3
"""Publish stdin bytes through the canonical setup safe-file writer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.setup.cli_errors import run_cli
from safe_file import SafeFileError, create_path, read_snapshot, replace_path_if_unchanged


def parse_mode(value: str) -> int:
    try:
        mode = int(value, 8)
    except ValueError as error:
        raise argparse.ArgumentTypeError("mode must be an octal file mode") from error
    if mode < 0 or mode > 0o777 or mode & 0o022:
        raise argparse.ArgumentTypeError("mode must not grant group/world write access")
    return mode


def publish(path: Path, data: bytes, mode: int) -> None:
    try:
        expected, existing_mode = read_snapshot(path.parent, Path(path.name))
    except FileNotFoundError:
        create_path(path, data, mode)
    else:
        replace_path_if_unchanged(
            path, expected, existing_mode, data, replacement_mode=mode
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", required=True, type=Path)
    parser.add_argument("--mode", required=True, type=parse_mode)
    args = parser.parse_args()
    try:
        publish(args.path.expanduser(), sys.stdin.buffer.read(), args.mode)
    except (OSError, SafeFileError, ValueError) as error:
        print(f"safe-file: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli("safe-file", main))

#!/usr/bin/env python3
"""Bind completed setup installation to the exact canonical pin files."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[2]
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from scripts.setup import safe_file
from scripts.setup.cli_errors import run_cli


PIN_PATHS = (
    Path("scripts/setup/manifest.json"),
    Path("runtime/npm/package.json"),
    Path("runtime/npm/package-lock.json"),
)


class PinStateError(ValueError):
    pass


def digest(root: Path) -> str:
    owner = hashlib.sha256()
    for relative in PIN_PATHS:
        content, mode = safe_file.read_snapshot(root, relative)
        encoded = relative.as_posix().encode()
        owner.update(len(encoded).to_bytes(4, "big"))
        owner.update(encoded)
        owner.update(mode.to_bytes(4, "big"))
        owner.update(len(content).to_bytes(8, "big"))
        owner.update(content)
    return owner.hexdigest()


def receipt(root: Path) -> bytes:
    return f"schema=1\nsha256={digest(root)}\n".encode()


def record(root: Path, state: Path) -> None:
    current = receipt(root)
    try:
        before, mode = safe_file.read_snapshot(state)
    except FileNotFoundError:
        safe_file.create_path(state, current, 0o600)
    else:
        safe_file.replace_path_if_unchanged(state, before, mode, current)


def check(root: Path, state: Path) -> None:
    try:
        current, mode = safe_file.read_snapshot(state)
    except FileNotFoundError as error:
        raise PinStateError("installed pin receipt is missing; run setup.sh install") from error
    if mode != 0o600 or current != receipt(root):
        raise PinStateError("installed pins are stale; run setup.sh install")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    value.add_argument("command", choices=("record", "check"))
    value.add_argument("--root", type=Path, required=True)
    value.add_argument("--state", type=Path, required=True)
    return value


def main() -> int:
    arguments = parser().parse_args()
    try:
        if arguments.command == "record":
            record(arguments.root, arguments.state)
        else:
            check(arguments.root, arguments.state)
    except (OSError, PinStateError) as error:
        print(f"setup:pin-state: FAIL: {error}", file=sys.stderr)
        return 1
    print(f"setup:pin-state: PASS action={arguments.command}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run_cli("setup:pin-state", main))

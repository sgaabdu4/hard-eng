#!/usr/bin/env python3
"""Fixture script for the script_runner regression: exits, prints, reads stdin, and mutates process state on request."""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent)]

from bounded_run import run_captured


def main() -> int:
    command = sys.argv[1] if len(sys.argv) > 1 else "exit"
    if command == "exit":
        code = int(sys.argv[2])
        print(f"exit {code}")
        return code
    if command == "die":
        raise SystemExit("probe died")
    if command == "crash":
        raise ValueError("boom")
    if command == "echo":
        print(f"stdin={sys.stdin.read()}")
        return 0
    if command == "pid":
        print(os.getpid())
        return 0
    if command == "spawn":
        child = run_captured([sys.executable, __file__, "exit", "0"], 60)
        sys.stdout.write(child.stdout.decode("utf-8", "replace"))
        return child.returncode
    if command == "mutate":
        print(f"cwd={os.getcwd()}")
        os.environ["PROBE_LEAK"] = "1"
        os.chdir(os.path.dirname(os.getcwd()) or "/")
        sys.argv.append("leaked")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

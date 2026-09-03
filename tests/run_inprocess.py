#!/usr/bin/env python3
"""Run every in-process regression without pytest: same seam, same child-process guard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parents[1] / "skills" / "deterministic-checks" / "scripts"
sys.path[:0] = [str(RUNNER_DIR), str(Path(__file__).resolve().parent)]

import script_runner
from regressions import IN_PROCESS


def main() -> int:
    os.environ[script_runner.INPROCESS_FLAG] = "1"
    script_runner.install_finder()
    script_runner.install_child_guard()
    for script in IN_PROCESS:
        code = script_runner.load_script(script).main()
        if code != 0:
            print(f"in-process regression FAIL: {script.name} exit={code}")
            return 1
    print(f"in-process regressions: PASS ({len(IN_PROCESS)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

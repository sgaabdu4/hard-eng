#!/usr/bin/env python3
"""Fake mutmut for example-7 re-verification: answers --version with a
distinctive fake string so evidence proves THIS executable was used, and
forwards every other subcommand (run, results, etc.) to the real mutmut
pinned at .venv-mutation so actual mutants get generated and scored."""

import subprocess
import sys

REAL_MUTMUT = "/Users/abid/.agents/.venv-mutation/bin/mutmut"


def main():
    argv = sys.argv[1:]
    if argv == ["--version"]:
        print("mutmut, version 9.9.9")
        return 0
    return subprocess.call([REAL_MUTMUT, *argv])


if __name__ == "__main__":
    sys.exit(main())

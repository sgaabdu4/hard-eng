#!/usr/bin/env python3
"""Fake `gh` for S-10 outside-verification. Logs every argv line and
answers the repo-visibility probe from FAKE_GH_PRIVATE (default false).
Never talks to a real network."""

import os
import sys

LOG_PATH = os.environ.get("S10_FAKE_GH_LOG", "/Users/abid/.agents/features/build-loop-records/receipts/s10-fake-gh.log")


def main():
    private = os.environ.get("FAKE_GH_PRIVATE", "false").strip().lower() in ("1", "true", "yes")
    result = "true" if private else "false"
    argv_line = " ".join(["gh"] + sys.argv[1:])
    with open(LOG_PATH, "a") as f:
        f.write(f"api.github.com {argv_line} -> {result}\n")
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())

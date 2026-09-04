#!/usr/bin/env python3
import os
import sys

LOG = os.environ.get("FAKE_GH_LOG", "/tmp/fake-gh.log")


def main():
    argv = sys.argv[1:]
    with open(LOG, "a") as f:
        f.write("api.github.com gh " + " ".join(argv) + "\n")
    if argv[:2] == ["repo", "view"]:
        priv = os.environ.get("FAKE_GH_PRIVATE", "false")
        sys.stdout.write(priv + "\n")
        return 0
    if argv[:2] == ["pr", "create"]:
        sys.stdout.write("https://github.invalid/fake/pulls/1\n")
        return 0
    sys.stdout.write("{}\n")
    return 0


sys.exit(main())

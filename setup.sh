#!/bin/sh
set -eu
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
git clone --quiet --depth 1 --recurse-submodules --branch main https://github.com/sgaabdu4/hard-eng.git "$temporary/source"
if [ -f "$PWD/.hooks/hard-eng-source.json" ]; then
    python3 -I -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from update import update; print(update(Path.cwd()))' "$temporary/source/.hooks"
else
    python3 "$temporary/source/setup.py" "$PWD"
fi

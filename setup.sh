#!/bin/sh
set -eu
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
git clone --quiet --depth 1 --recurse-submodules --branch main https://github.com/sgaabdu4/hard-eng.git "$temporary/source"
if [ -f "$PWD/.hooks/hard-eng-source.json" ]; then
    uv run --project "$temporary/source" --locked --no-dev python -I -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from update import update; print(update(Path.cwd()))' "$temporary/source/.hooks"
else
    uv run --project "$temporary/source" --locked --no-dev python "$temporary/source/setup.py" "$PWD"
fi

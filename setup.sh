#!/bin/sh
set -eu
if [ "$#" -eq 0 ]; then
    temporary=$(mktemp -d)
    trap 'rm -rf "$temporary"' EXIT HUP INT TERM
    git clone --quiet --depth 1 --branch main https://github.com/sgaabdu4/hard-eng.git "$temporary/source"
    revision=$(uv run --project "$temporary/source" --locked --no-dev python -I -c 'import sys; sys.path.insert(0, sys.argv[1]); from update import latest_verified; print(latest_verified("") or sys.exit("No CI-verified Hard Eng revision is available; nothing installed."))' "$temporary/source/.hooks")
    git -C "$temporary/source" fetch --quiet --depth 1 origin "$revision"
    git -C "$temporary/source" checkout --quiet --detach "$revision"
    git -C "$temporary/source" submodule update --init --recursive --quiet
    sh "$temporary/source/setup.sh" "$temporary/source"
elif [ -f "$PWD/.hooks/hard-eng-source.json" ]; then
    uv run --project "$1" --locked --no-dev python -I -c 'import sys; from pathlib import Path; sys.path.insert(0, sys.argv[1]); from update import update; print(update(Path.cwd(), repair=True))' "$1/.hooks"
else
    uv run --project "$1" --locked --no-dev python "$1/setup.py" "$PWD"
fi

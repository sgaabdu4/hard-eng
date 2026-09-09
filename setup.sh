#!/bin/sh
set -eu
temporary=$(mktemp -d)
trap 'rm -rf "$temporary"' EXIT HUP INT TERM
git clone --quiet --depth 1 --branch main https://github.com/sgaabdu4/hard-eng.git "$temporary/source"
python3 "$temporary/source/setup.py" "$PWD"

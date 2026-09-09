#!/bin/sh
set -eu
script_dir=$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)
repo=${1:-.}
if [ "$#" -gt 0 ]; then shift; fi
exec python3 "$script_dir/bin/hard-eng" --repo "$repo" install "$@"

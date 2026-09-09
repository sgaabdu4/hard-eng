#!/bin/sh
set -eu
hard_eng_download=$(mktemp -d)
trap 'rm -rf "$hard_eng_download"' 0
git clone --quiet --filter=blob:none https://github.com/sgaabdu4/hard-eng.git "$hard_eng_download"
python3 "$hard_eng_download/bin/hard-eng" install "$@"

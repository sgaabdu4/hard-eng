#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -x "$SCRIPT_DIR/setup.sh" ]]; then
  exec "$SCRIPT_DIR/setup.sh" "$@"
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "Missing required command: curl" >&2
  exit 1
fi

tmp="${TMPDIR:-/tmp}/hard-eng-setup.sh"
curl -fsSLo "$tmp" https://raw.githubusercontent.com/sgaabdu4/hard-eng/main/scripts/setup.sh
exec bash "$tmp" "$@"

#!/usr/bin/env bash
# Bootstrap for `npx -y github:sgaabdu4/hard-eng`; the installer itself lives in runtime/repository_native.
set -euo pipefail

fail() {
  printf 'hard-eng setup: %s\n' "$*" >&2
  exit 1
}

source_path=${BASH_SOURCE[0]:-}
[[ -n "$source_path" && -f "$source_path" ]] || fail "run install.sh from its checkout (npx -y github:sgaabdu4/hard-eng)"
while [[ -L "$source_path" ]]; do
  link_target=$(readlink "$source_path")
  case $link_target in
    /*) source_path=$link_target ;;
    *) source_path=$(dirname "$source_path")/$link_target ;;
  esac
done
root=$(cd "$(dirname "$source_path")" && pwd -P)
[[ -f "$root/bin/hard-eng" && -f "$root/runtime/repository_native/installer.py" ]] ||
  fail "installer files are missing next to install.sh: $root"
command -v python3 >/dev/null 2>&1 || fail "python3 3.12 or newer is required"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' ||
  fail "python3 3.12 or newer is required"
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$root/bin/hard-eng" install "$@"

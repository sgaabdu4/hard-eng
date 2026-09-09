#!/bin/bash
set -eu

ROOT=$(cd "$(dirname "$0")/.." && pwd -P)
scratch_parent=$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-scratch-parent.XXXXXX")
probe_home=$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-scratch-home.XXXXXX")
scratch_parent=$(cd "$scratch_parent" && pwd -P)
probe_home=$(cd "$probe_home" && pwd -P)
cleanup() {
  [ -z "${target:-}" ] || [ ! -e "$target" ] || safe_remove_scratch_tree "$target"
  rm -f "$probe_home/.local/bin" "$probe_home/protected/sentinel"
  rmdir "$probe_home/.local" "$probe_home/protected" 2>/dev/null || true
  rmdir "$scratch_parent" "$probe_home"
}
trap cleanup EXIT HUP INT TERM

HOME=$probe_home
TMPDIR=$scratch_parent/
export HOME TMPDIR
. "$ROOT/scripts/setup/common.sh"

target=$(setup_scratch_dir contract)
case "$target" in
  "$scratch_parent"/.hard-eng-contract.*) ;;
  *) setup_fail "scratch root was not canonicalized"; exit 1 ;;
esac
safe_remove_scratch_tree "$target"
[ ! -e "$target" ] || { setup_fail "scratch cleanup failed"; exit 1; }
if TMPDIR=/ setup_scratch_root >/dev/null 2>&1; then
  setup_fail "filesystem-root scratch owner was accepted"
  exit 1
fi
mkdir -p "$probe_home/.local" "$probe_home/protected"
printf 'preserve\n' >"$probe_home/protected/sentinel"
ln -s "$probe_home/protected" "$probe_home/.local/bin"
if install_managed_directories >/dev/null 2>&1; then
  setup_fail "symlinked managed root was accepted"
  exit 1
fi
[ "$(cat "$probe_home/protected/sentinel")" = preserve ] ||
  { setup_fail "managed root conflict changed user bytes"; exit 1; }
printf 'setup-scratch-contract: PASS\n'

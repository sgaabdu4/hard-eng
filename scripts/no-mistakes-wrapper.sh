#!/usr/bin/env bash
# Managed by hard-eng no-mistakes wrapper.
set -euo pipefail

real_home="${HOME:-}"
if [[ -z "$real_home" ]]; then
  echo "no-mistakes wrapper: HOME is required." >&2
  exit 1
fi

default_nm_home="${HARD_ENG_NO_MISTAKES_DEFAULT_NM_HOME:-$real_home/.no-mistakes}"
default_real_binary="${HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN:-$default_nm_home/bin/no-mistakes}"
default_hard_eng_home="${HARD_ENG_DEFAULT_HOME:-$real_home/.agents}"
nm_home="${NM_HOME:-${NO_MISTAKES_HOME:-$default_nm_home}}"
hard_eng_home="${HARD_ENG_HOME:-$default_hard_eng_home}"
if [[ -n "${HARD_ENG_NO_MISTAKES_REAL_BIN:-}" ]]; then
  real_binary="$HARD_ENG_NO_MISTAKES_REAL_BIN"
elif [[ -n "${HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN+x}" ]]; then
  real_binary="$default_real_binary"
else
  real_binary="$nm_home/bin/no-mistakes"
fi

if [[ ! -x "$real_binary" ]]; then
  echo "no-mistakes wrapper: real binary not found at $real_binary" >&2
  exit 127
fi

if [[ "${1:-}" != "init" ]]; then
  NM_HOME="$nm_home" exec "$real_binary" "$@"
fi

for arg in "$@"; do
  if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
    NM_HOME="$nm_home" exec "$real_binary" "$@"
  fi
done

isolated_home="${HARD_ENG_NO_MISTAKES_AGENT_HOME:-}"
cleanup=0
if [[ -z "$isolated_home" ]]; then
  isolated_home="$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-no-mistakes-home.XXXXXX")"
  cleanup=1
fi

cleanup_isolated_home() {
  if [[ "$cleanup" == "1" ]]; then
    rm -rf "$isolated_home"
  fi
}
trap cleanup_isolated_home EXIT

mkdir -p "$isolated_home"
HOME="$isolated_home" \
  CODEX_HOME="$isolated_home/.codex" \
  NM_HOME="$nm_home" \
  NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
  NO_MISTAKES_NO_UPDATE_CHECK=1 \
  "$real_binary" "$@"

repair_script="$hard_eng_home/integrations/no-mistakes/scripts/repair-gate-hook.mjs"
if [[ -f "$repair_script" ]]; then
  node "$repair_script" "$(pwd)"
fi

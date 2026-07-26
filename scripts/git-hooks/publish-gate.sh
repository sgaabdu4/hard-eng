#!/bin/bash
set -u

ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
MODE=${1:-push}

run_gate() {
  local label=$1
  shift
  local output status
  output=$("$@" 2>&1)
  status=$?
  if [[ "$status" -ne 0 ]]; then
    printf '%s\n' "$output" >&2
    printf 'publish-gate: %s FAIL\n' "$label" >&2
    return "$status"
  fi
  printf 'publish-gate: %s PASS\n' "$label"
}

run_gate managed-skills node "$ROOT/scripts/check-managed-skills.js" || exit
run_gate design-md node "$ROOT/skills/deterministic-checks/scripts/check-design-md.js" || exit
if [[ "$MODE" == "push" ]]; then
  run_gate skill-contracts python3 "$ROOT/skills/deterministic-checks/scripts/bounded_run.py" \
    --timeout 600 -- python3 "$ROOT/scripts/check-skill-contracts.py" || exit
fi

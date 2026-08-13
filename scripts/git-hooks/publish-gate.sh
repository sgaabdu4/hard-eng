#!/bin/bash
set -u

ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
MODE=${1:-push}
case "$MODE" in
  commit|push) ;;
  *)
    printf 'usage: %s [commit|push]\n' "$0" >&2
    exit 2
    ;;
esac

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

WORKTREE_INTENT=publish
[[ "$MODE" == "commit" ]] && WORKTREE_INTENT=write
run_gate worktree python3 "$ROOT/skills/deterministic-checks/scripts/worktree.py" \
  --repo "$ROOT" --intent "$WORKTREE_INTENT" || exit
if [[ "$MODE" == "commit" ]]; then
  run_gate project-checks python3 \
    "$ROOT/skills/deterministic-checks/scripts/project_gate.py" phase \
    --repo "$ROOT" --timeout 180 --phase commit || exit
else
  run_gate project-checks python3 \
    "$ROOT/skills/deterministic-checks/scripts/project_gate.py" phase \
    --repo "$ROOT" --timeout 300 --phase push || exit
fi

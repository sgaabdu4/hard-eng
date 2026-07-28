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
    "$ROOT/skills/deterministic-checks/scripts/project_gate.py" run \
    --repo "$ROOT" --timeout 180 --family format --family lint || exit
else
  run_gate project-checks python3 \
    "$ROOT/skills/deterministic-checks/scripts/project_gate.py" run \
    --repo "$ROOT" --timeout 300 --family typecheck --family format --family lint \
    --family tests --family fallow || exit
fi
run_gate managed-skills python3 "$ROOT/skills/deterministic-checks/scripts/bounded_run.py" \
  --timeout 120 --cwd "$ROOT" -- node "$ROOT/scripts/check-managed-skills.js" || exit
run_gate design-md python3 "$ROOT/skills/deterministic-checks/scripts/bounded_run.py" \
  --timeout 120 --cwd "$ROOT" -- node \
  "$ROOT/skills/deterministic-checks/scripts/check-design-md.js" "$ROOT/DESIGN.md" || exit
if [[ "$MODE" == "push" ]]; then
  run_gate skill-contracts python3 "$ROOT/skills/deterministic-checks/scripts/bounded_run.py" \
    --timeout 600 --cwd "$ROOT" -- python3 "$ROOT/scripts/check-skill-contracts.py" || exit
fi

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

should_run_quality_preflight() {
  if [[ "${HARD_ENG_NO_MISTAKES_SKIP_PREFLIGHT:-}" == "1" ]]; then
    return 1
  fi

  case "${1:-}" in
    rerun)
      return 0
      ;;
    axi)
      [[ "${2:-}" == "run" ]]
      return
      ;;
    *)
      return 1
      ;;
  esac
}

run_quality_preflight() {
  local gate_script="$hard_eng_home/scripts/check-project-quality-gates.mjs"
  local worktree_script="$hard_eng_home/scripts/ensure-worktree-ready.sh"
  if [[ ! -f "$gate_script" ]]; then
    echo "no-mistakes wrapper: deterministic gate script not found at $gate_script" >&2
    exit 127
  fi
  if [[ ! -x "$worktree_script" ]]; then
    echo "no-mistakes wrapper: worktree readiness script not found at $worktree_script" >&2
    exit 127
  fi

  if ! command -v git >/dev/null 2>&1; then
    echo "no-mistakes wrapper: git is required for deterministic preflight." >&2
    exit 127
  fi
  if ! command -v node >/dev/null 2>&1; then
    echo "no-mistakes wrapper: node is required for deterministic preflight." >&2
    exit 127
  fi

  local repo_root
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [[ -z "$repo_root" ]]; then
    return 0
  fi

  set +e
  "$worktree_script" --check --require-pre-push "$repo_root"
  local status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    echo "no-mistakes wrapper: worktree readiness failed before no-mistakes; fix project hooks first." >&2
    exit "$status"
  fi

  set +e
  node "$gate_script" --require-push-gate "$repo_root"
  status=$?
  set -e
  if [[ "$status" -ne 0 ]]; then
    echo "no-mistakes wrapper: deterministic quality gate failed before no-mistakes; fix .no-mistakes.yaml or project gates first." >&2
    exit "$status"
  fi
}

if [[ "${1:-}" != "init" ]]; then
  if should_run_quality_preflight "$@"; then
    run_quality_preflight
  fi
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
  if command -v node >/dev/null 2>&1; then
    node "$repair_script" "$(pwd)"
  else
    echo "no-mistakes wrapper: skipping repair hook because node is not on PATH." >&2
  fi
fi

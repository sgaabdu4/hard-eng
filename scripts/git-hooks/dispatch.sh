#!/bin/bash
set -u

# git-env-hygiene: exempt - dispatch resolves the invoking hook's own repository,
# so the inherited environment is the correct target; each child sanitizes itself.

owner_common_dir() (
  local variable
  for variable in $(git rev-parse --local-env-vars); do
    unset "$variable"
  done
  git -C "$1" rev-parse --path-format=absolute --git-common-dir 2>/dev/null
)

run_worktree_setup() {
  local repo_top git_dir common_dir setup tracked_drift
  [[ "${1:-}" == "0000000000000000000000000000000000000000" && "${3:-}" == "1" ]] ||
    return 0
  repo_top=$(git rev-parse --show-toplevel 2>/dev/null) || return 0
  git_dir=$(git rev-parse --path-format=absolute --git-dir 2>/dev/null) || return 0
  common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || return 0
  [[ ! "$git_dir" -ef "$common_dir" ]] || return 0
  setup="$repo_top/scripts/worktree-setup.sh"
  [[ -e "$setup" || -L "$setup" ]] || return 0
  [[ -f "$setup" && ! -L "$setup" && -x "$setup" ]] || {
    printf 'hard-eng-hook: worktree setup must be a regular executable: %s\n' "$setup" >&2
    return 1
  }
  git -C "$repo_top" ls-files --error-unmatch -- scripts/worktree-setup.sh >/dev/null 2>&1 || {
    printf 'hard-eng-hook: worktree setup must be tracked: %s\n' "$setup" >&2
    return 1
  }
  "$setup" || return $?
  tracked_drift=$(git -C "$repo_top" status --short --untracked-files=no 2>/dev/null) || return 1
  [[ -z "$tracked_drift" ]] || {
    printf 'hard-eng-hook: worktree setup changed tracked files\n%s\n' "$tracked_drift" >&2
    return 1
  }
}

hook=${0##*/}
hooks_dir=$(cd "$(dirname "$0")" && pwd -P)
global_status=0

if [[ "$hook" == "post-checkout" ]]; then
  "$hooks_dir/hard-eng-copy-worktree-env" "$@" || global_status=$?
  if [[ "$global_status" -eq 0 ]]; then
    run_worktree_setup "$@" || global_status=$?
  fi
fi

if [[ "$hook" == "pre-commit" || "$hook" == "pre-push" ]]; then
  gate_source=$(readlink "$0" 2>/dev/null) || gate_source=$0
  [[ "$gate_source" == /* ]] || gate_source="$hooks_dir/$gate_source"
  owner_root=$(cd "$(dirname "$gate_source")/../.." 2>/dev/null && pwd -P) || owner_root=
  repo_top=$(git rev-parse --show-toplevel 2>/dev/null) || repo_top=
  repo_common=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) || repo_common=
  owner_common=$(owner_common_dir "$owner_root") || owner_common=
  if [[ -n "$repo_top" && -n "$repo_common" && -n "$owner_common" &&
    "$repo_common" -ef "$owner_common" ]]; then
    gate="$repo_top/scripts/git-hooks/publish-gate.sh"
    if [[ ! -x "$gate" ]]; then
      printf 'hard-eng-hook: required checkout gate missing: %s\n' "$gate" >&2
      exit 1
    fi
    "$gate" "${hook#pre-}" || exit $?
  fi
fi

common_dir=$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null) ||
  exit "$global_status"
native="$common_dir/hooks/$hook"

if [[ -x "$native" && ! "$native" -ef "$0" ]]; then
  if [[ "$hook" != "post-checkout" ]]; then
    exec "$native" "$@"
  fi
  "$native" "$@" || {
    native_status=$?
    [[ "$global_status" -ne 0 ]] || global_status=$native_status
  }
fi

exit "$global_status"

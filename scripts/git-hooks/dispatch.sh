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

hook=${0##*/}
hooks_dir=$(cd "$(dirname "$0")" && pwd -P)
global_status=0

if [[ "$hook" == "post-checkout" ]]; then
  "$hooks_dir/hard-eng-copy-worktree-env" "$@" || global_status=$?
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

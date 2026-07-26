#!/bin/bash
set -u

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
  if [[ -n "$owner_root" && -n "$repo_top" && "$repo_top" -ef "$owner_root" &&
    -x "$owner_root/scripts/git-hooks/publish-gate.sh" ]]; then
    "$owner_root/scripts/git-hooks/publish-gate.sh" "${hook#pre-}" || exit $?
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

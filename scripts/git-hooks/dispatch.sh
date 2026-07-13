#!/bin/bash
set -u

hook=${0##*/}
hooks_dir=$(cd "$(dirname "$0")" && pwd -P)
global_status=0

if [[ "$hook" == "post-checkout" ]]; then
  "$hooks_dir/hard-eng-copy-worktree-env" "$@" || global_status=$?
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

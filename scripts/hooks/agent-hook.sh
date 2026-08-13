#!/bin/bash
# Agent runtimes run hook commands through the user's shell, which may be fish.
# Registering this wrapper pins every guard invocation to bash semantics.
set -u

# Parameter expansion instead of a subshell plus a dirname exec: this runs on
# every tool call in every runtime. ${0%/*} returns $0 unchanged when the path
# has no slash, which would build an invalid policy path, hence the guard.
HOOK_DIR=${0%/*}
[ "$HOOK_DIR" = "$0" ] && HOOK_DIR=.
[[ "${2:-}" == "posttooluse" || "${2:-}" == "stop" ]] && exit 0
perl "$HOOK_DIR/../enforcement_policy.pl" "$@" && exit 0
reason='Hard Eng could not check this tool call because its policy failed. Run ./setup.sh check.'
if [[ "${1:-}" == "copilot" ]]; then
  printf '{"permissionDecision":"deny","permissionDecisionReason":"%s"}' "$reason"
else
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"%s"}}' "$reason"
fi

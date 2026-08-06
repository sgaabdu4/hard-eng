#!/bin/bash
# Agent runtimes run hook commands through the user's shell, which may be fish.
# Registering this wrapper pins every guard invocation to bash semantics.
set -u

# Parameter expansion instead of a subshell plus a dirname exec: this runs on
# every tool call in every runtime. ${0%/*} returns $0 unchanged when the path
# has no slash, which would build "agent-hook.sh/agent_hook.py", hence the guard.
HOOK_DIR=${0%/*}
[ "$HOOK_DIR" = "$0" ] && HOOK_DIR=.
exec python3 "$HOOK_DIR/agent_hook.py" "$@"

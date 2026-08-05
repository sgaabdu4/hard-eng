#!/bin/bash
# Agent runtimes run hook commands through the user's shell, which may be fish.
# Registering this wrapper pins every guard invocation to bash semantics.
set -u

HOOK_DIR=$(cd "$(dirname "$0")" && pwd -P)
exec python3 "$HOOK_DIR/agent_hook.py" "$@"

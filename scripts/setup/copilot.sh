#!/bin/bash

COPILOT_DIR=$HOME/.copilot
CANONICAL_AGENTS=$HOME/.agents/AGENTS.md
COPILOT_PROFILE_TOOL=$ROOT/scripts/setup/copilot-profile.py

copilot_home_status() {
  if [ -L "$COPILOT_DIR" ] || { [ -e "$COPILOT_DIR" ] && [ ! -d "$COPILOT_DIR" ]; }; then
    setup_fail "Copilot home is not a regular directory: $COPILOT_DIR"
    return 1
  fi
  [ -d "$COPILOT_DIR" ] || return 3
}

copilot_canonical_available() {
  [ -f "$CANONICAL_AGENTS" ] &&
    [ ! -L "$CANONICAL_AGENTS" ] &&
    [ "$CANONICAL_AGENTS" -ef "$ROOT/AGENTS.md" ] ||
    setup_fail "canonical instructions must be the repository file: $CANONICAL_AGENTS"
}

copilot_profile_tool() {
  python3 "$COPILOT_PROFILE_TOOL" "$1"
}

install_copilot_integration() {
  local status
  status=0
  copilot_home_status || status=$?
  case $status in
    0) ;;
    3) return ;;
    *) return "$status" ;;
  esac
  copilot_canonical_available || return 1
  copilot_profile_tool install
}

check_copilot_integration() {
  local status
  status=0
  copilot_home_status || status=$?
  case $status in
    0) ;;
    3) return ;;
    *) return "$status" ;;
  esac
  copilot_canonical_available || return 1
  copilot_profile_tool check
}

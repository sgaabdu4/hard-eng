#!/bin/bash

COPILOT_DIR=${COPILOT_HOME:-$HOME/.copilot}
CANONICAL_AGENTS=$HOME/.agents/AGENTS.md
COPILOT_PROFILE_TOOL=$ROOT/scripts/setup/copilot-profile.py
COPILOT_SETTINGS_TOOL=$ROOT/scripts/setup/copilot-settings.py
COPILOT_PLUGIN_STATE_TOOL=$ROOT/scripts/setup/copilot-plugin-state.py
COPILOT_CONTEXT_PLUGIN_SOURCE=
COPILOT_CONTEXT_PLUGIN_NAME=
COPILOT_CONTEXT_VERSION=

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

load_copilot_context_contract() {
  COPILOT_CONTEXT_PLUGIN_NAME=$(manifest get copilot.context_mode.plugin_name)
  COPILOT_CONTEXT_PLUGIN_SUBDIR=$(manifest get copilot.context_mode.plugin_source_subdir)
  COPILOT_CONTEXT_VERSION=$(manifest get codex.context_mode.version)
  COPILOT_CONTEXT_PLUGIN_SOURCE="$ASSET_DIR/npm-runtime/node_modules/context-mode/$COPILOT_CONTEXT_PLUGIN_SUBDIR"
}

copilot_context_state() {
  COPILOT_CONFIG_DIR="$COPILOT_DIR" \
    COPILOT_PLUGIN_SOURCE="$COPILOT_CONTEXT_PLUGIN_SOURCE" \
    COPILOT_PLUGIN_NAME="$COPILOT_CONTEXT_PLUGIN_NAME" \
    COPILOT_CONTEXT_VERSION="$COPILOT_CONTEXT_VERSION" \
    python3 "$COPILOT_PLUGIN_STATE_TOOL" status
}

copilot_settings_tool() {
  COPILOT_SETTINGS="$COPILOT_DIR/settings.json" \
    python3 "$COPILOT_SETTINGS_TOOL" "$1"
}

copilot_cli_available() {
  command -v copilot >/dev/null 2>&1 ||
    setup_fail "missing required command: copilot"
}

preflight_copilot_context() {
  local status
  load_copilot_context_contract
  copilot_cli_available || return 1
  status=0
  copilot_context_state || status=$?
  case $status in
    0|3|5) ;;
    *) return "$status" ;;
  esac
  status=0
  copilot_settings_tool check || status=$?
  case $status in
    0|5) ;;
    *) return "$status" ;;
  esac
}

converge_copilot_context() {
  local status
  status=0
  copilot_context_state || status=$?
  case $status in
    0) return ;;
    3|5)
      COPILOT_HOME="$COPILOT_DIR" copilot plugin install \
        "$COPILOT_CONTEXT_PLUGIN_SOURCE" >/dev/null ||
        { setup_fail "Copilot Context Mode plugin convergence failed"; return 1; }
      ;;
    *) return "$status" ;;
  esac
  copilot_context_state
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
  preflight_copilot_context || return 1
  converge_copilot_context || return 1
  copilot_settings_tool install || return 1
  copilot_profile_tool install
  check_copilot_integration
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
  load_copilot_context_contract
  copilot_cli_available || return 1
  copilot_context_state || return 1
  copilot_settings_tool check || return 1
  copilot_profile_tool check
}

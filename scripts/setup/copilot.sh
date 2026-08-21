#!/bin/bash

COPILOT_DIR=${COPILOT_HOME:-$HOME/.copilot}
CANONICAL_AGENTS=$HOME/.agents/AGENTS.md
COPILOT_PROFILE_TOOL=$ROOT/scripts/setup/copilot-profile.py
COPILOT_SETTINGS_TOOL=$ROOT/scripts/setup/copilot-settings.py
COPILOT_PLUGIN_STATE_TOOL=$ROOT/scripts/setup/copilot-plugin-state.py
COPILOT_TRANSACTION_TOOL=$ROOT/scripts/setup/copilot-transaction.py
COPILOT_CONTEXT_PLUGIN_SOURCE=
COPILOT_CONTEXT_RUNTIME_SOURCE=
COPILOT_CONTEXT_PLUGIN_ROOT=$ASSET_DIR/copilot-context-mode-source
COPILOT_CONTEXT_SOURCE_MARKER=$COPILOT_CONTEXT_PLUGIN_ROOT/.hard-eng-source
COPILOT_CONTEXT_PLUGIN_NAME=
COPILOT_CONTEXT_VERSION=
COPILOT_TRANSACTION_DIR=

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
  COPILOT_CONTEXT_RUNTIME_SOURCE="$ASSET_DIR/npm-runtime/node_modules/context-mode/$COPILOT_CONTEXT_PLUGIN_SUBDIR"
  COPILOT_CONTEXT_PLUGIN_SOURCE="$COPILOT_CONTEXT_PLUGIN_ROOT/context-mode"
}

copilot_context_source_status() {
  if [ -L "$COPILOT_CONTEXT_PLUGIN_ROOT" ] ||
    { [ -e "$COPILOT_CONTEXT_PLUGIN_ROOT" ] &&
      [ ! -d "$COPILOT_CONTEXT_PLUGIN_ROOT" ]; }; then
    setup_fail "managed Copilot plugin source root is not a regular directory: $COPILOT_CONTEXT_PLUGIN_ROOT"
    return 1
  fi
  if [ ! -e "$COPILOT_CONTEXT_PLUGIN_ROOT" ]; then
    return 3
  fi
  [ -f "$COPILOT_CONTEXT_SOURCE_MARKER" ] ||
    { setup_fail "managed Copilot plugin source root is missing its ownership marker"; return 1; }
  if [ -L "$COPILOT_CONTEXT_PLUGIN_SOURCE" ] ||
    { [ -e "$COPILOT_CONTEXT_PLUGIN_SOURCE" ] &&
      [ ! -d "$COPILOT_CONTEXT_PLUGIN_SOURCE" ]; }; then
    setup_fail "managed Copilot plugin source is not a regular directory: $COPILOT_CONTEXT_PLUGIN_SOURCE"
    return 1
  fi
  [ -d "$COPILOT_CONTEXT_PLUGIN_SOURCE" ] || return 3
  [ "$(cat "$COPILOT_CONTEXT_SOURCE_MARKER")" = "$COPILOT_CONTEXT_VERSION" ] ||
    return 5
}

sync_copilot_context_source() {
  local status temporary
  status=0
  copilot_context_source_status || status=$?
  case $status in
    0|3|5) ;;
    *) return "$status" ;;
  esac
  [ -d "$COPILOT_CONTEXT_RUNTIME_SOURCE" ] &&
    [ ! -L "$COPILOT_CONTEXT_RUNTIME_SOURCE" ] ||
    { setup_fail "pinned Copilot plugin source is missing from the npm runtime: $COPILOT_CONTEXT_RUNTIME_SOURCE"; return 1; }
  temporary=$(setup_scratch_dir copilot-source)
  mkdir -p "$COPILOT_CONTEXT_PLUGIN_ROOT"
  cp -R "$COPILOT_CONTEXT_RUNTIME_SOURCE" "$temporary/context-mode" ||
    { safe_remove_scratch_tree "$temporary"; setup_fail "could not stage Copilot plugin source"; return 1; }
  if [ -e "$COPILOT_CONTEXT_PLUGIN_SOURCE" ] &&
    ! mv "$COPILOT_CONTEXT_PLUGIN_SOURCE" "$temporary/previous"; then
    safe_remove_scratch_tree "$temporary"
    setup_fail "could not stage replacement Copilot plugin source"
    return 1
  fi
  if ! mv "$temporary/context-mode" "$COPILOT_CONTEXT_PLUGIN_SOURCE"; then
    [ -e "$temporary/previous" ] &&
      mv "$temporary/previous" "$COPILOT_CONTEXT_PLUGIN_SOURCE"
    safe_remove_scratch_tree "$temporary"
    setup_fail "could not activate Copilot plugin source"
    return 1
  fi
  safe_remove_scratch_tree "$temporary"
  atomic_write_text "$COPILOT_CONTEXT_SOURCE_MARKER" "$COPILOT_CONTEXT_VERSION"
}

copilot_context_state() {
  COPILOT_CONFIG_DIR="$COPILOT_DIR" \
    COPILOT_PLUGIN_SOURCE="$COPILOT_CONTEXT_PLUGIN_SOURCE" \
    COPILOT_LEGACY_PLUGIN_SOURCE="$COPILOT_CONTEXT_RUNTIME_SOURCE" \
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

copilot_transaction_capture() {
  COPILOT_TRANSACTION_DIR=$(setup_scratch_dir copilot-transaction) || return 1
  if python3 "$COPILOT_TRANSACTION_TOOL" capture "$COPILOT_TRANSACTION_DIR" \
    "$COPILOT_CONTEXT_PLUGIN_ROOT" \
    "$COPILOT_DIR/config.json" \
    "$COPILOT_DIR/installed-plugins" \
    "$COPILOT_DIR/settings.json" \
    "$COPILOT_DIR/hooks/hard-eng.json" \
    "$COPILOT_DIR/mcp-config.json"; then
    return 0
  fi
  safe_remove_scratch_tree "$COPILOT_TRANSACTION_DIR"
  COPILOT_TRANSACTION_DIR=
  return 1
}

copilot_transaction_mark() {
  python3 "$COPILOT_TRANSACTION_TOOL" mark "$COPILOT_TRANSACTION_DIR" "$@"
}

rollback_copilot_install() {
  if python3 "$COPILOT_TRANSACTION_TOOL" restore "$COPILOT_TRANSACTION_DIR"; then
    safe_remove_scratch_tree "$COPILOT_TRANSACTION_DIR"
    COPILOT_TRANSACTION_DIR=
    return 0
  fi
  setup_fail "Copilot rollback incomplete; inspect $COPILOT_DIR and $COPILOT_TRANSACTION_DIR"
}

commit_copilot_install() {
  safe_remove_scratch_tree "$COPILOT_TRANSACTION_DIR"
  COPILOT_TRANSACTION_DIR=
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

copilot_mcp_status() {
  local status
  status=0
  MEMORY_MCP_CONFIG="$COPILOT_DIR/mcp-config.json" \
    MEMORY_MCP_NAME="$MEMORY_MCP_NAME" \
    MEMORY_MCP_COMMAND="$MEMORY_MCP_COMMAND" \
    python3 "$MCP_REGISTRATION_TOOL" || status=$?
  case $status in
    0|3) return "$status" ;;
    *) return 1 ;;
  esac
}

converge_copilot_mcp() {
  local status
  status=0
  copilot_mcp_status || status=$?
  case $status in
    0) return ;;
    3) ;;
    *) return "$status" ;;
  esac
  COPILOT_HOME="$COPILOT_DIR" bounded_setup_run 60 copilot mcp add "$MEMORY_MCP_NAME" -- "$MEMORY_MCP_COMMAND" ||
    { setup_fail "Copilot MCP registration failed"; return 1; }
  copilot_mcp_status
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
  guard_hook_available || return 1
  load_copilot_context_contract
  copilot_transaction_capture || return 1
  if ! sync_copilot_context_source ||
    ! copilot_transaction_mark "$COPILOT_CONTEXT_PLUGIN_ROOT"; then
    rollback_copilot_install
    return 1
  fi
  if ! preflight_copilot_context; then
    rollback_copilot_install
    return 1
  fi
  if ! converge_copilot_context; then
    if copilot_context_state; then
      copilot_transaction_mark \
        "$COPILOT_DIR/config.json" \
        "$COPILOT_DIR/installed-plugins" \
        "$COPILOT_DIR/settings.json" || true
    fi
    rollback_copilot_install
    return 1
  fi
  copilot_transaction_mark \
    "$COPILOT_DIR/config.json" \
    "$COPILOT_DIR/installed-plugins" \
    "$COPILOT_DIR/settings.json" ||
    { rollback_copilot_install; return 1; }
  if ! converge_copilot_mcp; then
    copilot_transaction_mark "$COPILOT_DIR/mcp-config.json" || true
    rollback_copilot_install
    return 1
  fi
  copilot_transaction_mark "$COPILOT_DIR/mcp-config.json" ||
    { rollback_copilot_install; return 1; }
  copilot_settings_tool install ||
    { rollback_copilot_install; return 1; }
  copilot_transaction_mark "$COPILOT_DIR/settings.json" ||
    { rollback_copilot_install; return 1; }
  guard_hook_tool copilot install ||
    { rollback_copilot_install; return 1; }
  copilot_transaction_mark "$COPILOT_DIR/hooks/hard-eng.json" ||
    { rollback_copilot_install; return 1; }
  copilot_context_source_status &&
    copilot_context_state &&
    copilot_mcp_status &&
    copilot_settings_tool check &&
    guard_hook_tool copilot check ||
    { rollback_copilot_install; return 1; }
  copilot_profile_tool install ||
    { rollback_copilot_install; return 1; }
  commit_copilot_install
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
  guard_hook_available || return 1
  load_copilot_context_contract
  copilot_context_source_status || return 1
  copilot_cli_available || return 1
  copilot_context_state || return 1
  copilot_mcp_status || return 1
  copilot_settings_tool check || return 1
  guard_hook_tool copilot check || return 1
  copilot_profile_tool check
}

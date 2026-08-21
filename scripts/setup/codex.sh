#!/bin/bash

CODEX_DIR=$HOME/.codex
CANONICAL_AGENTS=$HOME/.agents/AGENTS.md
CODEX_AGENTS=$CODEX_DIR/AGENTS.md
CODEX_STATE=$ROOT/scripts/setup/codex-state.py
CODEX_CONTEXT_VERSION=
CODEX_CONTEXT_PLUGIN_ROOT=

INSTRUCTION_LINK_CREATED=no
MARKETPLACE_CREATED=no
MARKETPLACE_CHANGED=no
MARKETPLACE_REPLACED=no
PLUGIN_CREATED=no
PLUGIN_WAS_PRESENT=no
CODEX_MCP_ADDED=no
PREVIOUS_MARKETPLACE_COMMIT=

load_context_contract() {
  CONTEXT_MARKETPLACE_REPO=$(manifest get codex.context_mode.marketplace_repo)
  CONTEXT_MARKETPLACE_NAME=$(manifest get codex.context_mode.marketplace_name)
  CONTEXT_MARKETPLACE_REF=$(manifest get codex.context_mode.marketplace_ref)
  CONTEXT_PLUGIN_ID=$(manifest get codex.context_mode.plugin_id)
  CODEX_CONTEXT_VERSION=$(manifest get codex.context_mode.version)
  CODEX_CONTEXT_PLUGIN_ROOT=$CODEX_DIR/plugins/cache/$CONTEXT_MARKETPLACE_NAME/$CONTEXT_MARKETPLACE_NAME/$CODEX_CONTEXT_VERSION
}

codex_context_runtime_patch() {
  local operation
  operation=$1
  [ -d "$CODEX_CONTEXT_PLUGIN_ROOT" ] && [ ! -L "$CODEX_CONTEXT_PLUGIN_ROOT" ] ||
    { setup_fail "Codex Context Mode plugin cache is missing: $CODEX_CONTEXT_PLUGIN_ROOT"; return 1; }
  context_mode_runtime_patch "$operation" "$CODEX_CONTEXT_PLUGIN_ROOT" ||
    { setup_fail "Codex Context Mode runtime overlay failed: $CODEX_CONTEXT_PLUGIN_ROOT"; return 1; }
}

canonical_instructions_available() {
  [ -f "$CANONICAL_AGENTS" ] &&
    [ ! -L "$CANONICAL_AGENTS" ] &&
    [ "$CANONICAL_AGENTS" -ef "$ROOT/AGENTS.md" ] ||
    setup_fail "canonical instructions must be the repository file: $CANONICAL_AGENTS"
}

instruction_link_status() {
  canonical_instructions_available || return 1
  if [ -L "$CODEX_AGENTS" ]; then
    [ "$(readlink "$CODEX_AGENTS")" = "$CANONICAL_AGENTS" ] ||
      setup_fail "Codex AGENTS.md symlink has another owner: $CODEX_AGENTS"
  elif [ -e "$CODEX_AGENTS" ]; then
    setup_fail "Codex AGENTS.md conflicts with canonical symlink: $CODEX_AGENTS"
  else
    return 3
  fi
}

install_instruction_link() {
  local status
  status=0
  instruction_link_status || status=$?
  case $status in
    0) return ;;
    3)
      if [ -L "$CODEX_DIR" ] || { [ -e "$CODEX_DIR" ] && [ ! -d "$CODEX_DIR" ]; }; then
        setup_fail "Codex home is not a directory: $CODEX_DIR"
        return 1
      fi
      mkdir -p "$CODEX_DIR"
      ln -s "$CANONICAL_AGENTS" "$CODEX_AGENTS" ||
        { setup_fail "could not create canonical Codex instruction link"; return 1; }
      INSTRUCTION_LINK_CREATED=yes
      ;;
    *) return "$status" ;;
  esac
}

codex_state() {
  local command_name temporary mirror status
  command_name=$1
  temporary=$(setup_scratch_dir codex-state)
  mirror=$temporary/codex
  mkdir -p "$temporary/home" "$mirror/.tmp" "$mirror/plugins"
  if [ -f "$CODEX_DIR/config.toml" ] && [ ! -L "$CODEX_DIR/config.toml" ]; then
    cp -p "$CODEX_DIR/config.toml" "$mirror/config.toml"
  fi
  if [ -d "$CODEX_DIR/.tmp/marketplaces" ]; then
    ln -s "$CODEX_DIR/.tmp/marketplaces" "$mirror/.tmp/marketplaces"
  fi
  if [ -d "$CODEX_DIR/plugins/cache" ]; then
    ln -s "$CODEX_DIR/plugins/cache" "$mirror/plugins/cache"
  fi
  status=0
  HOME=$temporary/home CODEX_HOME=$mirror \
    MEMORY_MCP_COMMAND="$MEMORY_MCP_COMMAND" \
    python3 "$CODEX_STATE" "$command_name" || status=$?
  safe_remove_scratch_tree "$temporary"
  return "$status"
}

preflight_codex() {
  local status
  status=0
  instruction_link_status || status=$?
  case $status in 0|3) ;; *) return "$status" ;; esac
  status=0
  codex_state marketplace >/dev/null || status=$?
  case $status in 0|3|5) ;; *) return "$status" ;; esac
  status=0
  codex_state plugin >/dev/null || status=$?
  case $status in 0|3|5) ;; *) return "$status" ;; esac
  status=0
  codex_state mcp >/dev/null || status=$?
  case $status in 0|3) ;; *) return "$status" ;; esac
}

converge_context_marketplace() {
  local status was_missing
  status=0
  was_missing=no
  codex_state marketplace >/dev/null || status=$?
  case $status in
    0) return ;;
    3) was_missing=yes ;;
    5)
      status=0
      codex_state plugin >/dev/null || status=$?
      case $status in
        0|5) PLUGIN_WAS_PRESENT=yes ;;
        3) ;;
        *) return "$status" ;;
      esac
      PREVIOUS_MARKETPLACE_COMMIT=$(codex_state marketplace-head) || return
      codex plugin marketplace remove "$CONTEXT_MARKETPLACE_NAME" \
        --json >/dev/null || return
      MARKETPLACE_REPLACED=yes
      ;;
    *) return "$status" ;;
  esac
  codex plugin marketplace add "$CONTEXT_MARKETPLACE_REPO" \
    --ref "$CONTEXT_MARKETPLACE_REF" --json >/dev/null || return
  [ "$was_missing" = no ] || MARKETPLACE_CREATED=yes
  MARKETPLACE_CHANGED=yes
  codex_state marketplace >/dev/null
}

converge_context_plugin() {
  local status was_missing
  status=0
  was_missing=no
  codex_state plugin >/dev/null || status=$?
  case $status in
    0) [ "$MARKETPLACE_CHANGED" = yes ] || return 0 ;;
    3) was_missing=yes ;;
    5) ;;
    *) return "$status" ;;
  esac
  codex plugin add "$CONTEXT_PLUGIN_ID" --json >/dev/null || return
  [ "$was_missing" = no ] || PLUGIN_CREATED=yes
  codex_state plugin >/dev/null
}

converge_codex_mcp() {
  local status
  status=0
  codex_state mcp >/dev/null || status=$?
  case $status in
    0) return ;;
    3) ;;
    *) return "$status" ;;
  esac
  bounded_setup_run 60 codex mcp add "$MEMORY_MCP_NAME" -- "$MEMORY_MCP_COMMAND" || return
  CODEX_MCP_ADDED=yes
  codex_state mcp >/dev/null
}

rollback_codex_install() {
  local failed
  failed=no
  if [ "$CODEX_MCP_ADDED" = yes ]; then
    bounded_setup_run 60 codex mcp remove "$MEMORY_MCP_NAME" >/dev/null 2>&1 ||
      failed=yes
  fi
  if [ "$PLUGIN_CREATED" = yes ]; then
    codex plugin remove "$CONTEXT_PLUGIN_ID" --json >/dev/null 2>&1 ||
      failed=yes
  fi
  if [ "$MARKETPLACE_CREATED" = yes ] ||
    { [ "$MARKETPLACE_REPLACED" = yes ] &&
      [ "$MARKETPLACE_CHANGED" = yes ]; }; then
    codex plugin marketplace remove "$CONTEXT_MARKETPLACE_NAME" \
      --json >/dev/null 2>&1 || failed=yes
  fi
  if [ "$MARKETPLACE_REPLACED" = yes ]; then
    if codex plugin marketplace add "$CONTEXT_MARKETPLACE_REPO" \
      --ref "$PREVIOUS_MARKETPLACE_COMMIT" --json >/dev/null 2>&1; then
      if [ "$PLUGIN_WAS_PRESENT" = yes ]; then
        codex plugin add "$CONTEXT_PLUGIN_ID" --json >/dev/null 2>&1 ||
          failed=yes
      fi
    else
      failed=yes
    fi
  fi
  if [ "$INSTRUCTION_LINK_CREATED" = yes ] &&
    [ -L "$CODEX_AGENTS" ] &&
    [ "$(readlink "$CODEX_AGENTS")" = "$CANONICAL_AGENTS" ]; then
    rm -f -- "$CODEX_AGENTS"
  fi
  [ "$failed" = no ] ||
    setup_fail "Codex rollback incomplete; inspect plugin state"
}

install_codex_integration() {
  load_context_contract
  guard_hook_available || return 1
  preflight_codex
  install_instruction_link
  if ! converge_context_marketplace ||
    ! converge_context_plugin ||
    ! converge_codex_mcp ||
    ! codex_context_runtime_patch apply ||
    ! guard_hook_tool codex install ||
    ! check_codex_integration; then
    if rollback_codex_install; then
      setup_fail "Codex Context Mode plugin convergence failed"
    else
      setup_fail "Codex Context Mode plugin convergence and rollback failed"
    fi
    return 1
  fi
}

check_codex_integration() {
  load_context_contract
  guard_hook_available || return 1
  instruction_link_status || return 1
  codex_state check >/dev/null || return 1
  codex_state mcp >/dev/null || return 1
  codex_context_runtime_patch check || return 1
  guard_hook_tool codex check
}

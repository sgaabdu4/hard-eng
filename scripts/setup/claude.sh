#!/bin/bash

CLAUDE_DIR=$HOME/.claude
CLAUDE_MEMORY=$CLAUDE_DIR/CLAUDE.md
CLAUDE_MEMORY_CONTENT='@~/.agents/AGENTS.md'
CLAUDE_SKILLS=$CLAUDE_DIR/skills
CANONICAL_SKILLS=$HOME/.agents/skills
CLAUDE_OUTPUT_STYLES=$CLAUDE_DIR/output-styles
CANONICAL_OUTPUT_STYLES=$HOME/.agents/output-styles
CLAUDE_SETTINGS_FILE=$CLAUDE_DIR/settings.json
CLAUDE_SETTINGS_TOOL=$ROOT/scripts/setup/claude-settings.py
CLAUDE_LEGACY_RG_GUARD=$CLAUDE_DIR/hooks/rg-guard.py

CLAUDE_MEMORY_CREATED=no
CLAUDE_SKILLS_LINK_CREATED=no
CLAUDE_OUTPUT_STYLES_LINK_CREATED=no
CLAUDE_TRANSACTION_DIR=
CLAUDE_SETTINGS_JOURNAL=
CLAUDE_SETTINGS_CHANGED=no
CLAUDE_LEGACY_RG_GUARD_REMOVED=no
CLAUDE_LEGACY_RG_GUARD_TARGET=

claude_canonical_available() {
  [ -f "$CANONICAL_AGENTS" ] && [ "$CANONICAL_AGENTS" -ef "$ROOT/AGENTS.md" ] ||
    setup_fail "canonical instructions must be the repository file: $CANONICAL_AGENTS"
  [ -d "$CANONICAL_SKILLS" ] && [ "$CANONICAL_SKILLS" -ef "$ROOT/skills" ] ||
    setup_fail "canonical skills must be the repository directory: $CANONICAL_SKILLS"
  [ -d "$CANONICAL_OUTPUT_STYLES" ] &&
    [ "$CANONICAL_OUTPUT_STYLES" -ef "$ROOT/output-styles" ] ||
    setup_fail "canonical output styles must be the repository directory: $CANONICAL_OUTPUT_STYLES"
  guard_hook_available
}

claude_memory_status() {
  claude_canonical_available || return 1
  if [ -L "$CLAUDE_MEMORY" ]; then
    setup_fail "Claude memory stub must be a regular file: $CLAUDE_MEMORY"
  elif [ -f "$CLAUDE_MEMORY" ]; then
    [ "$(cat "$CLAUDE_MEMORY")" = "$CLAUDE_MEMORY_CONTENT" ] ||
      setup_fail "Claude memory stub has another owner: $CLAUDE_MEMORY"
  elif [ -e "$CLAUDE_MEMORY" ]; then
    setup_fail "Claude memory stub conflicts with existing state: $CLAUDE_MEMORY"
  else
    return 3
  fi
}

claude_skills_status() {
  claude_canonical_available || return 1
  if [ -L "$CLAUDE_SKILLS" ]; then
    [ "$(readlink "$CLAUDE_SKILLS")" = "$CANONICAL_SKILLS" ] ||
      setup_fail "Claude skills symlink has another owner: $CLAUDE_SKILLS"
  elif [ -e "$CLAUDE_SKILLS" ]; then
    setup_fail "Claude skills path conflicts with canonical symlink: $CLAUDE_SKILLS"
  else
    return 3
  fi
}

claude_output_styles_status() {
  claude_canonical_available || return 1
  if [ -L "$CLAUDE_OUTPUT_STYLES" ]; then
    [ "$(readlink "$CLAUDE_OUTPUT_STYLES")" = "$CANONICAL_OUTPUT_STYLES" ] ||
      setup_fail "Claude output styles symlink has another owner: $CLAUDE_OUTPUT_STYLES"
  elif [ -e "$CLAUDE_OUTPUT_STYLES" ]; then
    setup_fail "Claude output styles path conflicts with canonical symlink: $CLAUDE_OUTPUT_STYLES"
  else
    return 3
  fi
}

claude_settings_tool() {
  CLAUDE_SETTINGS="$CLAUDE_SETTINGS_FILE" \
    HARD_ENG_HOOK_COMMAND="$GUARD_HOOK_COMMAND" \
    CONTEXT_MARKETPLACE_NAME="$CONTEXT_MARKETPLACE_NAME" \
    CONTEXT_MARKETPLACE_REPO="$CONTEXT_MARKETPLACE_REPO" \
    CONTEXT_MARKETPLACE_REF="$CONTEXT_MARKETPLACE_REF" \
    CONTEXT_PLUGIN_ID="$CONTEXT_PLUGIN_ID" \
    CLAUDE_SETTINGS_JOURNAL="$CLAUDE_SETTINGS_JOURNAL" \
    python3 "$CLAUDE_SETTINGS_TOOL" "$1"
}

remove_legacy_claude_rg_guard() {
  [ -L "$CLAUDE_LEGACY_RG_GUARD" ] || return 0
  case "$(readlink "$CLAUDE_LEGACY_RG_GUARD")" in
    */claude-rg-guard.py)
      CLAUDE_LEGACY_RG_GUARD_TARGET=$(readlink "$CLAUDE_LEGACY_RG_GUARD")
      rm -f -- "$CLAUDE_LEGACY_RG_GUARD" || return 1
      CLAUDE_LEGACY_RG_GUARD_REMOVED=yes
      ;;
  esac
  rmdir "$CLAUDE_DIR/hooks" 2>/dev/null || true
}

rollback_claude_install() {
  local failed
  failed=no
  if [ "$CLAUDE_SETTINGS_CHANGED" = yes ]; then
    claude_settings_tool rollback || failed=yes
  fi
  if [ "$CLAUDE_OUTPUT_STYLES_LINK_CREATED" = yes ] &&
    [ -L "$CLAUDE_OUTPUT_STYLES" ] &&
    [ "$(readlink "$CLAUDE_OUTPUT_STYLES")" = "$CANONICAL_OUTPUT_STYLES" ]; then
    rm -f -- "$CLAUDE_OUTPUT_STYLES"
  fi
  if [ "$CLAUDE_SKILLS_LINK_CREATED" = yes ] &&
    [ -L "$CLAUDE_SKILLS" ] &&
    [ "$(readlink "$CLAUDE_SKILLS")" = "$CANONICAL_SKILLS" ]; then
    rm -f -- "$CLAUDE_SKILLS"
  fi
  if [ "$CLAUDE_MEMORY_CREATED" = yes ] &&
    [ -f "$CLAUDE_MEMORY" ] &&
    [ "$(cat "$CLAUDE_MEMORY")" = "$CLAUDE_MEMORY_CONTENT" ]; then
    rm -f -- "$CLAUDE_MEMORY"
  fi
  if [ "$CLAUDE_LEGACY_RG_GUARD_REMOVED" = yes ]; then
    if [ -e "$CLAUDE_LEGACY_RG_GUARD" ] || [ -L "$CLAUDE_LEGACY_RG_GUARD" ]; then
      failed=yes
    else
      mkdir -p "$(dirname "$CLAUDE_LEGACY_RG_GUARD")" &&
        ln -s "$CLAUDE_LEGACY_RG_GUARD_TARGET" "$CLAUDE_LEGACY_RG_GUARD" ||
        failed=yes
    fi
  fi
  if [ "$failed" = no ]; then
    [ -z "$CLAUDE_TRANSACTION_DIR" ] ||
      safe_remove_scratch_tree "$CLAUDE_TRANSACTION_DIR"
    CLAUDE_TRANSACTION_DIR=
    CLAUDE_SETTINGS_JOURNAL=
    return 0
  fi
  setup_fail "Claude rollback incomplete; inspect $CLAUDE_DIR and $CLAUDE_TRANSACTION_DIR"
}

install_claude_integration() {
  local status
  load_context_contract
  if [ -L "$CLAUDE_DIR" ] || { [ -e "$CLAUDE_DIR" ] && [ ! -d "$CLAUDE_DIR" ]; }; then
    setup_fail "Claude home is not a directory: $CLAUDE_DIR"
    return 1
  fi
  CLAUDE_TRANSACTION_DIR=$(setup_scratch_dir claude-transaction) || return 1
  CLAUDE_SETTINGS_JOURNAL=$CLAUDE_TRANSACTION_DIR/settings.json
  status=0
  claude_memory_status || status=$?
  case $status in
    0) ;;
    3)
      mkdir -p "$CLAUDE_DIR" ||
        { rollback_claude_install; return 1; }
      printf '%s\n' "$CLAUDE_MEMORY_CONTENT" > "$CLAUDE_MEMORY" ||
        { rollback_claude_install; setup_fail "could not create Claude memory stub"; return 1; }
      CLAUDE_MEMORY_CREATED=yes
      ;;
    *) rollback_claude_install; return "$status" ;;
  esac
  status=0
  claude_skills_status || status=$?
  case $status in
    0) ;;
    3)
      ln -s "$CANONICAL_SKILLS" "$CLAUDE_SKILLS" ||
        { rollback_claude_install; setup_fail "could not create canonical Claude skills link"; return 1; }
      CLAUDE_SKILLS_LINK_CREATED=yes
      ;;
    *) rollback_claude_install; return "$status" ;;
  esac
  status=0
  claude_output_styles_status || status=$?
  case $status in
    0) ;;
    3)
      ln -s "$CANONICAL_OUTPUT_STYLES" "$CLAUDE_OUTPUT_STYLES" ||
        { rollback_claude_install; setup_fail "could not create canonical Claude output styles link"; return 1; }
      CLAUDE_OUTPUT_STYLES_LINK_CREATED=yes
      ;;
    *) rollback_claude_install; return "$status" ;;
  esac
  if ! remove_legacy_claude_rg_guard; then
    rollback_claude_install
    setup_fail "could not retire the legacy Claude rg guard"
    return 1
  fi
  if claude_settings_tool install; then
    [ ! -f "$CLAUDE_SETTINGS_JOURNAL" ] || CLAUDE_SETTINGS_CHANGED=yes
  else
    rollback_claude_install
    setup_fail "Claude integration convergence failed"
    return 1
  fi
  if ! check_claude_integration; then
    if rollback_claude_install; then
      setup_fail "Claude integration convergence failed"
    else
      setup_fail "Claude integration convergence and rollback failed"
    fi
    [ -z "$CLAUDE_TRANSACTION_DIR" ] ||
      safe_remove_scratch_tree "$CLAUDE_TRANSACTION_DIR"
    return 1
  fi
  [ -z "$CLAUDE_TRANSACTION_DIR" ] ||
    safe_remove_scratch_tree "$CLAUDE_TRANSACTION_DIR"
  CLAUDE_TRANSACTION_DIR=
  CLAUDE_SETTINGS_JOURNAL=
}

check_claude_integration() {
  load_context_contract
  claude_memory_status
  claude_skills_status
  claude_output_styles_status
  claude_settings_tool check
}

#!/bin/bash

CLAUDE_DIR=$HOME/.claude
CLAUDE_MEMORY=$CLAUDE_DIR/CLAUDE.md
CLAUDE_MEMORY_CONTENT='@~/.agents/AGENTS.md'
CLAUDE_SKILLS=$CLAUDE_DIR/skills
CANONICAL_SKILLS=$HOME/.agents/skills
CLAUDE_SETTINGS_FILE=$CLAUDE_DIR/settings.json
CLAUDE_SETTINGS_TOOL=$ROOT/scripts/setup/claude-settings.py
CLAUDE_HOOKS_DIR=$CLAUDE_DIR/hooks
CLAUDE_RG_GUARD=$CLAUDE_HOOKS_DIR/rg-guard.py
CANONICAL_RG_GUARD=$ROOT/scripts/setup/claude-rg-guard.py

CLAUDE_MEMORY_CREATED=no
CLAUDE_SKILLS_LINK_CREATED=no
CLAUDE_HOOKS_DIR_CREATED=no
CLAUDE_RG_GUARD_LINK_CREATED=no
CLAUDE_SETTINGS_BACKUP_DIR=
CLAUDE_SETTINGS_WAS_PRESENT=no

claude_canonical_available() {
  [ -f "$CANONICAL_AGENTS" ] && [ "$CANONICAL_AGENTS" -ef "$ROOT/AGENTS.md" ] ||
    setup_fail "canonical instructions must be the repository file: $CANONICAL_AGENTS"
  [ -d "$CANONICAL_SKILLS" ] && [ "$CANONICAL_SKILLS" -ef "$ROOT/skills" ] ||
    setup_fail "canonical skills must be the repository directory: $CANONICAL_SKILLS"
  [ -f "$CANONICAL_RG_GUARD" ] && [ ! -L "$CANONICAL_RG_GUARD" ] &&
    [ -x "$CANONICAL_RG_GUARD" ] ||
    setup_fail "canonical Claude rg guard must be an executable repository file: $CANONICAL_RG_GUARD"
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

claude_rg_guard_status() {
  claude_canonical_available || return 1
  if [ -L "$CLAUDE_HOOKS_DIR" ] ||
    { [ -e "$CLAUDE_HOOKS_DIR" ] && [ ! -d "$CLAUDE_HOOKS_DIR" ]; }; then
    setup_fail "Claude hooks path is not a regular directory: $CLAUDE_HOOKS_DIR"
    return 1
  fi
  if [ -L "$CLAUDE_RG_GUARD" ]; then
    [ "$(readlink "$CLAUDE_RG_GUARD")" = "$CANONICAL_RG_GUARD" ] ||
      setup_fail "Claude rg guard symlink has another owner: $CLAUDE_RG_GUARD"
  elif [ -e "$CLAUDE_RG_GUARD" ]; then
    setup_fail "Claude rg guard conflicts with existing state: $CLAUDE_RG_GUARD"
  else
    return 3
  fi
}

claude_settings_tool() {
  CLAUDE_SETTINGS="$CLAUDE_SETTINGS_FILE" \
    CLAUDE_RG_GUARD_COMMAND="\"$CLAUDE_RG_GUARD\"" \
    CONTEXT_MARKETPLACE_NAME="$CONTEXT_MARKETPLACE_NAME" \
    CONTEXT_MARKETPLACE_REPO="$CONTEXT_MARKETPLACE_REPO" \
    CONTEXT_MARKETPLACE_REF="$CONTEXT_MARKETPLACE_REF" \
    CONTEXT_PLUGIN_ID="$CONTEXT_PLUGIN_ID" \
    python3 "$CLAUDE_SETTINGS_TOOL" "$1"
}

install_claude_rg_guard() {
  local status
  status=0
  claude_rg_guard_status || status=$?
  case $status in
    0) return ;;
    3)
      if [ ! -d "$CLAUDE_HOOKS_DIR" ]; then
        mkdir -p "$CLAUDE_HOOKS_DIR"
        CLAUDE_HOOKS_DIR_CREATED=yes
      fi
      ln -s "$CANONICAL_RG_GUARD" "$CLAUDE_RG_GUARD" ||
        { setup_fail "could not create Claude rg guard link"; return 1; }
      CLAUDE_RG_GUARD_LINK_CREATED=yes
      ;;
    *) return "$status" ;;
  esac
  claude_rg_guard_status
}

rollback_claude_install() {
  local failed
  failed=no
  if [ "$CLAUDE_SETTINGS_WAS_PRESENT" = yes ] &&
    [ -n "$CLAUDE_SETTINGS_BACKUP_DIR" ] &&
    [ -f "$CLAUDE_SETTINGS_BACKUP_DIR/settings.json" ]; then
    cp -p "$CLAUDE_SETTINGS_BACKUP_DIR/settings.json" "$CLAUDE_SETTINGS_FILE" ||
      failed=yes
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
  if [ "$CLAUDE_RG_GUARD_LINK_CREATED" = yes ] &&
    [ -L "$CLAUDE_RG_GUARD" ] &&
    [ "$(readlink "$CLAUDE_RG_GUARD")" = "$CANONICAL_RG_GUARD" ]; then
    rm -f -- "$CLAUDE_RG_GUARD"
  fi
  if [ "$CLAUDE_HOOKS_DIR_CREATED" = yes ]; then
    rmdir "$CLAUDE_HOOKS_DIR" 2>/dev/null || true
  fi
  [ "$failed" = no ] ||
    setup_fail "Claude rollback incomplete; inspect $CLAUDE_DIR state"
}

install_claude_integration() {
  local status
  load_context_contract
  if [ -L "$CLAUDE_DIR" ] || { [ -e "$CLAUDE_DIR" ] && [ ! -d "$CLAUDE_DIR" ]; }; then
    setup_fail "Claude home is not a directory: $CLAUDE_DIR"
    return 1
  fi
  status=0
  claude_memory_status || status=$?
  case $status in
    0) ;;
    3)
      mkdir -p "$CLAUDE_DIR"
      printf '%s\n' "$CLAUDE_MEMORY_CONTENT" > "$CLAUDE_MEMORY" ||
        { setup_fail "could not create Claude memory stub"; return 1; }
      CLAUDE_MEMORY_CREATED=yes
      ;;
    *) return "$status" ;;
  esac
  status=0
  claude_skills_status || status=$?
  case $status in
    0) ;;
    3)
      ln -s "$CANONICAL_SKILLS" "$CLAUDE_SKILLS" ||
        { setup_fail "could not create canonical Claude skills link"; return 1; }
      CLAUDE_SKILLS_LINK_CREATED=yes
      ;;
    *) return "$status" ;;
  esac
  if ! install_claude_rg_guard; then
    rollback_claude_install
    setup_fail "Claude rg guard convergence failed"
    return 1
  fi
  if [ -f "$CLAUDE_SETTINGS_FILE" ]; then
    CLAUDE_SETTINGS_WAS_PRESENT=yes
    CLAUDE_SETTINGS_BACKUP_DIR=$(setup_scratch_dir claude-settings)
    cp -p "$CLAUDE_SETTINGS_FILE" "$CLAUDE_SETTINGS_BACKUP_DIR/settings.json"
  fi
  if ! claude_settings_tool install || ! check_claude_integration; then
    if rollback_claude_install; then
      setup_fail "Claude integration convergence failed"
    else
      setup_fail "Claude integration convergence and rollback failed"
    fi
    [ -z "$CLAUDE_SETTINGS_BACKUP_DIR" ] ||
      safe_remove_scratch_tree "$CLAUDE_SETTINGS_BACKUP_DIR"
    return 1
  fi
  [ -z "$CLAUDE_SETTINGS_BACKUP_DIR" ] ||
    safe_remove_scratch_tree "$CLAUDE_SETTINGS_BACKUP_DIR"
}

check_claude_integration() {
  load_context_contract
  claude_memory_status
  claude_skills_status
  claude_rg_guard_status
  claude_settings_tool check
}

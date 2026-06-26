#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DRY_RUN=0
YES="${HARD_ENG_UNINSTALL_YES:-0}"

usage() {
  cat <<'EOF'
Usage:
  scripts/uninstall.sh --yes [--dry-run]

Removes Hard Eng-managed links, skills, hooks, cron blocks, shell PATH block,
watchdog LaunchAgent, managed Codex bin files, and Hard Eng caches.
Shared prerequisites such as Homebrew, Git, Node, Dart, Flutter, Treehouse, and
no-mistakes are not removed because they may be used outside this repo.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --yes) YES=1 ;;
    --dry-run) DRY_RUN=1 ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done

if [[ "$YES" != "1" ]]; then
  echo "Refusing uninstall without --yes." >&2
  exit 2
fi

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    printf 'dry-run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

remove_if_symlink_to() {
  local target="$1"
  local prefix="$2"
  [[ -L "$target" ]] || return 0
  case "$(readlink "$target")" in
    "$prefix"|"$prefix"/*) run rm -f "$target" ;;
  esac
}

remove_exact_stub() {
  local target="$1"
  [[ -f "$target" ]] || return 0
  if [[ "$(cat "$target")" == "@AGENTS.md" ]]; then
    run rm -f "$target"
  fi
}

remove_managed_file() {
  local target="$1"
  [[ -f "$target" ]] || return 0
  if grep -q 'Managed by hard-eng installer' "$target" 2>/dev/null; then
    run rm -f "$target"
  fi
}

remove_shell_block() {
  local target="${HARD_ENG_SHELL_ENV_FILE:-$HOME/.zshenv}"
  local tmp
  [[ -f "$target" ]] || return 0
  tmp="${target}.hard-eng-uninstall.$$"
  awk \
    -v begin="# BEGIN hard-eng bootstrap path" \
    -v end="# END hard-eng bootstrap path" '
      $0 == begin { skip = 1; next }
      $0 == end { skip = 0; next }
      !skip { print }
    ' "$target" >"$tmp"
  if [[ "$DRY_RUN" == "1" ]]; then
    run mv "$tmp" "$target"
    rm -f "$tmp"
  else
    mv "$tmp" "$target"
  fi
}

remove_cron_blocks() {
  command -v crontab >/dev/null 2>&1 || return 0
  local current tmp
  current="$(crontab -l 2>/dev/null || true)"
  tmp="$(mktemp)"
  printf '%s\n' "$current" | awk \
    -v begin="# BEGIN hard-eng auto-sync" \
    -v end="# END hard-eng auto-sync" \
    -v stack_begin="# BEGIN hard-eng codex-stack-update" \
    -v stack_end="# END hard-eng codex-stack-update" '
      $0 == begin || $0 == stack_begin { skip = 1; next }
      $0 == end || $0 == stack_end { skip = 0; next }
      !skip { print }
    ' >"$tmp"
  run crontab "$tmp"
  rm -f "$tmp"
}

remove_launch_agent() {
  [[ "$(uname -s)" == "Darwin" ]] || return 0
  local label plist legacy_person legacy_stack
  legacy_person="$(printf '\141\142\151\144')"
  legacy_stack="${legacy_person}-agents"
  if command -v launchctl >/dev/null 2>&1; then
    for label in \
      "dev.hard-eng.codex-watchdog" \
      "dev.${legacy_stack}.codex-watchdog" \
      "com.${legacy_person}.codex-watchdog"; do
      run launchctl bootout "gui/$(id -u)/$label" >/dev/null 2>&1 || true
      run launchctl disable "gui/$(id -u)/$label" >/dev/null 2>&1 || true
    done
  fi
  for label in \
    "dev.hard-eng.codex-watchdog" \
    "dev.${legacy_stack}.codex-watchdog" \
    "com.${legacy_person}.codex-watchdog"; do
    plist="$HOME/Library/LaunchAgents/${label}.plist"
    [[ -e "$plist" ]] && run rm -f "$plist"
  done
}

remove_hooks() {
  git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1 || return 0
  local hooks_dir hook
  hooks_dir="$(git -C "$ROOT" rev-parse --git-path hooks)"
  [[ "$hooks_dir" == /* ]] || hooks_dir="$ROOT/$hooks_dir"
  for hook in post-merge post-rewrite pre-commit pre-push; do
    remove_managed_file "$hooks_dir/$hook"
  done
}

for target in \
  "$HOME/.codex/AGENTS.md" "$HOME/.codex/mcp-config.json" "$HOME/.codex/hooks.json" \
  "$HOME/.claude/AGENTS.md" "$HOME/.copilot/AGENTS.md" "$HOME/.pi/AGENTS.md" "$HOME/.pi/agent/AGENTS.md"; do
  remove_if_symlink_to "$target" "$ROOT"
done
remove_exact_stub "$HOME/.claude/CLAUDE.md"

node "$ROOT/scripts/manage-skills.mjs" remove

for name in codex-watchdog codex-health codex-context-mode-health codex-cleanup codex-update-stack; do
  remove_managed_file "$HOME/.codex/bin/$name"
done

remove_hooks
remove_launch_agent
remove_cron_blocks
remove_shell_block
run rm -f "${HARD_ENG_SKILL_CONFIG:-$HOME/.config/hard-eng/skills.json}"
run rm -rf "$HOME/.cache/hard-eng"

echo "Hard Eng uninstall complete."

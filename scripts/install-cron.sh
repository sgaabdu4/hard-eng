#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEDULE="${HARD_ENG_CRON_SCHEDULE:-*/15 * * * *}"
CODEX_STACK_SCHEDULE="${HARD_ENG_CODEX_STACK_CRON_SCHEDULE:-17 5 * * 1}"
PATH_VALUE="${HARD_ENG_CRON_PATH:-/opt/homebrew/bin:/usr/local/bin:$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/flutter/bin:$HOME/.pub-cache/bin:/usr/bin:/bin:/usr/sbin:/sbin}"
LOG="$ROOT/.git/auto-sync.log"
CODEX_STACK_LOG="$HOME/.codex/logs/codex-update-stack.log"
BEGIN_MARK="# BEGIN hard-eng auto-sync"
END_MARK="# END hard-eng auto-sync"
CODEX_STACK_BEGIN_MARK="# BEGIN hard-eng codex-stack-update"
CODEX_STACK_END_MARK="# END hard-eng codex-stack-update"
JOB="$SCHEDULE cd \"$ROOT\" && PATH=\"$PATH_VALUE\" \"$ROOT/scripts/auto-sync.sh\" >> \"$LOG\" 2>&1"
CODEX_STACK_JOB="$CODEX_STACK_SCHEDULE mkdir -p \"$HOME/.codex/logs\" && cd \"$ROOT\" && PATH=\"$PATH_VALUE\" \"$ROOT/codex/bin/codex-update-stack\" >> \"$CODEX_STACK_LOG\" 2>&1"
TMP_CRON="$(mktemp)"
trap 'rm -f "$TMP_CRON"' EXIT

install_crontab() {
  local pid timeout_seconds elapsed
  timeout_seconds="${HARD_ENG_CRON_INSTALL_TIMEOUT_SECONDS:-15}"
  crontab "$TMP_CRON" &
  pid="$!"
  for ((elapsed = 0; elapsed < timeout_seconds; elapsed++)); do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"
      return "$?"
    fi
    sleep 1
  done
  kill "$pid" 2>/dev/null || true
  wait "$pid" 2>/dev/null || true
  echo "Timed out installing hard-eng auto-sync cron." >&2
  return 1
}

if ! command -v crontab >/dev/null 2>&1; then
  echo "crontab is not available on this machine." >&2
  exit 1
fi

current="$(crontab -l 2>/dev/null || true)"
has_auto_sync=0
has_codex_stack=0
if printf '%s\n' "$current" | grep -Fxq "$BEGIN_MARK" &&
  printf '%s\n' "$current" | grep -Fxq "$JOB" &&
  printf '%s\n' "$current" | grep -Fxq "$END_MARK"; then
  has_auto_sync=1
fi
if [[ "${HARD_ENG_SKIP_CODEX_STACK_CRON:-}" == "1" ]] ||
  { printf '%s\n' "$current" | grep -Fxq "$CODEX_STACK_BEGIN_MARK" &&
    printf '%s\n' "$current" | grep -Fxq "$CODEX_STACK_JOB" &&
    printf '%s\n' "$current" | grep -Fxq "$CODEX_STACK_END_MARK"; }; then
  has_codex_stack=1
fi
if [[ "$has_auto_sync" == "1" && "$has_codex_stack" == "1" ]]; then
  echo "Hard Eng auto-sync cron already installed: auto-sync=$SCHEDULE codex-stack=${HARD_ENG_SKIP_CODEX_STACK_CRON:-0}"
  exit 0
fi

filtered="$(printf '%s\n' "$current" | awk \
  -v begin="$BEGIN_MARK" \
  -v end="$END_MARK" \
  -v stack_begin="$CODEX_STACK_BEGIN_MARK" \
  -v stack_end="$CODEX_STACK_END_MARK" '
  $0 == begin || $0 == stack_begin { skip = 1; next }
  $0 == end || $0 == stack_end { skip = 0; next }
  !skip { print }
')"

{
  printf '%s\n' "$filtered"
  printf '%s\n' "$BEGIN_MARK"
  printf '%s\n' "$JOB"
  printf '%s\n' "$END_MARK"
  if [[ "${HARD_ENG_SKIP_CODEX_STACK_CRON:-}" != "1" ]]; then
    printf '%s\n' "$CODEX_STACK_BEGIN_MARK"
    printf '%s\n' "$CODEX_STACK_JOB"
    printf '%s\n' "$CODEX_STACK_END_MARK"
  fi
} >"$TMP_CRON"

install_crontab

echo "Installed hard-eng cron: auto-sync=$SCHEDULE codex-stack=${HARD_ENG_SKIP_CODEX_STACK_CRON:-0}"

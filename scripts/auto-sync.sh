#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---pull}"

cd "$ROOT"
source "$ROOT/scripts/no-mistakes-wrapper-install.sh"
LOCK_DIR="$(git rev-parse --git-path hard-eng-auto-sync.lock)"

if [[ "${HARD_ENG_SKIP_AUTO_SYNC:-}" == "1" ]]; then
  exit 0
fi

case "$MODE" in
  --pull|--after-pull) ;;
  *)
    echo "Usage: scripts/auto-sync.sh [--pull|--after-pull]" >&2
    exit 2
    ;;
esac

if [[ "$(basename "$ROOT")" != ".agents" ]]; then
  exit 0
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another hard-eng auto-sync is running; skipping."
  exit 0
fi
trap 'rmdir "$LOCK_DIR"' EXIT

update_no_mistakes() {
  local binary real_binary

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_UPDATE:-}" == "1" ]]; then
    return 0
  fi

  binary="${HARD_ENG_NO_MISTAKES_BIN:-}"
  if [[ -z "$binary" ]]; then
    if command -v no-mistakes >/dev/null 2>&1; then
      binary="$(command -v no-mistakes)"
    elif [[ -x "$HOME/.no-mistakes/bin/no-mistakes" ]]; then
      binary="$HOME/.no-mistakes/bin/no-mistakes"
    elif [[ -x "$HOME/.local/bin/no-mistakes" ]]; then
      binary="$HOME/.local/bin/no-mistakes"
    else
      echo "Skipping no-mistakes update: no-mistakes not found."
      return 0
    fi
  fi

  real_binary="$(resolve_no_mistakes_command_binary "$binary" || printf '%s\n' "$binary")"
  refresh_no_mistakes_agent_paths

  if ! NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
    NO_MISTAKES_NO_UPDATE_CHECK=1 \
    "$real_binary" update --yes; then
    echo "no-mistakes update failed; continuing auto-sync." >&2
    return 0
  fi

  refresh_no_mistakes_wrapper "$real_binary"
}

update_treehouse() {
  local binary

  if [[ "${HARD_ENG_SKIP_TREEHOUSE_UPDATE:-}" == "1" ]]; then
    return 0
  fi

  binary="${HARD_ENG_TREEHOUSE_BIN:-}"
  if [[ -z "$binary" ]]; then
    if command -v treehouse >/dev/null 2>&1; then
      binary="$(command -v treehouse)"
    else
      echo "Skipping Treehouse update: treehouse not found."
      return 0
    fi
  fi

  if ! "$binary" update; then
    echo "Treehouse update failed; continuing auto-sync." >&2
  fi
}

refresh_local_install() {
  local install_env key value
  if [[ "${HARD_ENG_SKIP_AUTO_INSTALL:-}" == "1" ]]; then
    return 0
  fi

  install_env=(env HARD_ENG_SKIP_NPM_INSTALL=1 HARD_ENG_SKIP_PREREQ_INSTALL=1 HARD_ENG_SKIP_SUBMODULE_INIT=1 HARD_ENG_SKIP_CRON=1)
  for key in HARD_ENG_TRUSTED_WORKSTATION HARD_ENG_SKIP_MCP_CONFIG HARD_ENG_SKIP_WATCHDOG HARD_ENG_SKIP_SHELL_PATH_UPDATE; do
    value="${!key:-0}"
    if [[ "$key" == "HARD_ENG_TRUSTED_WORKSTATION" ]]; then
      case "$value" in 1|true|TRUE|yes|YES|y|Y) install_env+=("$key=1") ;; esac
    elif [[ "$value" == "1" ]]; then
      install_env+=("$key=1")
    fi
  done
  if ! "${install_env[@]}" "$ROOT/scripts/install.sh"; then
    echo "Hard Eng local install refresh failed; run $ROOT/scripts/install.sh manually." >&2
  fi
}

if [[ "$(git branch --show-current)" != "main" ]]; then
  echo "Refusing auto-sync: current branch is not main." >&2
  exit 1
fi

if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "Refusing auto-sync: tracked working tree or index has local changes." >&2
  exit 1
fi

update_no_mistakes
update_treehouse

git fetch origin main

if [[ "$MODE" == "--pull" ]]; then
  HARD_ENG_SKIP_AUTO_SYNC=1 git pull --ff-only origin main
  refresh_local_install
elif [[ "$MODE" == "--after-pull" ]]; then
  refresh_local_install
fi

if [[ "${HARD_ENG_SKIP_SUBMODULE_BUMP:-}" == "1" ]]; then
  "$ROOT/scripts/update-submodules.sh" --init
  echo "Auto-sync complete."
  exit 0
fi

"$ROOT/scripts/update-submodules.sh" --remote

if git diff --quiet && git diff --cached --quiet; then
  echo "Auto-sync complete: no submodule updates."
  exit 0
fi

if command -v rg >/dev/null 2>&1; then
  changed_paths=()
  while IFS= read -r path; do
    changed_paths+=("$path")
  done < <(git diff --name-only -- .gitmodules vendor/skill-upstreams)
  home_matches=""
  secret_matches=""
  if [[ "${#changed_paths[@]}" -gt 0 ]]; then
    home_matches="$(rg -l --hidden --glob '!.git/**' --glob '!**/.git/**' -F "$HOME" -- "${changed_paths[@]}" || true)"
    secret_matches="$(rg -l --hidden --glob '!.git/**' --glob '!**/.git/**' '(github_pat_[A-Za-z0-9_]+|gh[pousr]_[A-Za-z0-9_]+|sk-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----)' -- "${changed_paths[@]}" || true)"
  fi
  matches="${home_matches}${home_matches:+$'\n'}${secret_matches}"
  if [[ -n "$matches" ]]; then
    printf '%s\n' "$matches" | sort -u
    echo "Refusing auto-sync: private path or secret-like reference found after submodule update." >&2
    exit 1
  fi
fi

git add .gitmodules vendor/skill-upstreams

if git diff --cached --quiet; then
  echo "Auto-sync complete: no staged submodule updates."
  exit 0
fi

if [[ "${HARD_ENG_AUTO_PUSH:-}" != "1" ]]; then
  echo "Auto-sync staged submodule updates; set HARD_ENG_AUTO_PUSH=1 to commit and push automatically." >&2
  exit 1
fi

git commit -m "Auto-update skill submodules"
git push --recurse-submodules=check origin main
echo "Auto-sync complete."

#!/usr/bin/env bash
set -euo pipefail

if [[ "${HARD_ENG_SKIP_NPM_INSTALL:-}" == "1" ]]; then
  echo "Skipping MCP tool install because HARD_ENG_SKIP_NPM_INSTALL=1"
  exit 0
fi

repair_missing_npm() {
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  if [[ "${HARD_ENG_SKIP_PREREQ_INSTALL:-0}" == "1" ||
    ! -x "$root/scripts/setup.sh" ]]; then
    return 0
  fi

  "$root/scripts/setup.sh" --prereqs-only
}

if ! command -v npm >/dev/null 2>&1; then
  repair_missing_npm
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found after prerequisite install; cannot install MCP tools." >&2
  exit 1
fi

context_mode_version="${HARD_ENG_CONTEXT_MODE_VERSION:-1.0.166}"
cbm_version="${HARD_ENG_CBM_VERSION:-0.8.1}"
codex_version="${HARD_ENG_CODEX_VERSION:-0.142.0}"
npm install -g "context-mode@$context_mode_version" "codebase-memory-mcp@$cbm_version" "@openai/codex@$codex_version"

sync_shadowed_codebase_memory() {
  local npm_root npm_prefix npm_bin candidate
  npm_root="$(npm root -g)"
  npm_prefix="$(npm prefix -g)"
  npm_bin="$npm_prefix/bin/codebase-memory-mcp"
  if [[ ! -x "$npm_bin" ]]; then
    npm_bin="$npm_root/codebase-memory-mcp/bin.js"
  fi
  if [[ ! -x "$npm_bin" ]]; then
    return 0
  fi

  for candidate in "$HOME/.local/bin/codebase-memory-mcp" "$(command -v codebase-memory-mcp || true)"; do
    if [[ -z "$candidate" || "$candidate" == "$npm_bin" || "$candidate" == "$HOME/.npm-global/bin/codebase-memory-mcp" ]]; then
      continue
    fi
    if [[ ! -e "$candidate" && ! -L "$candidate" ]]; then
      continue
    fi
    if [[ -L "$candidate" ]] && [[ "$(readlink "$candidate")" == "$npm_bin" ]]; then
      continue
    fi

    rm -f "$candidate"
    ln -s "$npm_bin" "$candidate"
    echo "Linked shadowed codebase-memory-mcp at $candidate to $npm_bin"
  done
}

sync_shadowed_codebase_memory

if command -v context-mode >/dev/null 2>&1 &&
  command -v codebase-memory-mcp >/dev/null 2>&1 &&
  command -v codex >/dev/null 2>&1; then
  echo "MCP tools installed and upgraded."
  exit 0
fi

echo "One or more MCP tools are still missing from PATH." >&2
exit 1

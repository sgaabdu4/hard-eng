#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODE="${1:---init}"

cd "$ROOT"

configure_sparse_checkouts() {
  local entry submodule source
  local -a sources
  local entries=(
    "vendor/skill-upstreams/vercel-agent-skills:skills/react-best-practices"
    "vendor/skill-upstreams/impeccable:.agents/skills/impeccable"
    "vendor/skill-upstreams/fallow-skills:fallow/skills/fallow"
    "vendor/skill-upstreams/react-doctor:skills/react-doctor"
    "vendor/skill-upstreams/appwrite-backend:references"
    "vendor/skill-upstreams/building-flutter-apps:references templates hooks .codex-plugin .claude-plugin"
    "vendor/skill-upstreams/no-mistakes:skills/no-mistakes"
    "vendor/skill-upstreams/sentry-cli:plugins/sentry-cli/skills/sentry-cli"
    "vendor/skill-upstreams/sentry-for-ai:skills"
  )

  for entry in "${entries[@]}"; do
    submodule="${entry%%:*}"
    source="${entry#*:}"
    [[ -d "$submodule/.git" || -f "$submodule/.git" ]] || continue
    read -r -a sources <<< "$source"
    git -C "$submodule" sparse-checkout init --cone >/dev/null
    git -C "$submodule" sparse-checkout set "${sources[@]}" >/dev/null
  done
}

case "$MODE" in
  --init|--remote|--status) ;;
  *)
    echo "Usage: scripts/update-submodules.sh [--init|--remote|--status]" >&2
    exit 2
    ;;
esac

if [[ ! -f .gitmodules ]]; then
  echo "No .gitmodules file found."
  exit 0
fi

case "$MODE" in
  --status)
    git submodule status --recursive
    exit 0
    ;;
  --init)
    git submodule sync --recursive
    git submodule update --init --recursive --jobs 6 --recommend-shallow
    configure_sparse_checkouts
    ;;
  --remote)
    if ! git diff --quiet || ! git diff --cached --quiet; then
      echo "Refusing submodule update: tracked working tree or index has local changes." >&2
      echo "Commit, stash, or discard tracked changes, then rerun scripts/update-submodules.sh --remote." >&2
      exit 1
    fi

    git submodule sync --recursive
    git submodule update --init --remote --recursive --jobs 6 --recommend-shallow
    configure_sparse_checkouts
    git status --short
    ;;
esac

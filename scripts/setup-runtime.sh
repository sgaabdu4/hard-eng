#!/usr/bin/env bash

if [[ -z "${ROOT:-}" ]]; then
  ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fi

if [[ -z "${HARD_ENG_NO_MISTAKES_HOME_CONFIGURED+x}" ]]; then
  if [[ -n "${NO_MISTAKES_HOME:-}" ]]; then
    HARD_ENG_NO_MISTAKES_HOME_CONFIGURED=1
  else
    HARD_ENG_NO_MISTAKES_HOME_CONFIGURED=0
  fi
fi
NO_MISTAKES_HOME="${NO_MISTAKES_HOME:-$HOME/.no-mistakes}"
TREEHOUSE_INSTALL_URL="${HARD_ENG_TREEHOUSE_INSTALL_URL:-https://kunchenguid.github.io/treehouse/install.sh}"
source "$ROOT/scripts/no-mistakes-wrapper-install.sh"

ask_extra_repos() {
  local answer

  if [[ -n "${HARD_ENG_NO_MISTAKES_REPOS:-}" ||
    "${HARD_ENG_SKIP_NO_MISTAKES:-}" == "1" ||
    "${HARD_ENG_SKIP_NO_MISTAKES_INIT:-}" == "1" ]]; then
    return 0
  fi

  if ! is_interactive; then
    return 0
  fi

  read -r -p "Extra repos to initialize with no-mistakes, colon-separated, blank to skip: " answer
  if [[ -n "$answer" ]]; then
    export HARD_ENG_NO_MISTAKES_REPOS="$answer"
  fi
}

ask_skill_selection() {
  local answer available
  if [[ -n "${HARD_ENG_SKILLS:-}" ]]; then
    return 0
  fi
  if ! is_interactive; then
    return 0
  fi
  if [[ "${HARD_ENG_SKIP_SKILL_SELECTION_PROMPT:-0}" == "1" ]]; then
    return 0
  fi
  if [[ -f "$ROOT/scripts/manage-skills.mjs" ]]; then
    available="$(node "$ROOT/scripts/manage-skills.mjs" list | tr '\n' ',' | sed 's/,$//')"
    echo "Available Hard Eng skills: $available"
  fi
  read -r -p "Hard Eng skills to link: all, none, or comma-separated names [all]: " answer
  if [[ -n "$answer" ]]; then
    export HARD_ENG_SKILLS="$answer"
  fi
}

persist_skill_selection() {
  if [[ -n "${HARD_ENG_SKILLS:-}" && -f "$ROOT/scripts/manage-skills.mjs" ]]; then
    node "$ROOT/scripts/manage-skills.mjs" configure "$HARD_ENG_SKILLS"
  fi
}

choose_setup_options() {
  if ask_yes_no HARD_ENG_SETUP_NO_MISTAKES "Install or update no-mistakes and initialize .agents?" yes; then
    unset HARD_ENG_SKIP_NO_MISTAKES
  else
    export HARD_ENG_SKIP_NO_MISTAKES=1
  fi

  if ask_yes_no HARD_ENG_SETUP_TREEHOUSE "Install or update Treehouse?" yes; then
    unset HARD_ENG_SKIP_TREEHOUSE
  else
    export HARD_ENG_SKIP_TREEHOUSE=1
  fi

  if ask_yes_no HARD_ENG_ENABLE_CRON "Enable auto-sync cron for .agents?" no; then
    export HARD_ENG_ENABLE_CRON=1
    unset HARD_ENG_SKIP_CRON
    unset HARD_ENG_REMOVE_MANAGED_CRON
  else
    unset HARD_ENG_ENABLE_CRON
    export HARD_ENG_SKIP_CRON=1
    export HARD_ENG_REMOVE_MANAGED_CRON=1
  fi

  ask_extra_repos
  ask_skill_selection
}

install_or_update_no_mistakes() {
  local binary real_binary version os arch filename url download_dir install_dir link_dir wrapper_binary

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES:-}" == "1" ]]; then
    return 0
  fi
  install_dir="$NO_MISTAKES_HOME/bin"
  link_dir="${NO_MISTAKES_LINK_DIR:-$HOME/.local/bin}"
  if [[ -n "${HARD_ENG_NO_MISTAKES_REAL_BIN:-}" && -x "$HARD_ENG_NO_MISTAKES_REAL_BIN" ]]; then
    binary="$HARD_ENG_NO_MISTAKES_REAL_BIN"
    NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$binary" update --yes
    refresh_no_mistakes_wrapper "$binary"
    return 0
  fi
  if ! no_mistakes_wrapper_uses_configured_real_binary &&
    command -v no-mistakes >/dev/null 2>&1; then
    binary="$(command -v no-mistakes)"
    real_binary="$(resolve_no_mistakes_command_binary "$binary" || printf '%s\n' "$binary")"
    NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$real_binary" update --yes
    refresh_no_mistakes_wrapper "$real_binary"
    return 0
  fi
  if [[ -x "$install_dir/no-mistakes" ]]; then
    NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$install_dir/no-mistakes" update --yes
    refresh_no_mistakes_wrapper "$install_dir/no-mistakes"
    return 0
  fi
  if command -v no-mistakes >/dev/null 2>&1; then
    binary="$(command -v no-mistakes)"
    real_binary="$(resolve_no_mistakes_command_binary "$binary" || printf '%s\n' "$binary")"
    NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$real_binary" update --yes
    wrapper_binary="$real_binary"
    if [[ -x "$install_dir/no-mistakes" ]]; then
      wrapper_binary="$install_dir/no-mistakes"
    fi
    refresh_no_mistakes_wrapper "$wrapper_binary"
    return 0
  fi
  require_command curl
  require_command tar
  version="${HARD_ENG_NO_MISTAKES_VERSION:-v1.30.1}"
  if [[ "$version" == "latest" ]]; then
    version="$(curl -fsSL "https://api.github.com/repos/kunchenguid/no-mistakes/releases/latest" |
      sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')"
  fi
  if [[ -z "$version" ]]; then
    echo "Could not determine latest no-mistakes release." >&2
    exit 1
  fi
  os="$(uname -s | tr '[:upper:]' '[:lower:]')"
  arch="$(uname -m)"
  case "$os" in
    darwin|linux) ;;
    *)
      echo "Unsupported no-mistakes OS: $os" >&2
      exit 1
      ;;
  esac

  case "$arch" in
    x86_64|amd64) arch="amd64" ;;
    arm64|aarch64) arch="arm64" ;;
    *)
      echo "Unsupported no-mistakes architecture: $arch" >&2
      exit 1
      ;;
  esac

  filename="no-mistakes-${version}-${os}-${arch}.tar.gz"
  url="https://github.com/kunchenguid/no-mistakes/releases/download/${version}/${filename}"
  download_dir="$NO_MISTAKES_HOME/downloads/$version"
  mkdir -p "$download_dir" "$install_dir" "$link_dir"
  curl -fsSL "$url" -o "$download_dir/$filename"
  tar xzf "$download_dir/$filename" -C "$download_dir"
  cp "$download_dir/no-mistakes" "$install_dir/no-mistakes"
  chmod 755 "$install_dir/no-mistakes"

  refresh_no_mistakes_wrapper "$install_dir/no-mistakes"
  refresh_no_mistakes_agent_paths
  NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
    NO_MISTAKES_NO_UPDATE_CHECK=1 \
    "$install_dir/no-mistakes" daemon restart
}

install_or_update_treehouse() {
  local installer
  if [[ "${HARD_ENG_SKIP_TREEHOUSE:-}" == "1" ]]; then
    return 0
  fi
  if command -v treehouse >/dev/null 2>&1; then
    if ! treehouse update; then
      echo "Treehouse update failed; continuing setup." >&2
    fi
    return 0
  fi
  require_command curl
  installer="$(mktemp "${TMPDIR:-/tmp}/hard-eng-treehouse-install.XXXXXX")"
  curl -fsSL "$TREEHOUSE_INSTALL_URL" -o "$installer"
  sh "$installer"
  rm -f "$installer"
  prepend_agent_paths
  if ! command -v treehouse >/dev/null 2>&1; then
    echo "Treehouse install completed but treehouse is not on PATH." >&2
    exit 1
  fi
}

no_mistakes_binary() {
  if [[ -n "${HARD_ENG_NO_MISTAKES_REAL_BIN:-}" && -x "$HARD_ENG_NO_MISTAKES_REAL_BIN" ]]; then
    printf '%s\n' "$HARD_ENG_NO_MISTAKES_REAL_BIN"
  elif ! no_mistakes_wrapper_uses_configured_real_binary &&
    command -v no-mistakes >/dev/null 2>&1; then
    command -v no-mistakes
  elif [[ -x "$NO_MISTAKES_HOME/bin/no-mistakes" ]]; then
    printf '%s\n' "$NO_MISTAKES_HOME/bin/no-mistakes"
  elif command -v no-mistakes >/dev/null 2>&1; then
    command -v no-mistakes
  elif [[ -x "$HOME/.local/bin/no-mistakes" ]]; then
    printf '%s\n' "$HOME/.local/bin/no-mistakes"
  fi
}

run_no_mistakes_with_isolated_agent_home() {
  local binary="$1"
  shift
  local isolated_home cleanup status
  isolated_home="${HARD_ENG_NO_MISTAKES_AGENT_HOME:-}"
  cleanup=0

  if [[ -z "$isolated_home" ]]; then
    isolated_home="$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-no-mistakes-home.XXXXXX")"
    cleanup=1
  fi
  mkdir -p "$isolated_home"
  set +e
  if is_managed_no_mistakes_wrapper "$binary" && [[ -z "${NM_HOME:-}" ]]; then
    HOME="$isolated_home" \
      CODEX_HOME="$isolated_home/.codex" \
      NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$binary" "$@"
  else
    HOME="$isolated_home" \
      CODEX_HOME="$isolated_home/.codex" \
      NM_HOME="${NM_HOME:-$NO_MISTAKES_HOME}" \
      NO_MISTAKES_TELEMETRY="${NO_MISTAKES_TELEMETRY:-0}" \
      NO_MISTAKES_NO_UPDATE_CHECK=1 \
      "$binary" "$@"
  fi
  status=$?
  set -e

  if [[ "$cleanup" == "1" ]]; then
    rm -rf "$isolated_home"
  fi
  return "$status"
}

ensure_worktree_ready_repo() {
  local repo="$1"
  local script="$ROOT/scripts/ensure-worktree-ready.sh"
  local args=()

  if [[ "${HARD_ENG_SKIP_WORKTREE_READY:-}" == "1" ]]; then
    return 0
  fi
  if [[ ! -x "$script" ]]; then
    echo "Skipping worktree readiness for $repo: $script is missing or not executable." >&2
    return 0
  fi

  if [[ "${HARD_ENG_WORKTREE_READY_INSTALL:-}" == "1" ]]; then
    args+=("--install")
  fi
  if [[ "${#args[@]}" -gt 0 ]]; then
    "$script" "${args[@]}" "$repo"
  else
    "$script" "$repo"
  fi
}

init_no_mistakes_repo() {
  local repo="$1"
  local binary
  if [[ "${HARD_ENG_SKIP_NO_MISTAKES:-}" == "1" ||
    "${HARD_ENG_SKIP_NO_MISTAKES_INIT:-}" == "1" ]]; then
    return 0
  fi

  binary="$(no_mistakes_binary || true)"
  if [[ -z "$binary" ]]; then
    echo "Skipping no-mistakes init for $repo: binary not found." >&2
    return 0
  fi

  if ! git -C "$repo" rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Skipping no-mistakes init for $repo: not a git checkout." >&2
    return 0
  fi

  if [[ -z "$(git -C "$repo" remote get-url origin 2>/dev/null || true)" ]]; then
    echo "Skipping no-mistakes init for $repo: no origin remote." >&2
    return 0
  fi
  (
    cd "$repo"
    run_no_mistakes_with_isolated_agent_home "$binary" init
  )
  if [[ -f "$ROOT/integrations/no-mistakes/scripts/repair-gate-hook.mjs" ]]; then
    node "$ROOT/integrations/no-mistakes/scripts/repair-gate-hook.mjs" "$repo"
  fi
  ensure_worktree_ready_repo "$repo"
}

init_extra_no_mistakes_repos() {
  local extra_repos repo
  extra_repos="${HARD_ENG_NO_MISTAKES_REPOS:-}"
  if [[ -z "$extra_repos" ]]; then
    return 0
  fi

  IFS=':' read -r -a repos <<<"$extra_repos"
  for repo in "${repos[@]}"; do
    [[ -n "$repo" ]] || continue
    init_no_mistakes_repo "$repo"
  done
}

wait_for_job() {
  local pid="$1"
  local label="$2"

  if wait "$pid"; then
    return 0
  fi
  echo "$label failed." >&2
  return 1
}

run_parallel_install() {
  local install_pid no_mistakes_pid treehouse_pid root_init_pid extra_init_pid
  local status=0
  "$ROOT/scripts/install.sh" &
  install_pid=$!
  install_or_update_no_mistakes &
  no_mistakes_pid=$!
  install_or_update_treehouse &
  treehouse_pid=$!
  wait_for_job "$install_pid" "Agent install" || status=1
  wait_for_job "$no_mistakes_pid" "no-mistakes install" || status=1
  wait_for_job "$treehouse_pid" "Treehouse install" || status=1
  if [[ "$status" != "0" ]]; then
    exit 1
  fi
  init_no_mistakes_repo "$ROOT" &
  root_init_pid=$!
  init_extra_no_mistakes_repos &
  extra_init_pid=$!
  wait_for_job "$root_init_pid" "no-mistakes root init" || status=1
  wait_for_job "$extra_init_pid" "no-mistakes extra repo init" || status=1
  if [[ "$status" != "0" ]]; then
    exit 1
  fi
}

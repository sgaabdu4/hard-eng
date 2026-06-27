#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${HARD_ENG_REPO_URL:-https://github.com/sgaabdu4/hard-eng.git}"
ROOT="${HARD_ENG_HOME:-$HOME/.agents}"
NO_MISTAKES_HOME="${NO_MISTAKES_HOME:-$HOME/.no-mistakes}"
TREEHOUSE_INSTALL_URL="${HARD_ENG_TREEHOUSE_INSTALL_URL:-https://kunchenguid.github.io/treehouse/install.sh}"

enabled() {
  case "${1:-}" in
    1|true|TRUE|yes|YES|y|Y) return 0 ;;
    *) return 1 ;;
  esac
}

require_command() {
  local command="$1"
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "Missing required command: $command" >&2
    exit 1
  fi
}

load_homebrew_shellenv() {
  local brew_bin=""
  if command -v brew >/dev/null 2>&1; then
    brew_bin="$(command -v brew)"
  elif [[ -x /opt/homebrew/bin/brew ]]; then
    brew_bin="/opt/homebrew/bin/brew"
  elif [[ -x /usr/local/bin/brew ]]; then
    brew_bin="/usr/local/bin/brew"
  fi
  if [[ -n "$brew_bin" ]]; then
    eval "$("$brew_bin" shellenv)"
  fi
}

prepend_agent_paths() {
  export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/flutter/bin:$HOME/.pub-cache/bin:$PATH"
  load_homebrew_shellenv
  hash -r 2>/dev/null || true
}

ensure_xcode_cli_tools() {
  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 0
  fi
  if xcode-select -p >/dev/null 2>&1; then
    return 0
  fi
  if [[ "${HARD_ENG_SKIP_XCODE_SELECT_INSTALL:-0}" == "1" ]]; then
    echo "Xcode Command Line Tools are missing; install them with: xcode-select --install" >&2
    exit 1
  fi
  echo "Requesting Xcode Command Line Tools install..."
  xcode-select --install >/dev/null 2>&1 || true
  echo "Finish the Xcode Command Line Tools installer, then rerun setup." >&2
  exit 1
}

ensure_homebrew() {
  prepend_agent_paths
  if command -v brew >/dev/null 2>&1; then
    return 0
  fi
  if [[ "$(uname -s)" != "Darwin" ]]; then
    echo "Homebrew is missing; install it before running setup on this platform." >&2
    exit 1
  fi
  if [[ "${HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP:-0}" != "1" ]]; then
    echo "Homebrew is missing; install it manually or set HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP=1 to run the upstream bootstrap." >&2
    exit 1
  fi
  require_command curl
  echo "Installing Homebrew..."
  NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  prepend_agent_paths
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew install completed but brew is not on PATH." >&2
    exit 1
  fi
}

print_shell_path_block() {
  cat <<'EOF'
# BEGIN hard-eng bootstrap path
if [ -x /opt/homebrew/bin/brew ]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -x /usr/local/bin/brew ]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi
export PATH="$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/flutter/bin:$HOME/.pub-cache/bin:$PATH"
# END hard-eng bootstrap path
EOF
}

install_shell_path_block() {
  if [[ "${HARD_ENG_SKIP_SHELL_PATH_UPDATE:-0}" == "1" ]]; then
    return 0
  fi

  local target begin end tmp
  target="${HARD_ENG_SHELL_ENV_FILE:-$HOME/.zshenv}"
  begin="# BEGIN hard-eng bootstrap path"
  end="# END hard-eng bootstrap path"
  mkdir -p "$(dirname "$target")"
  if [[ -f "$target" ]] && grep -q "$begin" "$target" && ! grep -q "$end" "$target"; then
    echo "Preserving malformed managed PATH block in $target; missing end marker." >&2
    return 0
  fi
  if [[ -f "$target" ]] && grep -q "$begin" "$target"; then
    tmp="${target}.hard-eng.$$"
    awk -v begin="$begin" -v end="$end" '
      function print_block() {
        print "# BEGIN hard-eng bootstrap path"
        print "if [ -x /opt/homebrew/bin/brew ]; then"
        print "  eval \"$(/opt/homebrew/bin/brew shellenv)\""
        print "elif [ -x /usr/local/bin/brew ]; then"
        print "  eval \"$(/usr/local/bin/brew shellenv)\""
        print "fi"
        print "export PATH=\"$HOME/.npm-global/bin:$HOME/.local/bin:$HOME/flutter/bin:$HOME/.pub-cache/bin:$PATH\""
        print "# END hard-eng bootstrap path"
      }
      $0 == begin {
        if (!done) {
          print_block()
        }
        done = 1
        skipping = 1
        next
      }
      $0 == end && skipping {
        skipping = 0
        next
      }
      !skipping {
        print
      }
      END {
        if (!done) {
          print_block()
        }
      }
    ' "$target" >"$tmp"
    mv "$tmp" "$target"
  else
    if [[ -s "$target" ]]; then
      printf '\n' >>"$target"
    fi
    print_shell_path_block >>"$target"
  fi
}

needs_brew_prerequisites() {
  ! command -v git >/dev/null 2>&1 ||
    ! command -v node >/dev/null 2>&1 ||
    ! command -v npm >/dev/null 2>&1 ||
    ! command -v dart >/dev/null 2>&1
}

install_brew_packages() {
  local packages=()
  if ! command -v git >/dev/null 2>&1; then
    packages+=("git")
  fi
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    packages+=("node")
  fi
  if ! command -v dart >/dev/null 2>&1; then
    brew tap dart-lang/dart
    packages+=("dart")
  fi
  if [[ "${#packages[@]}" -gt 0 ]]; then
    echo "Installing prerequisite packages: ${packages[*]}"
    brew install "${packages[@]}"
    prepend_agent_paths
  fi
}

install_flutter_if_missing() {
  prepend_agent_paths
  if command -v flutter >/dev/null 2>&1; then
    return 0
  fi
  if [[ "${HARD_ENG_SKIP_FLUTTER_INSTALL:-0}" == "1" ]]; then
    echo "Flutter is missing; skipped because HARD_ENG_SKIP_FLUTTER_INSTALL=1."
    return 0
  fi
  require_command git
  local flutter_home="${HARD_ENG_FLUTTER_HOME:-$HOME/flutter}"
  if [[ -x "$flutter_home/bin/flutter" ]]; then
    export PATH="$flutter_home/bin:$PATH"
    return 0
  fi
  if [[ -e "$flutter_home" ]]; then
    echo "Flutter target exists but $flutter_home/bin/flutter is missing: $flutter_home" >&2
    echo "Set HARD_ENG_FLUTTER_HOME to another path or fix the existing checkout." >&2
    exit 1
  fi

  echo "Installing Flutter stable SDK at $flutter_home..."
  git clone --depth 1 -b stable https://github.com/flutter/flutter.git "$flutter_home"
  export PATH="$flutter_home/bin:$PATH"
  flutter --version >/dev/null
}

install_python_prerequisites() {
  require_command python3
  if python3 - <<'PY' >/dev/null 2>&1
import tiktoken
PY
  then
    return 0
  fi
  if [[ "${HARD_ENG_SKIP_PYTHON_DEPS:-0}" == "1" ]]; then
    echo "Python package tiktoken is missing; unset HARD_ENG_SKIP_PYTHON_DEPS to install it." >&2
    exit 1
  fi
  python3 -m pip install --user tiktoken
}

install_prerequisites() {
  if [[ "${HARD_ENG_SKIP_PREREQ_INSTALL:-0}" == "1" ]]; then
    prepend_agent_paths
    return 0
  fi
  prepend_agent_paths
  ensure_xcode_cli_tools
  if needs_brew_prerequisites; then
    ensure_homebrew
    install_brew_packages
  fi
  install_python_prerequisites
  install_flutter_if_missing
  install_shell_path_block
  export HARD_ENG_PREREQS_READY=1
}

is_interactive() {
  [[ -t 0 && -t 1 && "${CI:-}" != "true" ]]
}

is_disabled() {
  case "${1:-}" in
    0|false|FALSE|no|NO|n|N) return 0 ;;
    *) return 1 ;;
  esac
}

ask_yes_no() {
  local env_name="$1"
  local prompt="$2"
  local default="$3"
  local value="${!env_name:-}"
  local answer suffix

  if [[ -n "$value" ]]; then
    enabled "$value"
    return "$?"
  fi

  if ! is_interactive; then
    [[ "$default" == "yes" ]]
    return "$?"
  fi

  if [[ "$default" == "yes" ]]; then
    suffix="[Y/n]"
  else
    suffix="[y/N]"
  fi

  while true; do
    read -r -p "$prompt $suffix " answer
    if [[ -z "$answer" ]]; then
      [[ "$default" == "yes" ]]
      return "$?"
    fi
    if enabled "$answer"; then
      return 0
    fi
    if is_disabled "$answer"; then
      return 1
    fi
    echo "Please answer yes or no." >&2
  done
}

ask_explained_yes_no() {
  local env_name="$1"
  local title="$2"
  local details="$3"
  local default="$4"

  if [[ -z "${!env_name:-}" && is_interactive ]]; then
    printf '\n%s\n' "$title"
    printf '  %s\n' "$details"
  fi
  ask_yes_no "$env_name" "$title" "$default"
}

choose_interactive_default_options() {
  cat <<'EOF'
Hard Eng setup will ask before installing workstation-level tools.
Use --safe for the public-safe surface only, or --full for the complete workstation setup.
EOF

  if ! ask_explained_yes_no \
    HARD_ENG_INSTALL_AGENT_SURFACE \
    "Install the public-safe Hard Eng agent surface?" \
    "Clones/updates this repo, links shared AGENTS.md, selected skills, Codex hooks, and repo-local Git hooks." \
    yes; then
    echo "No install selected. Exiting."
    exit 0
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_PREREQS \
    "Install or repair prerequisite tools?" \
    "May install missing Git, Node/npm, Dart, Python tiktoken, Flutter, and a managed shell PATH block." \
    no; then
    unset HARD_ENG_SKIP_PREREQ_INSTALL
    if ask_explained_yes_no \
      HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP \
      "Allow Homebrew bootstrap if Homebrew is missing?" \
      "Runs the upstream Homebrew installer only when Homebrew is missing; otherwise setup stops and asks you to install Homebrew manually." \
      no; then
      export HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP=1
    else
      unset HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP
    fi
  else
    export HARD_ENG_SKIP_PREREQ_INSTALL=1
    export HARD_ENG_SKIP_SHELL_PATH_UPDATE=1
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_NPM_TOOLS \
    "Install or update global npm tools?" \
    "Installs context-mode, codebase-memory-mcp, and @openai/codex for MCP/context tooling." \
    no; then
    unset HARD_ENG_SKIP_NPM_INSTALL
  else
    export HARD_ENG_SKIP_NPM_INSTALL=1
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_MCP_CONFIG \
    "Write active Codex MCP config?" \
    "Registers codebase-memory-mcp, context-mode, and Dart in ~/.codex/config.toml; commands must exist if npm install is skipped." \
    no; then
    unset HARD_ENG_SKIP_MCP_CONFIG
  else
    export HARD_ENG_SKIP_MCP_CONFIG=1
  fi

  if ask_explained_yes_no \
    HARD_ENG_TRUSTED_WORKSTATION \
    "Write trusted Codex settings?" \
    "Sets approval_policy = \"never\" and sandbox_mode = \"danger-full-access\"; only use on your own trusted workstation." \
    no; then
    export HARD_ENG_TRUSTED_WORKSTATION=1
  else
    unset HARD_ENG_TRUSTED_WORKSTATION
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_WATCHDOG \
    "Install the Codex watchdog and managed bins?" \
    "Installs ~/.codex/bin health/cleanup/update scripts and a macOS LaunchAgent; process killing remains opt-in." \
    no; then
    unset HARD_ENG_SKIP_WATCHDOG
  else
    export HARD_ENG_SKIP_WATCHDOG=1
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_TREEHOUSE \
    "Install or update Treehouse?" \
    "Provides reusable worktree isolation for staged agent work." \
    no; then
    unset HARD_ENG_SKIP_TREEHOUSE
    export HARD_ENG_SETUP_TREEHOUSE=1
  else
    export HARD_ENG_SKIP_TREEHOUSE=1
    export HARD_ENG_SETUP_TREEHOUSE=0
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_NO_MISTAKES \
    "Install or update no-mistakes and initialize .agents?" \
    "Provides the final local shipping gate and PR evidence workflow." \
    no; then
    unset HARD_ENG_SKIP_NO_MISTAKES
    unset HARD_ENG_SKIP_NO_MISTAKES_INIT
    export HARD_ENG_SETUP_NO_MISTAKES=1
  else
    export HARD_ENG_SKIP_NO_MISTAKES=1
    export HARD_ENG_SKIP_NO_MISTAKES_INIT=1
    export HARD_ENG_SETUP_NO_MISTAKES=0
  fi

  if ask_explained_yes_no \
    HARD_ENG_SETUP_WORKTREE_READY \
    "Run worktree readiness checks?" \
    "Checks that project hooks are active before trusting no-mistakes or push gates." \
    no; then
    unset HARD_ENG_SKIP_WORKTREE_READY
  else
    export HARD_ENG_SKIP_WORKTREE_READY=1
  fi

  if ask_explained_yes_no \
    HARD_ENG_ENABLE_CRON \
    "Enable optional cron jobs?" \
    "Adds marked crontab blocks for repo auto-sync and Codex stack update jobs." \
    no; then
    export HARD_ENG_ENABLE_CRON=1
    unset HARD_ENG_SKIP_CRON
    unset HARD_ENG_REMOVE_MANAGED_CRON
  else
    export HARD_ENG_ENABLE_CRON=0
    export HARD_ENG_SKIP_CRON=1
    export HARD_ENG_REMOVE_MANAGED_CRON=1
  fi
}

usage() {
  cat <<'EOF'
Usage:
  setup.sh [--safe|--full|--skills-only|--prereqs-only|--uninstall] [--dry-run]
Modes:
  --safe         Public-safe install; link rules/skills/config without external tools or trusted Codex settings.
  --full         Full workstation setup; cron still needs HARD_ENG_ENABLE_CRON=1.
  --skills-only  Link repo configs/skills only; skip tools, watchdog, cron, repair.
  --prereqs-only Install only prerequisite tools needed by setup.
  --uninstall    Remove Hard Eng-managed links, hooks, cron, watchdog, bins, caches, and shell PATH blocks.
  --dry-run      Print planned writes without changing files.
Default:
  Interactive terminals ask before workstation-level installs; non-interactive uses --safe behavior.
EOF
}

apply_full_mode() {
  export HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP="${HARD_ENG_ALLOW_HOMEBREW_BOOTSTRAP:-1}"
  export HARD_ENG_SETUP_NO_MISTAKES="${HARD_ENG_SETUP_NO_MISTAKES:-1}"
  export HARD_ENG_SETUP_TREEHOUSE="${HARD_ENG_SETUP_TREEHOUSE:-1}"
  export HARD_ENG_SKILLS="${HARD_ENG_SKILLS:-all}"
  unset HARD_ENG_SKIP_NPM_INSTALL
  unset HARD_ENG_SKIP_MCP_CONFIG
  unset HARD_ENG_SKIP_NO_MISTAKES
  unset HARD_ENG_SKIP_NO_MISTAKES_INIT
  unset HARD_ENG_SKIP_TREEHOUSE
  unset HARD_ENG_SKIP_WATCHDOG
  unset HARD_ENG_SKIP_CRON
  unset HARD_ENG_REMOVE_MANAGED_CRON
  unset HARD_ENG_SKIP_WORKTREE_READY
}

apply_skills_only_mode() {
  export HARD_ENG_SKIP_PREREQ_INSTALL=1
  export HARD_ENG_SKIP_NPM_INSTALL=1
  export HARD_ENG_SKIP_MCP_CONFIG=1
  export HARD_ENG_SKIP_NO_MISTAKES=1
  export HARD_ENG_SKIP_NO_MISTAKES_INIT=1
  export HARD_ENG_SKIP_TREEHOUSE=1
  export HARD_ENG_SKIP_WATCHDOG=1
  export HARD_ENG_SKIP_CRON=1
  export HARD_ENG_REMOVE_MANAGED_CRON=1
  export HARD_ENG_SKIP_WORKTREE_READY=1
  export HARD_ENG_SETUP_NO_MISTAKES=0
  export HARD_ENG_SETUP_TREEHOUSE=0
  unset HARD_ENG_ENABLE_CRON
}

apply_safe_mode() {
  apply_skills_only_mode
  export HARD_ENG_SKILLS="${HARD_ENG_SKILLS:-all}"
  export HARD_ENG_SKIP_SHELL_PATH_UPDATE=1
}

print_setup_dry_run() {
  local mode="$1"
  cat <<EOF
Hard Eng setup dry-run for ${mode:-default} mode
Would use repo: $ROOT
Would clone/update from: $REPO_URL
Would then run scripts/install.sh with the effective setup flags.
EOF
  if [[ "${HARD_ENG_SKIP_PREREQ_INSTALL:-0}" != "1" ]]; then
    cat <<'EOF'
Would repair prerequisites when missing: Git, Node/npm, Dart, Python tiktoken, Flutter, and managed shell PATH.
EOF
  else
    cat <<'EOF'
Would skip prerequisite repair and shell PATH changes.
EOF
  fi
  if [[ "${HARD_ENG_SKIP_NPM_INSTALL:-0}" != "1" ]]; then
    cat <<'EOF'
Would install or update global npm tools: context-mode, codebase-memory-mcp, @openai/codex.
EOF
  else
    cat <<'EOF'
Would skip global npm tool installation.
EOF
  fi
  if [[ "${HARD_ENG_SKIP_MCP_CONFIG:-0}" == "1" ]]; then
    cat <<'EOF'
Would skip active Codex MCP config resolution.
EOF
  fi
  if [[ "${HARD_ENG_SKIP_NO_MISTAKES:-0}" != "1" ]]; then
    cat <<'EOF'
Would install/update no-mistakes and initialize configured repos.
EOF
  else
    cat <<'EOF'
Would skip no-mistakes install/init.
EOF
  fi
  if [[ "${HARD_ENG_SKIP_TREEHOUSE:-0}" != "1" ]]; then
    cat <<'EOF'
Would install/update Treehouse.
EOF
  else
    cat <<'EOF'
Would skip Treehouse install/update.
EOF
  fi
  if [[ "${HARD_ENG_SKIP_WATCHDOG:-0}" != "1" ]]; then
    cat <<'EOF'
Would install Codex watchdog managed bins and LaunchAgent.
EOF
  else
    cat <<'EOF'
Would skip Codex watchdog managed bins and LaunchAgent.
EOF
  fi
  if enabled "${HARD_ENG_TRUSTED_WORKSTATION:-0}"; then
    cat <<'EOF'
Would write trusted Codex settings: approval_policy = "never", sandbox_mode = "danger-full-access".
EOF
  else
    cat <<'EOF'
Would not write trusted Codex sandbox/approval settings.
EOF
  fi
}

clone_or_update_repo() {
  if git -C "$ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    echo "Updating existing .agents checkout: $ROOT"
    git -C "$ROOT" pull --ff-only origin main
    return 0
  fi
  if [[ -e "$ROOT" ]]; then
    echo "Refusing setup: $ROOT exists but is not a git checkout." >&2
    exit 1
  fi
  echo "Cloning .agents into $ROOT"
  git clone --recurse-submodules "$REPO_URL" "$ROOT"
}

mode=""
uninstall_args=""
while [[ "$#" -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --dry-run)
      export HARD_ENG_DRY_RUN=1
      ;;
    --safe|--full|--skills-only|--prereqs-only|--uninstall)
      if [[ -n "$mode" ]]; then
        echo "Only one setup mode can be used at a time." >&2
        usage >&2
        exit 2
      fi
      mode="$1"
      ;;
    --yes)
      uninstall_args="$uninstall_args --yes"
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  shift
done

case "$mode" in
  --prereqs-only)
    if [[ "${HARD_ENG_DRY_RUN:-0}" == "1" ]]; then
      print_setup_dry_run "$mode"
      exit 0
    fi
    install_prerequisites
    exit 0
    ;;
  --uninstall)
    if [[ -x "$ROOT/scripts/uninstall.sh" ]]; then
      if [[ "${HARD_ENG_DRY_RUN:-0}" == "1" ]]; then
        uninstall_args="$uninstall_args --dry-run"
      fi
      "$ROOT/scripts/uninstall.sh" $uninstall_args
      exit "$?"
    fi
    echo "Missing uninstall script: $ROOT/scripts/uninstall.sh" >&2
    exit 1
    ;;
  --safe)
    apply_safe_mode
    ;;
  --full)
    apply_full_mode
    ;;
  --skills-only)
    apply_skills_only_mode
    ;;
  "")
    if [[ "${HARD_ENG_DRY_RUN:-0}" == "1" ]]; then
      apply_safe_mode
    elif is_interactive; then
      choose_interactive_default_options
    else
      apply_safe_mode
    fi
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
if [[ "${HARD_ENG_DRY_RUN:-0}" == "1" ]]; then
  print_setup_dry_run "$mode"
  if [[ -x "$ROOT/scripts/install.sh" ]]; then
    HARD_ENG_DRY_RUN=1 "$ROOT/scripts/install.sh" --dry-run
  fi
  exit 0
fi
install_prerequisites
require_command git
clone_or_update_repo
if [[ ! -f "$ROOT/scripts/setup-runtime.sh" ]]; then
  echo "Missing setup runtime helper: $ROOT/scripts/setup-runtime.sh" >&2
  exit 1
fi
# shellcheck source=/dev/null
source "$ROOT/scripts/setup-runtime.sh"
choose_setup_options
persist_skill_selection
run_parallel_install
HARD_ENG_SKIP_NPM_INSTALL=1 HARD_ENG_SKIP_SUBMODULE_INIT=1 "$ROOT/scripts/install.sh"
echo "Hard Eng setup complete: $ROOT"

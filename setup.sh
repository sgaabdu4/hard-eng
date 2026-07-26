#!/bin/bash
set -eu
export PYTHONDONTWRITEBYTECODE=1

ROOT=$(cd "$(dirname "$0")" && pwd -P)
MODE=${1:-install}
PATH_ACTION=none

# shellcheck source=scripts/setup/common.sh
. "$ROOT/scripts/setup/common.sh"
# shellcheck source=scripts/setup/binaries.sh
. "$ROOT/scripts/setup/binaries.sh"
# shellcheck source=scripts/setup/npm-runtime.sh
. "$ROOT/scripts/setup/npm-runtime.sh"
# shellcheck source=scripts/setup/codex.sh
. "$ROOT/scripts/setup/codex.sh"
# shellcheck source=scripts/setup/claude.sh
. "$ROOT/scripts/setup/claude.sh"

install_tools() {
  need git
  need node
  need npm
  need python3
  need codex
  need curl
  need tar
  manifest validate >/dev/null
  install_managed_directories
  install_npm_runtime
  install_binary_pins
  install_codex_integration
  install_claude_integration
}

check_tools() {
  local command_name
  for command_name in git node npm python3 codex curl tar rtk jq; do
    need "$command_name"
  done
  manifest validate >/dev/null
  check_managed_directories
  check_npm_runtime
  check_codebase_memory_cli
  context-mode --help >/dev/null
  ctx7 --help >/dev/null
  rtk --version >/dev/null
  check_binary_pins
  check_codex_integration
  check_claude_integration
}

check_design_contract() {
  local temporary
  temporary=$(setup_scratch_dir design-check)
  if ! npm_config_cache="$temporary" npm_config_update_notifier=false \
    node "$ROOT/skills/deterministic-checks/scripts/check-design-md.js"; then
    safe_remove_scratch_tree "$temporary"
    return 1
  fi
  safe_remove_scratch_tree "$temporary"
}

case "$MODE" in
  install)
    "$ROOT/scripts/setup/path.sh" preflight
    install_tools
    "$ROOT/scripts/git-hooks/install.sh" install
    PATH_ACTION=install
    ;;
  check)
    "$ROOT/scripts/git-hooks/install.sh" check
    PATH_ACTION=check
    ;;
  update)
    shift
    python3 "$ROOT/scripts/setup/update.py" "$@"
    exit
    ;;
  binary-check)
    check_binary_pins
    exit
    ;;
  npm-tree-check)
    verify_npm_tree "$2" "$3" "$4" "$5"
    exit
    ;;
  npm-archive-check)
    [ -f "$2" ] && [ "$(sha512 "$2")" = "$3" ]
    exit
    ;;
  *)
    printf 'usage: %s [install|check|update <reviewed-manifest.json>|binary-check|npm-tree-check|npm-archive-check]\n' \
      "$0" >&2
    exit 2
    ;;
esac

check_tools
python3 "$ROOT/skills/deterministic-checks/scripts/bounded_run.py" \
  --timeout 600 -- python3 "$ROOT/scripts/check-skill-contracts.py"
check_design_contract
node "$ROOT/scripts/check-managed-skills.js"
"$ROOT/scripts/setup/path.sh" "$PATH_ACTION"
printf 'setup: PASS\n'

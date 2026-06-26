#!/usr/bin/env bash
set -euo pipefail

mode="repair"
install_deps=0
require_pre_push=0
quiet=0
targets=()

usage() {
  cat <<'EOF'
Usage: ensure-worktree-ready.sh [--check] [--install] [--require-pre-push] [repo...]

Repairs or verifies portable Git hook readiness for a checkout/worktree.

Default behavior:
- no-op for repos without project hook managers
- reject private or no-mistakes-owned hook paths
- enforce portable relative hook paths for known managers
- generate missing Husky shim files with npm run prepare when Husky owns hooks
- fail closed if hooks cannot be activated

Flags:
  --check             Verify only; do not change config or generated files.
  --install           If Husky prepare cannot run because deps are missing, run npm ci first.
  --require-pre-push  Fail when a managed-hook repo has no pre-push hook.
  --quiet             Print only errors.
EOF
}

log() {
  if [[ "$quiet" != "1" ]]; then
    printf '%s\n' "$*"
  fi
}

fail() {
  printf 'ensure-worktree-ready: %s\n' "$*" >&2
  return 1
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --check)
      mode="check"
      ;;
    --install)
      install_deps=1
      ;;
    --require-pre-push)
      require_pre_push=1
      ;;
    --quiet)
      quiet=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      while [[ "$#" -gt 0 ]]; do
        targets+=("$1")
        shift
      done
      break
      ;;
    -*)
      fail "unknown flag: $1"
      exit 2
      ;;
    *)
      targets+=("$1")
      ;;
  esac
  shift
done

if [[ "${#targets[@]}" -eq 0 ]]; then
  targets=(".")
fi
initial_cwd="$(pwd)"

detect_hook_owner() {
  if [[ -f ".husky/pre-push" || -f ".husky/pre-commit" ]]; then
    printf '%s\n' "husky:.husky/_"
    return 0
  fi
  if [[ -f package.json ]] &&
    grep -Eq '"prepare"[[:space:]]*:[[:space:]]*"[^"]*husky|"(devDependencies|dependencies)"[[:space:]]*:' package.json &&
    grep -Eq '"husky"' package.json; then
    printf '%s\n' "husky:.husky/_"
    return 0
  fi
  if [[ -d ".githooks" ]]; then
    printf '%s\n' "generic:.githooks"
    return 0
  fi
  if [[ -d ".git-hooks" ]]; then
    printf '%s\n' "generic:.git-hooks"
    return 0
  fi
  if [[ -f "lefthook.yml" || -f "lefthook.yaml" ]]; then
    printf '%s\n' "external:"
    return 0
  fi
  if [[ -f "pre-commit-config.yaml" || -f ".pre-commit-config.yaml" ]]; then
    printf '%s\n' "external:"
    return 0
  fi
  return 1
}

hook_path_is_private_or_gate() {
  local value="$1"
  [[ "$value" == "$HOME"* ||
    "$value" == /Users/* ||
    "$value" == /home/* ||
    "$value" == *"/.no-mistakes/repos/"* ]]
}

set_hooks_path() {
  local repo="$1"
  local expected="$2"
  if git -C "$repo" config --get extensions.worktreeConfig 2>/dev/null | grep -qi '^true$'; then
    git -C "$repo" config --worktree core.hooksPath "$expected"
  elif git -C "$repo" config --worktree --get core.hooksPath >/dev/null 2>&1; then
    git -C "$repo" config --worktree core.hooksPath "$expected"
  else
    git -C "$repo" config --local core.hooksPath "$expected"
  fi
}

run_prepare() {
  local repo="$1"

  if [[ ! -f "$repo/package.json" ]]; then
    fail "$repo has Husky hooks but no package.json to run prepare"
    return 1
  fi
  if ! command -v npm >/dev/null 2>&1; then
    fail "npm is required to generate Husky shims in $repo"
    return 1
  fi

  if npm --prefix "$repo" run prepare --if-present; then
    return 0
  fi

  if [[ "$install_deps" != "1" ]]; then
    fail "npm prepare failed in $repo; rerun with --install after confirming dependency install is acceptable"
    return 1
  fi
  if [[ ! -f "$repo/package-lock.json" ]]; then
    fail "--install requires $repo/package-lock.json so dependency repair is reproducible"
    return 1
  fi

  npm --prefix "$repo" ci
  npm --prefix "$repo" run prepare --if-present
}

check_or_repair_repo() {
  local input="$1"
  local top current all_values shim owner owner_kind expected pre_push_hook

  if ! top="$(git -C "$input" rev-parse --show-toplevel 2>/dev/null)"; then
    fail "$input is not a Git checkout"
    return 1
  fi

  cd "$top"

  current="$(git config --get core.hooksPath 2>/dev/null || true)"
  if ! owner="$(detect_hook_owner)"; then
    current="$(git config --get core.hooksPath 2>/dev/null || true)"
    if [[ -n "$current" ]] && hook_path_is_private_or_gate "$current"; then
      fail "$top has private or gate-owned core.hooksPath and no detected project hook owner: $current"
      return 1
    fi
    log "worktree ready: $top (no project hook manager detected)"
    return 0
  fi
  owner_kind="${owner%%:*}"
  expected="${owner#*:}"

  if [[ "$owner_kind" == "external" ]]; then
    if [[ -n "$current" ]] && hook_path_is_private_or_gate "$current"; then
      fail "$top has private or gate-owned core.hooksPath with external hook manager; run the manager install command"
      return 1
    fi
    log "worktree ready: $top (external hook manager detected)"
    return 0
  fi

  pre_push_hook="$expected/pre-push"
  if [[ "$owner_kind" == "husky" ]]; then
    pre_push_hook=".husky/pre-push"
  fi

  if [[ "$require_pre_push" == "1" && ! -f "$pre_push_hook" ]]; then
    fail "$top has $owner_kind hooks but no $pre_push_hook gate"
    return 1
  fi

  if [[ "$current" != "$expected" ]]; then
    if [[ "$mode" == "check" ]]; then
      fail "$top core.hooksPath is ${current:-unset}; expected $expected"
      return 1
    fi
    set_hooks_path "$top" "$expected"
  fi

  current="$(git config --get core.hooksPath 2>/dev/null || true)"
  if [[ "$current" != "$expected" ]]; then
    fail "$top core.hooksPath is ${current:-unset}; expected $expected after repair"
    return 1
  fi

  all_values="$(git config --get-all core.hooksPath 2>/dev/null || true)"
  if printf '%s\n' "$all_values" | grep -Eq '/Users/|/home/|/\.no-mistakes/repos/'; then
    fail "$top still has private or gate-owned core.hooksPath entries"
    return 1
  fi

  if [[ "$owner_kind" == "husky" ]]; then
    shim=".husky/_/pre-push"
    if [[ ! -x "$shim" ]]; then
      if [[ "$mode" == "check" ]]; then
        fail "$top missing executable $shim"
        return 1
      fi
      run_prepare "$top"
    fi

    if [[ ! -x "$shim" ]]; then
      fail "$top missing executable $shim after prepare"
      return 1
    fi
    if [[ ! -f ".husky/_/h" ]]; then
      fail "$top missing .husky/_/h dispatcher"
      return 1
    fi
    if [[ -f ".husky/pre-push" ]] && ! grep -q 'pre-push' ".husky/_/pre-push"; then
      log "worktree ready: $top (Husky shim exists; wrapper format is version-owned)"
    else
      log "worktree ready: $top"
    fi
  else
    if [[ "$require_pre_push" == "1" && ! -x "$pre_push_hook" ]]; then
      fail "$top has non-executable $pre_push_hook"
      return 1
    fi
    log "worktree ready: $top"
  fi
}

status=0
for target in "${targets[@]}"; do
  case "$target" in
    /*)
      resolved_target="$target"
      ;;
    *)
      resolved_target="$initial_cwd/$target"
      ;;
  esac
  if ! check_or_repair_repo "$resolved_target"; then
    status=1
  fi
done

exit "$status"

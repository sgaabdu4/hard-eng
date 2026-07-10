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
  --require-pre-push  Require an executable pre-push hook valid for its detected owner.
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

resolved_existing_path() {
  local value="$1"
  local directory
  directory="$(cd -P "$(dirname "$value")" 2>/dev/null && pwd -P)" || return 1
  printf '%s/%s\n' "$directory" "$(basename "$value")"
}

validate_executable_hook_path() {
  local repo="$1"
  local hook="$2"
  local owner="$3"
  local hook_real owner_real
  if [[ -L "$hook" ]]; then
    fail "$repo pre-push hook must not be a symlink: $hook"
    return 1
  fi
  if [[ ! -f "$hook" || ! -x "$hook" ]]; then
    fail "$repo pre-push hook is missing or not executable: ${hook:-unknown}"
    return 1
  fi
  hook_real="$(resolved_existing_path "$hook")" || return 1
  owner_real="$(cd -P "$owner" 2>/dev/null && pwd -P)" || return 1
  case "$hook_real" in
    "$owner_real"/*) ;;
    *)
      fail "$repo pre-push hook resolves outside its declared owner $owner: $hook_real"
      return 1
      ;;
  esac
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
    printf '%s\n' "external-lefthook:"
    return 0
  fi
  if [[ -f "pre-commit-config.yaml" || -f ".pre-commit-config.yaml" ]]; then
    printf '%s\n' "external-pre-commit:"
    return 0
  fi
  return 1
}

is_no_mistakes_gate_worktree() {
  local repo="$1"
  local hook_path="$2"
  [[ "$repo" == *"/.no-mistakes/worktrees/"* &&
    "$hook_path" == *"/.no-mistakes/repos/"*"/hooks" ]]
}

validate_no_mistakes_gate_pre_push() {
  local repo="$1"
  local hook executable_text

  hook="$(git rev-parse --git-path hooks/pre-push 2>/dev/null || true)"
  validate_executable_hook_path "$repo" "$hook" "$(dirname "$hook")" || return 1
  if grep -q 'Managed by hard-eng installer' "$hook"; then
    if grep -Fq 'if [[ "$(basename "$repo")" != ".agents" ]]; then' "$hook"; then
      fail "$repo no-mistakes gate pre-push hook exits before checking ID-named gate worktrees: $hook"
      return 1
    fi
    executable_text="$(sed -E '/^[[:space:]]*#/d; s/[[:space:]]+#.*$//; /^[[:space:]]*$/d' "$hook")"
    printf '%s\n' "$executable_text" | grep -Eq '^[[:space:]]*repo="\$\(git rev-parse --show-toplevel\)"[[:space:]]*$' || {
      fail "$repo managed no-mistakes gate pre-push hook lacks a bound repo root: $hook"
      return 1
    }
    for required in \
      'node "$repo/scripts/format-hard-eng.mjs" --check "$repo"' \
      'node "$repo/scripts/check-no-mistakes-projects.mjs" "$repo"' \
      'node "$repo/scripts/check-project-quality-gates.mjs" --require-push-gate "$repo"'
    do
      printf '%s\n' "$executable_text" | grep -Fqx "$required" || {
        fail "$repo managed no-mistakes gate pre-push hook lacks root-bound command: $required"
        return 1
      }
    done
  fi
}

hook_path_is_private_or_gate() {
  local value="$1"
  [[ "$value" == "$HOME"* ||
    "$value" == /Users/* ||
    "$value" == /home/* ||
    "$value" == *"/.no-mistakes/repos/"* ]]
}

pre_commit_config_has_pre_push() {
  local config="$1"
  awk '
    function indentation(line, prefix) {
      prefix = line
      sub(/[^ ].*$/, "", prefix)
      return length(prefix)
    }
    BEGIN { active = 0; key_indent = -1; found = 0 }
    {
      line = $0
      sub(/[[:space:]]+#.*$/, "", line)
      trimmed = line
      sub(/^[ ]*/, "", trimmed)
      if (trimmed == "" || trimmed ~ /^#/) next
      indent = indentation(line)
      if (active && indent > key_indent && trimmed ~ /^-[[:space:]]*pre-push[[:space:]]*$/) {
        found = 1
        exit
      }
      if (active && indent <= key_indent) active = 0
      if (trimmed ~ /^(default_stages|stages)[[:space:]]*:/) {
        value = trimmed
        sub(/^[^:]*:[[:space:]]*/, "", value)
        if (value ~ /(^|[^[:alnum:]_-])pre-push([^[:alnum:]_-]|$)/) {
          found = 1
          exit
        }
        active = 1
        key_indent = indent
      }
    }
    END { exit(found ? 0 : 1) }
  ' "$config"
}

external_manager_hook_installed() {
  local owner_kind="$1"
  local hook="$2"
  local config executable_text selected

  executable_text="$(sed -E '/^[[:space:]]*#/d; s/[[:space:]]+#.*$//; /^[[:space:]]*$/d' "$hook")"

  if [[ "$owner_kind" == "external-lefthook" ]]; then
    selected="$(printf '%s\n' "$executable_text" | sed -nE 's/.*lefthook[^#]*(--config|--file|-f)(=|[[:space:]]+)([^[:space:]]+).*/\3/p' | head -n 1)"
    selected="${selected#\"}"; selected="${selected%\"}"; selected="${selected#\'}"; selected="${selected%\'}"
    config="${selected:-lefthook.yml}"
    [[ -n "$selected" || -f "$config" ]] || config="lefthook.yaml"
    [[ "$config" != /* && "$config" != .. && "$config" != ../* && -f "$config" ]] || return 1
    printf '%s\n' "$executable_text" | grep -Eqi '(^|[^[:alnum:]_-])lefthook([^[:alnum:]_-]|$).*run[[:space:]]+pre-push([[:space:]]|$)' &&
      sed -E '/^[[:space:]]*#/d' "$config" | grep -Eq '^[[:space:]]*pre-push[[:space:]]*:'
    return
  fi
  selected="$(printf '%s\n' "$executable_text" | sed -nE 's/.*(pre-commit|pre_commit)[^#]*(--config|-c)(=|[[:space:]]+)([^[:space:]]+).*/\4/p' | head -n 1)"
  selected="${selected#\"}"; selected="${selected%\"}"; selected="${selected#\'}"; selected="${selected%\'}"
  config="${selected:-.pre-commit-config.yaml}"
  [[ -n "$selected" || -f "$config" ]] || config="pre-commit-config.yaml"
  [[ "$config" != /* && "$config" != .. && "$config" != ../* && -f "$config" ]] || return 1
  printf '%s\n' "$executable_text" | grep -Eqi '(^|[^[:alnum:]_-])pre-commit([^[:alnum:]_-]|$)|pre_commit' &&
    printf '%s\n' "$executable_text" | grep -Eqi 'hook-impl' &&
    printf '%s\n' "$executable_text" | grep -Eqi 'hook-type[= ]pre-push' &&
    pre_commit_config_has_pre_push "$config"
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
  if is_no_mistakes_gate_worktree "$top" "$current"; then
    validate_no_mistakes_gate_pre_push "$top" || return 1
    log "worktree ready: $top (active no-mistakes gate pre-push hook verified)"
    return 0
  fi
  if ! owner="$(detect_hook_owner)"; then
    current="$(git config --get core.hooksPath 2>/dev/null || true)"
    if [[ -n "$current" ]] && hook_path_is_private_or_gate "$current"; then
      fail "$top has private or gate-owned core.hooksPath and no detected project hook owner: $current"
      return 1
    fi
    if [[ "$require_pre_push" == "1" ]]; then
      pre_push_hook="$(git rev-parse --git-path hooks/pre-push 2>/dev/null || true)"
      validate_executable_hook_path "$top" "$pre_push_hook" "$(dirname "$pre_push_hook")" || return 1
    fi
    log "worktree ready: $top (no project hook manager detected)"
    return 0
  fi
  owner_kind="${owner%%:*}"
  expected="${owner#*:}"

  if [[ "$owner_kind" == external-* ]]; then
    if [[ -n "$current" ]] && hook_path_is_private_or_gate "$current"; then
      fail "$top has private or gate-owned core.hooksPath with external hook manager; run the manager install command"
      return 1
    fi
    if [[ "$require_pre_push" == "1" ]]; then
      pre_push_hook="$(git rev-parse --git-path hooks/pre-push 2>/dev/null || true)"
      validate_executable_hook_path "$top" "$pre_push_hook" "$(dirname "$pre_push_hook")" || return 1
      if ! external_manager_hook_installed "$owner_kind" "$pre_push_hook"; then
        fail "$top effective pre-push hook is not installed by ${owner_kind#external-}: $pre_push_hook"
        return 1
      fi
    fi
    log "worktree ready: $top (external hook manager detected)"
    return 0
  fi

  pre_push_hook="$expected/pre-push"
  if [[ "$owner_kind" == "husky" ]]; then
    pre_push_hook=".husky/pre-push"
  fi

  if [[ "$require_pre_push" == "1" ]]; then
    validate_executable_hook_path "$top" "$pre_push_hook" "${pre_push_hook%/pre-push}" || return 1
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
    if [[ -L "$shim" || ! -x "$shim" ]]; then
      if [[ "$mode" == "check" ]]; then
        fail "$top missing executable $shim"
        return 1
      fi
      run_prepare "$top"
    fi

    if [[ -L "$shim" || ! -x "$shim" ]]; then
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

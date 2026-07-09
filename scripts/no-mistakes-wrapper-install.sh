#!/usr/bin/env bash

resolve_wrapper_symlink_target() {
  local link_path="$1"
  local target target_dir

  target="$(readlink "$link_path")"
  case "$target" in
    /*) printf '%s\n' "$target" ;;
    *)
      target_dir="$(cd "$(dirname "$link_path")" >/dev/null 2>&1 && pwd -P)" || return 1
      printf '%s\n' "$target_dir/$target"
      ;;
  esac
}

infer_no_mistakes_home_from_binary() {
  local binary="$1"
  local nm_home

  case "$binary" in
    */bin/no-mistakes)
      nm_home="$(cd "$(dirname "$binary")/.." >/dev/null 2>&1 && pwd -P)" || return 1
      is_known_no_mistakes_home "$nm_home" || return 1
      printf '%s\n' "$nm_home"
      ;;
    *) return 1 ;;
  esac
}

no_mistakes_home_matches() {
  local candidate="$1"
  local expected="$2"
  local resolved

  [[ -n "$expected" ]] || return 1
  resolved="$(cd "$expected" >/dev/null 2>&1 && pwd -P)" || return 1
  [[ "$candidate" == "$resolved" ]]
}

is_known_no_mistakes_home() {
  local nm_home="$1"

  if no_mistakes_home_matches "$nm_home" "${NO_MISTAKES_HOME:-}"; then
    return 0
  fi
  if no_mistakes_home_matches "$nm_home" "${HOME:-}/.no-mistakes"; then
    return 0
  fi
  [[ "$(basename "$nm_home")" == ".no-mistakes" ]]
}

is_managed_no_mistakes_wrapper() {
  local wrapper_path="$1"

  [[ -f "$wrapper_path" ]] || return 1
  grep -q 'Managed by hard-eng no-mistakes wrapper' "$wrapper_path" 2>/dev/null
}

no_mistakes_wrapper_uses_configured_real_binary() {
  if [[ -n "${HARD_ENG_NO_MISTAKES_REAL_BIN:-}" ]]; then
    return 0
  fi
  if [[ -n "${HARD_ENG_NO_MISTAKES_HOME_CONFIGURED+x}" ]]; then
    [[ "${HARD_ENG_NO_MISTAKES_HOME_CONFIGURED:-0}" == "1" ]]
    return
  fi
  [[ -n "${NO_MISTAKES_HOME:-}" ]]
}

resolve_no_mistakes_command_binary() {
  local command_path="$1"
  local resolved embedded_binary

  if is_managed_no_mistakes_wrapper "$command_path" &&
    embedded_binary="$(read_no_mistakes_wrapper_assignment "$command_path" HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN)" &&
    [[ -x "$embedded_binary" ]]; then
    printf '%s\n' "$embedded_binary"
    return 0
  fi
  if [[ -L "$command_path" ]]; then
    resolved="$(resolve_wrapper_symlink_target "$command_path")" || return 1
    if [[ -x "$resolved" ]]; then
      printf '%s\n' "$resolved"
      return 0
    fi
  fi
  [[ -x "$command_path" ]] || return 1
  printf '%s\n' "$command_path"
}

decode_no_mistakes_wrapper_value() {
  local encoded="$1"
  local out="" char
  local i=0
  local len="${#encoded}"

  if [[ "$encoded" == "''" ]]; then
    printf '\n'
    return 0
  fi
  case "$encoded" in
    \$\'*) return 1 ;;
  esac
  while ((i < len)); do
    char="${encoded:i:1}"
    if [[ "$char" == "\\" ]]; then
      ((i += 1))
      if ((i >= len)); then
        return 1
      fi
      out+="${encoded:i:1}"
    else
      out+="$char"
    fi
    ((i += 1))
  done
  printf '%s\n' "$out"
}

read_no_mistakes_wrapper_assignment() {
  local wrapper="$1"
  local name="$2"
  local line

  [[ -f "$wrapper" ]] || return 1
  while IFS= read -r line; do
    case "$line" in
      "$name"=*)
        if decode_no_mistakes_wrapper_value "${line#*=}"; then
          return 0
        fi
        return 1
        ;;
    esac
  done <"$wrapper"
  return 1
}

write_no_mistakes_wrapper() {
  local source="$1"
  local target="$2"
  local nm_home="$3"
  local hard_eng_home="$4"
  local real_binary="$5"
  local target_dir tmp shebang

  target_dir="$(dirname "$target")"
  mkdir -p "$target_dir"
  tmp="$(mktemp "$target_dir/.no-mistakes-wrapper.XXXXXX")"
  IFS= read -r shebang <"$source"
  {
    printf '%s\n' "$shebang"
    printf 'HARD_ENG_NO_MISTAKES_DEFAULT_NM_HOME=%q\n' "$nm_home"
    printf 'HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN=%q\n' "$real_binary"
    printf 'HARD_ENG_DEFAULT_HOME=%q\n' "$hard_eng_home"
    tail -n +2 "$source"
  } >"$tmp"
  chmod 755 "$tmp"
  mv -f "$tmp" "$target"
}

normalize_no_mistakes_wrapper_path() {
  local wrapper_path="$1"
  local dir base

  dir="$(dirname "$wrapper_path")"
  base="$(basename "$wrapper_path")"
  dir="$(cd "$dir" >/dev/null 2>&1 && pwd -P)" || return 1
  printf '%s/%s\n' "$dir" "$base"
}

no_mistakes_wrapper_would_replace_real_binary() {
  local link_path="$1"
  local real_binary="$2"
  local normalized_link normalized_real

  normalized_link="$(normalize_no_mistakes_wrapper_path "$link_path")" || return 1
  normalized_real="$(normalize_no_mistakes_wrapper_path "$real_binary")" || return 1
  if [[ "$normalized_link" == "$normalized_real" ]]; then
    return 0
  fi
  if [[ ! -L "$link_path" && -e "$link_path" && -e "$real_binary" && "$link_path" -ef "$real_binary" ]]; then
    return 0
  fi
  return 1
}

install_no_mistakes_wrapper() {
  local link_path="$1"
  local real_binary="$2"
  local source="${3:-$ROOT/scripts/no-mistakes-wrapper.sh}"
  local nm_home="${4:-${NO_MISTAKES_HOME:-$HOME/.no-mistakes}}"
  local hard_eng_home="${5:-${HARD_ENG_HOME:-$ROOT}}"
  local target resolved inferred_home real_binary_configured wrapper_defaults_configured

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_WRAPPER:-}" == "1" ]]; then
    return 0
  fi
  if [[ ! -x "$source" ]]; then
    echo "Skipping no-mistakes wrapper install: $source is missing or not executable." >&2
    return 0
  fi
  mkdir -p "$(dirname "$link_path")"
  real_binary_configured=0
  wrapper_defaults_configured=0
  if [[ "$#" -ge 4 ]]; then
    wrapper_defaults_configured=1
  fi
  if [[ "$wrapper_defaults_configured" == "1" ]] ||
    no_mistakes_wrapper_uses_configured_real_binary; then
    real_binary_configured=1
  fi
  if [[ "$real_binary_configured" != "1" ]] &&
    inferred_home="$(infer_no_mistakes_home_from_binary "$real_binary")"; then
    nm_home="$inferred_home"
  fi
  if [[ -L "$link_path" ]]; then
    target="$(readlink "$link_path")"
    resolved="$(resolve_wrapper_symlink_target "$link_path" || printf '%s\n' "$target")"
    if [[ "$target" != "$real_binary" &&
      "$target" != "$source" &&
      "$resolved" != "$real_binary" &&
      "$resolved" != "$source" ]]; then
      if [[ -x "$resolved" && "$(basename "$resolved")" == "no-mistakes" ]]; then
        if [[ "$real_binary_configured" != "1" || ! -x "$real_binary" ]]; then
          real_binary="$resolved"
          if inferred_home="$(infer_no_mistakes_home_from_binary "$resolved")"; then
            nm_home="$inferred_home"
          fi
        fi
      else
        echo "Preserving existing no-mistakes symlink: $link_path"
        return 0
      fi
    fi
  elif [[ -e "$link_path" ]] &&
    ! is_managed_no_mistakes_wrapper "$link_path" &&
    [[ "${HARD_ENG_REPLACE_NO_MISTAKES_COMMAND:-0}" != "1" ]]; then
    echo "Preserving existing no-mistakes executable: $link_path"
    return 0
  fi
  if no_mistakes_wrapper_would_replace_real_binary "$link_path" "$real_binary"; then
    echo "Refusing no-mistakes wrapper install because link path would replace real binary: $link_path" >&2
    return 1
  fi
  write_no_mistakes_wrapper "$source" "$link_path" "$nm_home" "$hard_eng_home" "$real_binary"
}

refresh_no_mistakes_wrapper() {
  local nm_home="${NO_MISTAKES_HOME:-$HOME/.no-mistakes}"
  local link_dir="${NO_MISTAKES_LINK_DIR:-$HOME/.local/bin}"
  local link_path="$link_dir/no-mistakes"
  local real_binary="${HARD_ENG_NO_MISTAKES_REAL_BIN:-$nm_home/bin/no-mistakes}"
  local source="$ROOT/scripts/no-mistakes-wrapper.sh"
  local hard_eng_home="${HARD_ENG_HOME:-$ROOT}"
  local target resolved inferred_home embedded_home embedded_binary embedded_hard_eng_home real_binary_configured command_path command_binary

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_WRAPPER:-}" == "1" ]]; then
    return 0
  fi
  real_binary_configured=0
  if no_mistakes_wrapper_uses_configured_real_binary; then
    real_binary_configured=1
  fi
  if is_managed_no_mistakes_wrapper "$link_path"; then
    if [[ -z "${HARD_ENG_HOME:-}" ]] &&
      embedded_hard_eng_home="$(read_no_mistakes_wrapper_assignment "$link_path" HARD_ENG_DEFAULT_HOME)"; then
      hard_eng_home="$embedded_hard_eng_home"
    fi
    if [[ "$real_binary_configured" != "1" ]] &&
      embedded_binary="$(read_no_mistakes_wrapper_assignment "$link_path" HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN)" &&
      [[ -x "$embedded_binary" ]]; then
      real_binary="$embedded_binary"
      if embedded_home="$(read_no_mistakes_wrapper_assignment "$link_path" HARD_ENG_NO_MISTAKES_DEFAULT_NM_HOME)"; then
        nm_home="$embedded_home"
      elif inferred_home="$(infer_no_mistakes_home_from_binary "$embedded_binary")"; then
        nm_home="$inferred_home"
      fi
    fi
  fi
  if [[ -L "$link_path" ]]; then
    target="$(readlink "$link_path")"
    resolved="$(resolve_wrapper_symlink_target "$link_path" || printf '%s\n' "$target")"
    if [[ -x "$resolved" && "$(basename "$resolved")" == "no-mistakes" ]]; then
      if [[ "$real_binary_configured" != "1" || ! -x "$real_binary" ]]; then
        real_binary="$resolved"
        if inferred_home="$(infer_no_mistakes_home_from_binary "$resolved")"; then
          nm_home="$inferred_home"
        fi
      fi
    fi
  fi
  if [[ "$real_binary_configured" != "1" && ! -x "$real_binary" ]] &&
    command_path="$(command -v no-mistakes 2>/dev/null)" &&
    [[ -n "$command_path" ]]; then
    if command_binary="$(resolve_no_mistakes_command_binary "$command_path")" &&
      [[ -x "$command_binary" && "$command_binary" != "$link_path" && "$(basename "$command_binary")" == "no-mistakes" ]]; then
      real_binary="$command_binary"
      if inferred_home="$(infer_no_mistakes_home_from_binary "$command_binary")"; then
        nm_home="$inferred_home"
      fi
    fi
  fi
  [[ -x "$real_binary" ]] || return 0
  install_no_mistakes_wrapper "$link_path" "$real_binary" "$source" "$nm_home" "$hard_eng_home"
}

refresh_no_mistakes_agent_paths() {
  local nm_home="${NO_MISTAKES_HOME:-$HOME/.no-mistakes}"
  local binary="${HARD_ENG_CODEX_BIN:-}"
  local candidate

  if [[ -z "$binary" ]] && command -v codex >/dev/null 2>&1; then
    binary="$(command -v codex)"
  fi
  if [[ -z "$binary" || ! -x "$binary" ]]; then
    for candidate in "$HOME/.npm-global/bin/codex" "$HOME/.local/bin/codex" "/Applications/Codex.app/Contents/Resources/codex"; do
      if [[ -x "$candidate" ]]; then
        binary="$candidate"
        break
      fi
    done
  fi
  [[ -x "$binary" ]] || return 0
  node "$ROOT/scripts/refresh-no-mistakes-agent-paths.mjs" \
    --config "$nm_home/config.yaml" \
    --agent codex \
    --binary "$binary"
}

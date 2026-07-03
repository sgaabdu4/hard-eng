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
      printf '%s\n' "$nm_home"
      ;;
    *) return 1 ;;
  esac
}

is_managed_no_mistakes_wrapper() {
  local path="$1"

  [[ -f "$path" ]] || return 1
  grep -q 'Managed by hard-eng no-mistakes wrapper' "$path" 2>/dev/null
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
  local tmp shebang

  tmp="$(mktemp "${TMPDIR:-/tmp}/hard-eng-no-mistakes-wrapper.XXXXXX")"
  IFS= read -r shebang <"$source"
  {
    printf '%s\n' "$shebang"
    printf 'HARD_ENG_NO_MISTAKES_DEFAULT_NM_HOME=%q\n' "$nm_home"
    printf 'HARD_ENG_NO_MISTAKES_DEFAULT_REAL_BIN=%q\n' "$real_binary"
    printf 'HARD_ENG_DEFAULT_HOME=%q\n' "$hard_eng_home"
    tail -n +2 "$source"
  } >"$tmp"
  mv "$tmp" "$target"
  chmod 755 "$target"
}

install_no_mistakes_wrapper() {
  local link_path="$1"
  local real_binary="$2"
  local source="${3:-$ROOT/scripts/no-mistakes-wrapper.sh}"
  local nm_home="${4:-${NO_MISTAKES_HOME:-$HOME/.no-mistakes}}"
  local hard_eng_home="${5:-${HARD_ENG_HOME:-$ROOT}}"
  local target resolved inferred_home

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_WRAPPER:-}" == "1" ]]; then
    return 0
  fi
  if [[ ! -x "$source" ]]; then
    echo "Skipping no-mistakes wrapper install: $source is missing or not executable." >&2
    return 0
  fi
  mkdir -p "$(dirname "$link_path")"
  if [[ -L "$link_path" ]]; then
    target="$(readlink "$link_path")"
    resolved="$(resolve_wrapper_symlink_target "$link_path" || printf '%s\n' "$target")"
    if [[ "$target" != "$real_binary" &&
      "$target" != "$source" &&
      "$resolved" != "$real_binary" &&
      "$resolved" != "$source" ]]; then
      if [[ ! -x "$real_binary" &&
        -x "$resolved" ]] &&
        inferred_home="$(infer_no_mistakes_home_from_binary "$resolved")"; then
        real_binary="$resolved"
        nm_home="$inferred_home"
      else
        echo "Preserving existing no-mistakes symlink: $link_path"
        return 0
      fi
    fi
    rm -f "$link_path"
  elif [[ -e "$link_path" ]] &&
    ! is_managed_no_mistakes_wrapper "$link_path"; then
    echo "Preserving existing no-mistakes executable: $link_path"
    return 0
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
  local target resolved inferred_home embedded_home embedded_binary embedded_hard_eng_home

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_WRAPPER:-}" == "1" ]]; then
    return 0
  fi
  if is_managed_no_mistakes_wrapper "$link_path"; then
    if [[ -z "${HARD_ENG_HOME:-}" ]] &&
      embedded_hard_eng_home="$(read_no_mistakes_wrapper_assignment "$link_path" HARD_ENG_DEFAULT_HOME)"; then
      hard_eng_home="$embedded_hard_eng_home"
    fi
    if [[ -z "${NO_MISTAKES_HOME:-}" &&
      -z "${HARD_ENG_NO_MISTAKES_REAL_BIN:-}" ]] &&
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
  if [[ ! -x "$real_binary" ]]; then
    if [[ ! -L "$link_path" ]]; then
      return 0
    fi
    target="$(readlink "$link_path")"
    resolved="$(resolve_wrapper_symlink_target "$link_path" || printf '%s\n' "$target")"
    if [[ ! -x "$resolved" ]] || ! inferred_home="$(infer_no_mistakes_home_from_binary "$resolved")"; then
      return 0
    fi
    real_binary="$resolved"
    nm_home="$inferred_home"
  fi
  install_no_mistakes_wrapper "$link_path" "$real_binary" "$source" "$nm_home" "$hard_eng_home"
}

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
    ! grep -q 'Managed by hard-eng no-mistakes wrapper' "$link_path" 2>/dev/null; then
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
  local target resolved inferred_home

  if [[ "${HARD_ENG_SKIP_NO_MISTAKES_WRAPPER:-}" == "1" ]]; then
    return 0
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
  install_no_mistakes_wrapper "$link_path" "$real_binary" "$source" "$nm_home" "${HARD_ENG_HOME:-$ROOT}"
}

#!/bin/bash

SETUP_DIR=$ROOT/scripts/setup
MANIFEST_TOOL=$SETUP_DIR/manifest.py
BIN_DIR=$HOME/.local/bin
ASSET_DIR=$HOME/.local/share/hard-eng
STATE_DIR=$ASSET_DIR/state
PATH="$BIN_DIR:$PATH"
export PATH

setup_fail() {
  printf 'setup: %s\n' "$1" >&2
  return 1
}

need() {
  command -v "$1" >/dev/null 2>&1 ||
    setup_fail "missing required command: $1"
}

check_managed_directories() {
  local directory
  for directory in "$BIN_DIR" "$ASSET_DIR"; do
    [ -d "$directory" ] && [ ! -L "$directory" ] ||
      { setup_fail "managed root is not a regular directory: $directory"; return 1; }
  done
}

install_managed_directories() {
  local directory
  for directory in "$BIN_DIR" "$ASSET_DIR"; do
    if [ -L "$directory" ] || { [ -e "$directory" ] && [ ! -d "$directory" ]; }; then
      setup_fail "managed root conflicts with user-owned state: $directory"
      return 1
    fi
  done
  mkdir -p "$BIN_DIR" "$ASSET_DIR"
  check_managed_directories
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

sha512() {
  if command -v sha512sum >/dev/null 2>&1; then
    sha512sum "$1" | awk '{print $1}'
  else
    shasum -a 512 "$1" | awk '{print $1}'
  fi
}

setup_platform() {
  local os arch
  os=$(uname -s)
  arch=$(uname -m)
  case "$os:$arch" in
    Darwin:arm64) printf 'macos-arm64\n' ;;
    Darwin:x86_64) printf 'macos-amd64\n' ;;
    Linux:aarch64|Linux:arm64) printf 'linux-arm64\n' ;;
    Linux:x86_64|Linux:amd64) printf 'linux-amd64\n' ;;
    *) setup_fail "unsupported platform: $os:$arch" ;;
  esac
}

manifest() {
  python3 "$MANIFEST_TOOL" "$@"
}

safe_remove_setup_tree() {
  local target parent name
  target=$1
  parent=$(dirname "$target")
  name=$(basename "$target")
  [ "$parent" = "$ASSET_DIR" ] ||
    { setup_fail "refusing to remove unexpected path: $target"; return 1; }
  case "$name" in
    .hard-eng-*) rm -rf -- "$target" ;;
    *) setup_fail "refusing to remove unexpected path: $target" ;;
  esac
}

setup_scratch_dir() {
  local prefix root
  prefix=$1
  root=$(setup_scratch_root) || return 1
  mktemp -d "$root/.hard-eng-$prefix.XXXXXX"
}

setup_scratch_file() {
  local prefix root
  prefix=$1
  root=$(setup_scratch_root) || return 1
  mktemp "$root/.hard-eng-$prefix.XXXXXX"
}

setup_scratch_root() {
  local root
  root=${TMPDIR:-/tmp}
  case "$root" in /*) ;; *) setup_fail "temporary directory must be absolute: $root"; return 1 ;; esac
  [ -d "$root" ] || { setup_fail "temporary directory missing: $root"; return 1; }
  root=$(cd "$root" && pwd -P) || return 1
  [ "$root" != / ] ||
    { setup_fail "temporary directory cannot be the filesystem root"; return 1; }
  root=${root%/}
  printf '%s\n' "$root"
}

safe_remove_scratch_tree() {
  local target root parent name
  target=$1
  root=$(setup_scratch_root) || return 1
  parent=$(dirname "$target")
  name=$(basename "$target")
  [ "$parent" = "$root" ] ||
    { setup_fail "refusing to remove unexpected scratch path: $target"; return 1; }
  case "$name" in
    .hard-eng-*) rm -rf -- "$target" ;;
    *) setup_fail "refusing to remove unexpected scratch path: $target" ;;
  esac
}

atomic_write_text() {
  local destination content mode directory temporary
  destination=$1
  content=$2
  mode=${3:-600}
  directory=$(dirname "$destination")
  if [ -L "$directory" ] || { [ -e "$directory" ] && [ ! -d "$directory" ]; }; then
    setup_fail "managed state owner is not a directory: $directory"
    return 1
  fi
  mkdir -p "$directory"
  [ -d "$directory" ] && [ ! -L "$directory" ] ||
    { setup_fail "managed state owner is not a directory: $directory"; return 1; }
  chmod 700 "$directory"
  temporary=$(mktemp "$directory/.hard-eng-state.XXXXXX")
  if ! printf '%s\n' "$content" >"$temporary" ||
    ! chmod "$mode" "$temporary" ||
    ! mv -f "$temporary" "$destination"; then
    rm -f -- "$temporary"
    setup_fail "could not write managed state: $destination"
    return 1
  fi
}

canonical_command() {
  local name expected resolved
  name=$1
  expected=$2
  resolved=$(command -v "$name" || true)
  [ -n "$resolved" ] && [ -x "$expected" ] || return 1
  [ "$resolved" -ef "$expected" ]
}

verified_download_to() {
  local url expected destination mode directory temporary actual
  url=$1
  expected=$2
  destination=$3
  mode=${4:-644}
  directory=$(dirname "$destination")
  mkdir -p "$directory"
  temporary=$(mktemp "$directory/.hard-eng-download.XXXXXX")
  if ! curl -fsSL "$url" -o "$temporary"; then
    rm -f -- "$temporary"
    setup_fail "download failed: $url"
    return 1
  fi
  actual=$(sha256 "$temporary")
  if [ "$actual" != "$expected" ]; then
    rm -f -- "$temporary"
    setup_fail "checksum mismatch: $url"
    return 1
  fi
  if ! chmod "$mode" "$temporary" || ! mv -f "$temporary" "$destination"; then
    rm -f -- "$temporary"
    setup_fail "could not activate verified download: $destination"
    return 1
  fi
}

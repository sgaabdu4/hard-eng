#!/bin/bash
set -eu

ROOT=$(cd "$(dirname "$0")" && pwd -P)
MODE=${1:-install}
BIN_DIR=$HOME/.local/bin
ASSET_DIR=$HOME/.local/share/hard-eng
NPM_PACKAGES='codebase-memory-mcp@0.8.1 context-mode@1.0.168 ctx7@0.5.4'
NPM_SPEC_DIR=$ROOT/runtime/npm
NPM_RUNTIME_DIR=$ASSET_DIR/npm-runtime
NPM_RUNTIME_MARKER=$ASSET_DIR/npm-runtime-$(uname -s)-$(uname -m).sha256
RTK_VERSION=0.43.0
JQ_VERSION=1.7.1
JQ_BIN=$BIN_DIR/jq
RTK_BIN=$BIN_DIR/rtk
PATH="$BIN_DIR:$PATH"
export PATH

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'setup: missing required command: %s\n' "$1" >&2
    return 1
  }
}

npm_sum() {
  case $1 in
    codebase-memory-mcp@0.8.1) printf '%s' 41452a50bd422d3d5eb8b436788ea47edfad6662280b4c19c690add81f38e339f33a4f747e60d925b4fccfb79cdfaeb98a6b21373020ed2cdd97dbd8368c67fb ;;
    context-mode@1.0.168) printf '%s' b61ab324b0150bc6b85f35576089381c6e476bddb98ec26bb36bd3f1df229f11b9dfb8e22cfd424ff049cd621b9e2a66dd73d138291719f2037bd3ecc6a119e2 ;;
    ctx7@0.5.4) printf '%s' 0380e9fafb4ddf2ad8ac1f4ceccc59fffa138e7e63c08b224e3d9afd1f52cea63b782773fab897784d9633d904908bf96dc8cec15739a02a9215944f7cefd35e ;;
    *) return 1 ;;
  esac
}

npm_archive_path() {
  local command_name package
  command_name=$1
  package=$2
  printf '%s/npm-%s-%s.tgz\n' "$ASSET_DIR" "$command_name" "${package##*@}"
}

ensure_npm_archive() {
  local command_name package expected archive temporary
  command_name=$1
  package=$2
  expected=$3
  archive=$(npm_archive_path "$command_name" "$package")
  if [ -f "$archive" ] && [ "$(sha512 "$archive")" = "$expected" ]; then
    printf '%s\n' "$archive"
    return
  fi
  temporary=$(mktemp -d)
  npm pack "$package" --pack-destination "$temporary" >/dev/null 2>&1
  set -- "$temporary"/*.tgz
  if [ "$#" -ne 1 ] || [ ! -f "$1" ] || [ "$(sha512 "$1")" != "$expected" ]; then
    rm -rf "$temporary"
    printf 'setup: npm archive checksum mismatch: %s\n' "$package" >&2
    return 1
  fi
  mkdir -p "$ASSET_DIR"
  install -m 644 "$1" "$archive"
  rm -rf "$temporary"
  printf '%s\n' "$archive"
}

verify_npm_tree() {
  local archive expected installed exclusions temporary matched exclusion
  archive=$1
  expected=$2
  installed=$3
  exclusions=$4
  [ -f "$archive" ] && [ -d "$installed" ] && [ "$(sha512 "$archive")" = "$expected" ] || return 1
  temporary=$(mktemp -d)
  tar -xzf "$archive" -C "$temporary"
  set --
  for exclusion in $exclusions; do
    [ "$exclusion" = none ] || set -- "$@" -x "$exclusion"
  done
  if diff -qr "$@" "$temporary/package" "$installed" >/dev/null 2>&1; then matched=0; else matched=$?; fi
  rm -rf "$temporary"
  return "$matched"
}

runtime_tree_digest() {
  python3 "$ROOT/scripts/runtime-tree-digest.py" "$1"
}

runtime_lock_digest() {
  sha256 "$NPM_SPEC_DIR/package-lock.json"
}

link_npm_runtime() {
  local command_name
  mkdir -p "$BIN_DIR"
  for command_name in codebase-memory-mcp context-mode ctx7; do
    ln -sfn "$NPM_RUNTIME_DIR/node_modules/.bin/$command_name" "$BIN_DIR/$command_name"
  done
}

install_npm_runtime() {
  local package command_name temporary digest
  [ "$(node -p 'Number(process.versions.node.split(`.`)[0]) >= 22')" = true ] || {
    printf 'setup: Node.js 22+ is required for the script-free CLI runtime\n' >&2
    return 1
  }
  for package in $NPM_PACKAGES; do
    command_name=${package%@*}
    ensure_npm_archive "$command_name" "$package" "$(npm_sum "$package")" >/dev/null
  done
  temporary=$(mktemp -d)
  install -m 644 "$NPM_SPEC_DIR/package.json" "$temporary/package.json"
  install -m 644 "$NPM_SPEC_DIR/package-lock.json" "$temporary/package-lock.json"
  (cd "$temporary" && npm ci --ignore-scripts --no-audit --no-fund)
  install_codebase_binary "$temporary/node_modules/codebase-memory-mcp"
  digest=$(runtime_tree_digest "$temporary")
  rm -rf "$NPM_RUNTIME_DIR"
  mv "$temporary" "$NPM_RUNTIME_DIR"
  printf '%s %s\n' "$(runtime_lock_digest)" "$digest" > "$NPM_RUNTIME_MARKER"
  link_npm_runtime
  check_npm_runtime
}

check_npm_runtime() {
  local lock expected_lock expected_tree actual_tree package command_name exclusions
  [ -d "$NPM_RUNTIME_DIR" ] && [ -f "$NPM_RUNTIME_MARKER" ] || return 1
  read -r expected_lock expected_tree < "$NPM_RUNTIME_MARKER"
  lock=$(runtime_lock_digest)
  [ "$lock" = "$expected_lock" ] || return 1
  actual_tree=$(runtime_tree_digest "$NPM_RUNTIME_DIR")
  [ "$actual_tree" = "$expected_tree" ] || return 1
  for package in $NPM_PACKAGES; do
    command_name=${package%@*}
    exclusions=node_modules
    [ "$command_name" = codebase-memory-mcp ] && exclusions='node_modules bin'
    verify_npm_tree "$(npm_archive_path "$command_name" "$package")" "$(npm_sum "$package")" \
      "$NPM_RUNTIME_DIR/node_modules/$command_name" "$exclusions" || return 1
    canonical_command "$command_name" "$BIN_DIR/$command_name" || return 1
  done
  check_codebase_binary "$NPM_RUNTIME_DIR/node_modules/codebase-memory-mcp"
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

platform() {
  os=$(uname -s)
  arch=$(uname -m)
  case "$os:$arch" in
    Darwin:arm64) printf 'macos-arm64' ;;
    Darwin:x86_64) printf 'macos-amd64' ;;
    Linux:aarch64|Linux:arm64) printf 'linux-arm64' ;;
    Linux:x86_64|Linux:amd64) printf 'linux-amd64' ;;
    *) printf 'setup: unsupported platform: %s:%s\n' "$os" "$arch" >&2; return 1 ;;
  esac
}

verified_download() {
  url=$1
  expected=$2
  destination=$3
  mode=${4:-755}
  temporary=$(mktemp)
  if ! curl -fsSL "$url" -o "$temporary"; then
    rm -f "$temporary"
    return 1
  fi
  actual=$(sha256 "$temporary")
  if [ "$actual" != "$expected" ]; then
    rm -f "$temporary"
    printf 'setup: checksum mismatch: %s\n' "$url" >&2
    return 1
  fi
  mkdir -p "$(dirname "$destination")"
  install -m "$mode" "$temporary" "$destination"
  rm -f "$temporary"
}

select_jq_asset() {
  case $(platform) in
    macos-arm64) JQ_ASSET=jq-macos-arm64; JQ_SUM=0bbe619e663e0de2c550be2fe0d240d076799d6f8a652b70fa04aea8a8362e8a ;;
    macos-amd64) JQ_ASSET=jq-macos-amd64; JQ_SUM=4155822bbf5ea90f5c79cf254665975eb4274d426d0709770c21774de5407443 ;;
    linux-arm64) JQ_ASSET=jq-linux-arm64; JQ_SUM=4dd2d8a0661df0b22f1bb9a1f9830f06b6f3b8f7d91211a1ef5d7c4f06a8b4a5 ;;
    linux-amd64) JQ_ASSET=jq-linux-amd64; JQ_SUM=5942c9b0934e510ee61eb3e30273f1b3fe2590df93933a93d7c58b81d19c8ff5 ;;
  esac
}

select_rtk_asset() {
  case $(platform) in
    macos-arm64) RTK_ASSET=rtk-aarch64-apple-darwin.tar.gz; RTK_SUM=8a17e49acbd378997eb21d0eb6f7f861111f35b4fc9b1c74edf4c7448e576c65 ;;
    macos-amd64) RTK_ASSET=rtk-x86_64-apple-darwin.tar.gz; RTK_SUM=a85f60e2637811be68366208b8d8b9c5ba1b748cb5df4477ab20cd73d3c5d9f8 ;;
    linux-arm64) RTK_ASSET=rtk-aarch64-unknown-linux-gnu.tar.gz; RTK_SUM=5519f7ca12e5c143a609f0d28a0a77b97413a8dce31c2681f1a41c24519a8731 ;;
    linux-amd64) RTK_ASSET=rtk-x86_64-unknown-linux-musl.tar.gz; RTK_SUM=ff8a1e7766496e175291a85aeca1dc97c9ff6df33e51e5893d1fbc78fea2a609 ;;
  esac
  RTK_ARCHIVE=$ASSET_DIR/$RTK_ASSET
}

select_codebase_asset() {
  case $(platform) in
    macos-arm64) CBM_ASSET=codebase-memory-mcp-darwin-arm64.tar.gz; CBM_SUM=fbd047509852021b5446a11141bcb0a3d1dcaebf6e5112460960f29f052c1c58 ;;
    macos-amd64) CBM_ASSET=codebase-memory-mcp-darwin-amd64.tar.gz; CBM_SUM=fb62da3016ea12b948351208759b5c083fb1446cf6e78d6db8b7cd28fe86fd54 ;;
    linux-arm64) CBM_ASSET=codebase-memory-mcp-linux-arm64-portable.tar.gz; CBM_SUM=13526acc2a6a0697dff3c763fb443a416589bc10ad8b12015b63d87e515dd72b ;;
    linux-amd64) CBM_ASSET=codebase-memory-mcp-linux-amd64-portable.tar.gz; CBM_SUM=6ab87a6c05d049dde57700803ca0ab4199fcf25973a0606618af0fcee73f5abd ;;
  esac
  CBM_ARCHIVE=$ASSET_DIR/$CBM_ASSET
}

install_codebase_binary() {
  local package_root temporary destination
  package_root=$1
  select_codebase_asset
  if [ ! -f "$CBM_ARCHIVE" ] || [ "$(sha256 "$CBM_ARCHIVE")" != "$CBM_SUM" ]; then
    verified_download "https://github.com/DeusData/codebase-memory-mcp/releases/download/v0.8.1/$CBM_ASSET" "$CBM_SUM" "$CBM_ARCHIVE" 644
  fi
  temporary=$(mktemp -d)
  tar -xzf "$CBM_ARCHIVE" -C "$temporary"
  destination=$package_root/bin/codebase-memory-mcp
  mkdir -p "$(dirname "$destination")"
  install -m 755 "$temporary/codebase-memory-mcp" "$destination"
  rm -rf "$temporary"
}

check_codebase_binary() {
  local package_root temporary matched installed
  package_root=$1
  select_codebase_asset
  [ -f "$CBM_ARCHIVE" ] && [ "$(sha256 "$CBM_ARCHIVE")" = "$CBM_SUM" ] || return 1
  temporary=$(mktemp -d)
  tar -xzf "$CBM_ARCHIVE" -C "$temporary"
  installed=$package_root/bin/codebase-memory-mcp
  if [ -f "$installed" ] && [ "$(sha256 "$temporary/codebase-memory-mcp")" = "$(sha256 "$installed")" ]; then matched=0; else matched=1; fi
  rm -rf "$temporary"
  return "$matched"
}

canonical_command() {
  name=$1
  expected=$2
  resolved=$(command -v "$name" || true)
  [ -n "$resolved" ] && [ -x "$expected" ] || return 1
  [ "$resolved" -ef "$expected" ]
}

check_jq_pin() {
  canonical_command jq "$JQ_BIN" || return 1
  [ "$(sha256 "$JQ_BIN")" = "$JQ_SUM" ] || return 1
  "$JQ_BIN" --version | grep -q "^jq-$JQ_VERSION$"
}

check_rtk_pin() {
  canonical_command rtk "$RTK_BIN" || return 1
  [ -f "$RTK_ARCHIVE" ] && [ "$(sha256 "$RTK_ARCHIVE")" = "$RTK_SUM" ] || return 1
  directory=$(mktemp -d)
  tar -xzf "$RTK_ARCHIVE" -C "$directory"
  matched=yes
  cmp -s "$directory/rtk" "$RTK_BIN" || matched=no
  rm -rf "$directory"
  [ "$matched" = yes ] || return 1
  "$RTK_BIN" --version | grep -q "^rtk $RTK_VERSION$"
}

install_jq() {
  select_jq_asset
  if check_jq_pin >/dev/null 2>&1; then
    return
  fi
  verified_download "https://github.com/jqlang/jq/releases/download/jq-$JQ_VERSION/$JQ_ASSET" "$JQ_SUM" "$JQ_BIN"
  check_jq_pin
}

install_rtk() {
  select_rtk_asset
  if check_rtk_pin >/dev/null 2>&1; then
    return
  fi
  verified_download "https://github.com/rtk-ai/rtk/releases/download/v$RTK_VERSION/$RTK_ASSET" "$RTK_SUM" "$RTK_ARCHIVE" 644
  directory=$(mktemp -d)
  tar -xzf "$RTK_ARCHIVE" -C "$directory"
  mkdir -p "$BIN_DIR"
  install -m 755 "$directory/rtk" "$RTK_BIN"
  rm -rf "$directory"
  check_rtk_pin
}

check_binary_pins() {
  select_jq_asset
  select_rtk_asset
  check_jq_pin || { printf 'setup: canonical jq checksum/version mismatch\n' >&2; return 1; }
  check_rtk_pin || { printf 'setup: canonical rtk archive/binary/version mismatch\n' >&2; return 1; }
}

install_tools() {
  need git
  need node
  need npm
  need python3
  need codex
  install_npm_runtime
  install_rtk
  install_jq
}

check_tools() {
  for command_name in git node npm python3 codex rtk jq; do
    need "$command_name"
  done
  check_npm_runtime
  codebase-memory-mcp cli list_projects '{}' >/dev/null
  context-mode --help >/dev/null
  ctx7 --help >/dev/null
  rtk --version >/dev/null
  codex --version >/dev/null
  check_binary_pins
}

case "$MODE" in
  install)
    install_tools
    "$ROOT/scripts/git-hooks/install.sh" install
    ;;
  check)
    "$ROOT/scripts/git-hooks/install.sh" check
    ;;
  binary-check)
    check_binary_pins
    exit
    ;;
  npm-tree-check)
    verify_npm_tree "$2" "$3" "$4" "$5"
    exit
    ;;
  *)
    printf 'usage: %s [install|check|binary-check|npm-tree-check]\n' "$0" >&2
    exit 2
    ;;
esac

check_tools
python3 "$ROOT/scripts/check-skill-contracts.py"
node "$ROOT/skills/deterministic-checks/scripts/check-design-md.js"
node "$ROOT/scripts/check-managed-skills.js"
printf 'setup: PASS\n'

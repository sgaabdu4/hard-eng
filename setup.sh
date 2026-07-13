#!/bin/bash
set -eu

ROOT=$(cd "$(dirname "$0")" && pwd -P)
MODE=${1:-install}
NPM_PACKAGES='codebase-memory-mcp@0.8.1 context-mode@1.0.168 ctx7@0.5.4'
RTK_VERSION=0.43.0
JQ_VERSION=1.7.1
BIN_DIR=$HOME/.local/bin
ASSET_DIR=$HOME/.local/share/hard-eng
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

install_npm_cli() {
  command_name=$1
  package=$2
  if ! npm list -g "$package" --depth=0 >/dev/null 2>&1; then
    npm install -g "$package"
  fi
  pinned_npm_binary "$command_name" "$package" >/dev/null
}

pinned_npm_binary() {
  command_name=$1
  package=$2
  npm list -g "$package" --depth=0 >/dev/null
  prefix=$(npm prefix -g)
  expected=$prefix/bin/$command_name
  resolved=$(command -v "$command_name" || true)
  if [ ! -x "$expected" ] || [ -z "$resolved" ]; then
    printf 'setup: pinned executable missing: %s\n' "$package" >&2
    return 1
  fi
  expected_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$expected")
  resolved_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$resolved")
  if [ "$expected_real" != "$resolved_real" ]; then
    printf 'setup: PATH executable does not match %s: %s\n' "$package" "$resolved" >&2
    return 1
  fi
  printf '%s\n' "$expected"
}

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
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
  for package in $NPM_PACKAGES; do
    install_npm_cli "${package%@*}" "$package"
  done
  install_rtk
  install_jq
}

check_tools() {
  for command_name in git node npm python3 codex rtk jq; do
    need "$command_name"
  done
  codebase_cli=$(pinned_npm_binary codebase-memory-mcp codebase-memory-mcp@0.8.1)
  context_cli=$(pinned_npm_binary context-mode context-mode@1.0.168)
  ctx7_cli=$(pinned_npm_binary ctx7 ctx7@0.5.4)
  "$codebase_cli" cli list_projects '{}' >/dev/null
  "$context_cli" --help >/dev/null
  "$ctx7_cli" --help >/dev/null
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
  *)
    printf 'usage: %s [install|check|binary-check]\n' "$0" >&2
    exit 2
    ;;
esac

check_tools
python3 "$ROOT/scripts/check-skill-contracts.py"
node "$ROOT/skills/deterministic-checks/scripts/check-design-md.js"
node "$ROOT/scripts/check-managed-skills.js"
printf 'setup: PASS\n'

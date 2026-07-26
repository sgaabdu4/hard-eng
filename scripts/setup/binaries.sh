#!/bin/bash

asset_fields() {
  local name value
  name=$1
  value=$(manifest asset "$name" "$(setup_platform)") || return 1
  IFS='|' read -r ASSET_VERSION ASSET_FILE ASSET_SUM ASSET_URL ASSET_KIND <<EOF
$value
EOF
  ASSET_ARCHIVE=$ASSET_DIR/$ASSET_FILE
}

ensure_asset_archive() {
  local name
  name=$1
  asset_fields "$name"
  if [ -f "$ASSET_ARCHIVE" ] && [ "$(sha256 "$ASSET_ARCHIVE")" = "$ASSET_SUM" ]; then
    return
  fi
  verified_download_to "$ASSET_URL" "$ASSET_SUM" "$ASSET_ARCHIVE" 644
}

require_asset_archive() {
  local name
  name=$1
  asset_fields "$name"
  [ -f "$ASSET_ARCHIVE" ] &&
    [ "$(sha256 "$ASSET_ARCHIVE")" = "$ASSET_SUM" ] ||
    setup_fail "pinned binary archive missing or corrupt: $name@$ASSET_VERSION"
}

extract_asset_binary() {
  local name destination
  name=$1
  destination=$2
  asset_fields "$name"
  case $ASSET_KIND in
    file)
      install -m 755 "$ASSET_ARCHIVE" "$destination"
      ;;
    tar.gz)
      if ! tar -xOf "$ASSET_ARCHIVE" "$name" >"$destination" ||
        [ ! -s "$destination" ] ||
        ! chmod 755 "$destination"; then
        rm -f -- "$destination"
        setup_fail "invalid binary archive layout: $name@$ASSET_VERSION"
        return 1
      fi
      ;;
    *) setup_fail "unsupported binary archive kind: $ASSET_KIND" ;;
  esac
}

expected_binary_sum() {
  local name temporary result
  name=$1
  temporary=$(setup_scratch_file binary)
  extract_asset_binary "$name" "$temporary"
  result=$(sha256 "$temporary")
  rm -f -- "$temporary"
  printf '%s\n' "$result"
}

binary_receipt() {
  printf '%s/binary-%s.sha256\n' "$STATE_DIR" "$1"
}

binary_is_owned() {
  local name destination receipt recorded
  name=$1
  destination=$2
  receipt=$(binary_receipt "$name")
  [ -f "$destination" ] && [ ! -L "$destination" ] &&
    [ -f "$receipt" ] && [ ! -L "$receipt" ] || return 1
  recorded=$(sed -n '1p' "$receipt")
  [ -n "$recorded" ] && [ "$(sha256 "$destination")" = "$recorded" ]
}

activate_binary() {
  local name staged destination expected receipt backup had_previous
  name=$1
  staged=$2
  destination=$BIN_DIR/$name
  expected=$(sha256 "$staged")
  receipt=$(binary_receipt "$name")
  had_previous=no

  if [ -L "$destination" ] || { [ -e "$destination" ] && [ ! -f "$destination" ]; }; then
    setup_fail "user-owned command conflicts with managed $name: $destination"
    return 1
  fi
  if [ -f "$destination" ]; then
    if [ "$(sha256 "$destination")" = "$expected" ]; then
      rm -f -- "$staged"
      atomic_write_text "$receipt" "$expected"
      return
    fi
    if ! binary_is_owned "$name" "$destination"; then
      setup_fail "user-owned command conflicts with managed $name: $destination"
      return 1
    fi
    had_previous=yes
  fi

  backup=$(mktemp "$BIN_DIR/.hard-eng-$name.backup.XXXXXX")
  rm -f -- "$backup"
  if [ "$had_previous" = yes ] && ! mv "$destination" "$backup"; then
    setup_fail "could not stage previous managed command: $destination"
    return 1
  fi
  if ! mv "$staged" "$destination"; then
    [ "$had_previous" = yes ] && mv "$backup" "$destination"
    setup_fail "could not activate managed command: $destination"
    return 1
  fi
  if ! atomic_write_text "$receipt" "$expected"; then
    rm -f -- "$destination"
    [ "$had_previous" = yes ] && mv "$backup" "$destination"
    return 1
  fi
  rm -f -- "$backup"
}

install_binary() {
  local name staged
  name=$1
  mkdir -p "$BIN_DIR" "$ASSET_DIR"
  ensure_asset_archive "$name"
  staged=$(mktemp "$BIN_DIR/.hard-eng-$name.stage.XXXXXX")
  extract_asset_binary "$name" "$staged"
  validate_staged_binary "$name" "$staged"
  activate_binary "$name" "$staged"
  check_binary "$name"
}

validate_staged_binary() {
  local name staged expected
  name=$1
  staged=$2
  expected=$(expected_binary_sum "$name")
  [ -f "$staged" ] && [ "$(sha256 "$staged")" = "$expected" ] || return 1
  asset_fields "$name"
  case $name in
    jq) "$staged" --version | grep -q "^jq-$ASSET_VERSION$" ;;
    rtk) "$staged" --version | grep -q "^rtk $ASSET_VERSION$" ;;
    *) return 1 ;;
  esac
}

check_binary() {
  local name destination expected receipt
  name=$1
  destination=$BIN_DIR/$name
  require_asset_archive "$name"
  receipt=$(binary_receipt "$name")
  canonical_command "$name" "$destination" || return 1
  validate_staged_binary "$name" "$destination" || return 1
  expected=$(sha256 "$destination")
  [ -f "$receipt" ] && [ ! -L "$receipt" ] &&
    [ "$(sed -n '1p' "$receipt")" = "$expected" ] || return 1
}

install_codebase_binary() {
  local package_root archive_mode destination
  package_root=$1
  archive_mode=$2
  case $archive_mode in
    install) ensure_asset_archive codebase-memory-mcp ;;
    check) require_asset_archive codebase-memory-mcp ;;
    *) return 1 ;;
  esac
  destination=$package_root/bin/codebase-memory-mcp
  mkdir -p "$(dirname "$destination")"
  extract_asset_binary codebase-memory-mcp "$destination"
}

check_codebase_binary() {
  local package_root installed expected
  package_root=$1
  require_asset_archive codebase-memory-mcp
  installed=$package_root/bin/codebase-memory-mcp
  expected=$(expected_binary_sum codebase-memory-mcp)
  [ -f "$installed" ] && [ "$(sha256 "$installed")" = "$expected" ]
}

install_binary_pins() {
  install_binary rtk
  install_binary jq
}

check_binary_pins() {
  check_binary jq ||
    { setup_fail "canonical jq checksum/version/ownership mismatch"; return 1; }
  check_binary rtk ||
    { setup_fail "canonical rtk checksum/version/ownership mismatch"; return 1; }
}

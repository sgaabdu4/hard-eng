#!/bin/bash

NPM_SPEC_DIR=$ROOT/runtime/npm
NPM_RUNTIME_DIR=$ASSET_DIR/npm-runtime
NPM_CACHE_DIR=$ASSET_DIR/npm-cache
NPM_RECEIPT=$STATE_DIR/npm-runtime.sha256

npm_packages() {
  manifest npm-specs
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
  mkdir -p "$ASSET_DIR" "$NPM_CACHE_DIR"
  temporary=$(mktemp -d "$ASSET_DIR/.hard-eng-npm-pack.XXXXXX")
  if ! npm pack "$package" --cache "$NPM_CACHE_DIR" \
    --pack-destination "$temporary" >/dev/null 2>&1; then
    safe_remove_setup_tree "$temporary"
    setup_fail "npm pack failed: $package"
    return 1
  fi
  set -- "$temporary"/*.tgz
  if [ "$#" -ne 1 ] || [ ! -f "$1" ] || [ "$(sha512 "$1")" != "$expected" ]; then
    safe_remove_setup_tree "$temporary"
    setup_fail "npm archive checksum mismatch: $package"
    return 1
  fi
  install -m 644 "$1" "$archive"
  safe_remove_setup_tree "$temporary"
  printf '%s\n' "$archive"
}

require_npm_archive() {
  local command_name package expected archive
  command_name=$1
  package=$2
  expected=$3
  archive=$(npm_archive_path "$command_name" "$package")
  if [ ! -f "$archive" ] || [ "$(sha512 "$archive")" != "$expected" ]; then
    setup_fail "pinned npm archive missing or corrupt: $package"
    return 1
  fi
  printf '%s\n' "$archive"
}

verify_npm_tree() {
  local archive expected installed exclusions temporary matched exclusion
  archive=$1
  expected=$2
  installed=$3
  exclusions=$4
  [ -f "$archive" ] && [ -d "$installed" ] &&
    [ "$(sha512 "$archive")" = "$expected" ] || return 1
  temporary=$(setup_scratch_dir npm-tree)
  tar -xzf "$archive" -C "$temporary"
  set --
  for exclusion in $exclusions; do
    set -- "$@" -x "$exclusion"
  done
  if diff -qr "$@" "$temporary/package" "$installed" >/dev/null 2>&1; then
    matched=0
  else
    matched=$?
  fi
  safe_remove_scratch_tree "$temporary"
  return "$matched"
}

runtime_tree_digest() {
  python3 "$ROOT/scripts/runtime-tree-digest.py" "$1"
}

context_mode_runtime_patch() {
  python3 "$ROOT/scripts/setup/context-mode-runtime.py" "$1" "$2" \
    "$(manifest get codex.context_mode.version)"
}

check_node_version() {
  local minimum status
  minimum=$(manifest get requirements.node_min)
  status=0
  bounded_setup_run 30 node -e "const m='$minimum'.split('.').map(Number),v=process.versions.node.split('.').map(Number); if(!(v[0]>m[0]||(v[0]===m[0]&&(v[1]>m[1]||(v[1]===m[1]&&v[2]>=m[2])))))process.exit(1)" ||
    status=$?
  [ "$status" != 124 ] || return 1
  [ "$status" = 0 ] ||
    setup_fail "Node.js $minimum+ is required for the pinned CLI runtime and the repository checks"
}

prepare_npm_runtime() {
  local destination archive_mode cache offline package command_name expected remove_path
  destination=$1
  archive_mode=$2
  cache=$3
  check_node_version
  for package in $(npm_packages); do
    command_name=${package%@*}
    expected=$(manifest npm-sha512 "$package")
    case $archive_mode in
      install)
        mkdir -p "$cache"
        ensure_npm_archive "$command_name" "$package" "$expected" >/dev/null
        ;;
      check) require_npm_archive "$command_name" "$package" "$expected" >/dev/null ;;
      *) return 1 ;;
    esac
  done
  install -m 644 "$NPM_SPEC_DIR/package.json" "$destination/package.json"
  install -m 644 "$NPM_SPEC_DIR/package-lock.json" "$destination/package-lock.json"
  offline=
  [ "$archive_mode" = install ] || offline=--offline
  (cd "$destination" &&
    npm ci $offline --cache "$cache" --ignore-scripts --no-audit --no-fund)
  for remove_path in $(manifest npm-remove-paths); do
    rm -rf -- "$destination/$remove_path"
  done
  install_codebase_binary "$destination/node_modules/codebase-memory-mcp" "$archive_mode"
  context_mode_runtime_patch apply "$destination/node_modules/context-mode"
}

validate_prepared_npm_runtime() {
  local destination package command_name expected exclusions
  destination=$1
  for package in $(npm_packages); do
    command_name=${package%@*}
    expected=$(manifest npm-sha512 "$package")
    exclusions=$(manifest npm-exclusions "$command_name")
    verify_npm_tree "$(npm_archive_path "$command_name" "$package")" "$expected" \
      "$destination/node_modules/$command_name" "$exclusions" || return 1
  done
  context_mode_runtime_patch check "$destination/node_modules/context-mode"
  check_codebase_binary "$destination/node_modules/codebase-memory-mcp" || return 1
  check_codebase_memory_command \
    "$destination/node_modules/codebase-memory-mcp/bin/codebase-memory-mcp" || return 1
  bounded_setup_run 60 node "$ROOT/scripts/context-mode-runtime-check.mjs" \
    "$destination/node_modules/context-mode"
}

npm_link_target() {
  printf '%s/node_modules/.bin/%s\n' "$NPM_RUNTIME_DIR" "$1"
}

npm_link_is_owned() {
  local name link
  name=$1
  link=$BIN_DIR/$name
  [ -L "$link" ] && [ "$(readlink "$link")" = "$(npm_link_target "$name")" ]
}

preflight_npm_links() {
  local package name link
  for package in $(npm_packages); do
    name=${package%@*}
    link=$BIN_DIR/$name
    if [ -L "$link" ]; then
      npm_link_is_owned "$name" ||
        { setup_fail "user-owned command conflicts with managed $name: $link"; return 1; }
    elif [ -e "$link" ]; then
      setup_fail "user-owned command conflicts with managed $name: $link"
      return 1
    fi
  done
}

npm_runtime_is_owned() {
  local package name owned_link current current_owner expected_owner
  [ -d "$NPM_RUNTIME_DIR" ] && [ ! -L "$NPM_RUNTIME_DIR" ] || return 1
  if [ -f "$NPM_RECEIPT" ] && [ ! -L "$NPM_RECEIPT" ]; then
    current=$(runtime_tree_digest "$NPM_RUNTIME_DIR") || return 1
    [ "$(sed -n '1p' "$NPM_RECEIPT")" = "$current" ] && return 0
  fi
  owned_link=no
  for package in $(npm_packages); do
    name=${package%@*}
    if npm_link_is_owned "$name"; then
      owned_link=yes
    elif [ -e "$BIN_DIR/$name" ] || [ -L "$BIN_DIR/$name" ]; then
      return 1
    fi
  done
  current_owner=$(node -p 'require(process.argv[1]).name' \
    "$NPM_RUNTIME_DIR/package.json" 2>/dev/null || true)
  expected_owner=$(node -p 'require(process.argv[1]).name' \
    "$NPM_SPEC_DIR/package.json" 2>/dev/null || true)
  [ "$owned_link" = yes ] &&
    [ -n "$expected_owner" ] &&
    [ "$current_owner" = "$expected_owner" ]
}

write_npm_receipt() {
  atomic_write_text "$NPM_RECEIPT" "$(runtime_tree_digest "$NPM_RUNTIME_DIR")"
}

rollback_npm_activation() {
  local backup created name failed
  backup=$1
  created=$2
  for name in $created; do
    npm_link_is_owned "$name" && rm -f -- "$BIN_DIR/$name"
  done
  if [ -d "$NPM_RUNTIME_DIR" ]; then
    failed=$(mktemp -d "$ASSET_DIR/.hard-eng-npm-failed.XXXXXX")
    rmdir "$failed"
    if ! mv "$NPM_RUNTIME_DIR" "$failed"; then
      rmdir "$failed"
      setup_fail "npm rollback could not isolate failed runtime: $NPM_RUNTIME_DIR"
      return 1
    fi
    safe_remove_setup_tree "$failed"
  fi
  if [ -n "$backup" ] && [ -d "$backup" ] &&
    ! mv "$backup" "$NPM_RUNTIME_DIR"; then
    setup_fail "npm rollback could not restore prior runtime; backup retained: $backup"
    return 1
  fi
}

activate_npm_runtime() {
  local staged backup package name link created target
  staged=$1
  backup=
  created=
  mkdir -p "$BIN_DIR" "$ASSET_DIR"
  preflight_npm_links
  if [ -e "$NPM_RUNTIME_DIR" ]; then
    npm_runtime_is_owned ||
      { setup_fail "unowned npm runtime conflicts with managed path: $NPM_RUNTIME_DIR"; return 1; }
    backup=$(mktemp -d "$ASSET_DIR/.hard-eng-npm-backup.XXXXXX")
    rmdir "$backup"
    mv "$NPM_RUNTIME_DIR" "$backup"
  fi
  if ! mv "$staged" "$NPM_RUNTIME_DIR"; then
    [ -n "$backup" ] && mv "$backup" "$NPM_RUNTIME_DIR"
    setup_fail "could not activate npm runtime"
    return 1
  fi
  for package in $(npm_packages); do
    name=${package%@*}
    link=$BIN_DIR/$name
    target=$(npm_link_target "$name")
    if [ ! -L "$link" ]; then
      if ! ln -s "$target" "$link"; then
        rollback_npm_activation "$backup" "$created"
        setup_fail "could not activate managed command: $link"
        return 1
      fi
      created="$created $name"
    fi
  done
  if ! write_npm_receipt; then
    rollback_npm_activation "$backup" "$created"
    return 1
  fi
  if [ -n "$backup" ]; then
    safe_remove_setup_tree "$backup"
  fi
}

install_npm_runtime() {
  local staged
  if check_npm_runtime >/dev/null 2>&1; then
    return
  fi
  mkdir -p "$ASSET_DIR"
  staged=$(mktemp -d "$ASSET_DIR/.hard-eng-npm-stage.XXXXXX")
  if ! prepare_npm_runtime "$staged" install "$NPM_CACHE_DIR"; then
    safe_remove_setup_tree "$staged"
    return 1
  fi
  if ! validate_prepared_npm_runtime "$staged"; then
    safe_remove_setup_tree "$staged"
    setup_fail "prepared npm runtime failed verification"
    return 1
  fi
  activate_npm_runtime "$staged"
  check_npm_runtime
}

check_npm_runtime() {
  local expected_tree actual_tree temporary cache package command_name exclusions expected
  [ -d "$NPM_RUNTIME_DIR" ] && [ ! -L "$NPM_RUNTIME_DIR" ] &&
    [ -d "$NPM_CACHE_DIR" ] && [ ! -L "$NPM_CACHE_DIR" ] || return 1
  preflight_npm_links || return 1
  for package in $(npm_packages); do
    command_name=${package%@*}
    npm_link_is_owned "$command_name" || return 1
  done
  temporary=$(setup_scratch_dir npm-check)
  cache=$(setup_scratch_dir npm-cache)
  if find "$NPM_CACHE_DIR" -type l -print -quit | grep -q .; then
    safe_remove_scratch_tree "$temporary"
    safe_remove_scratch_tree "$cache"
    return 1
  fi
  cp -R "$NPM_CACHE_DIR/." "$cache/"
  if ! prepare_npm_runtime "$temporary" check "$cache"; then
    safe_remove_scratch_tree "$temporary"
    safe_remove_scratch_tree "$cache"
    return 1
  fi
  expected_tree=$(runtime_tree_digest "$temporary")
  actual_tree=$(runtime_tree_digest "$NPM_RUNTIME_DIR")
  safe_remove_scratch_tree "$temporary"
  safe_remove_scratch_tree "$cache"
  [ "$actual_tree" = "$expected_tree" ] || return 1
  [ -f "$NPM_RECEIPT" ] && [ ! -L "$NPM_RECEIPT" ] &&
    [ "$(sed -n '1p' "$NPM_RECEIPT")" = "$actual_tree" ] || return 1
  context_mode_runtime_patch check "$NPM_RUNTIME_DIR/node_modules/context-mode"
  for package in $(npm_packages); do
    command_name=${package%@*}
    expected=$(manifest npm-sha512 "$package")
    exclusions=$(manifest npm-exclusions "$command_name")
    verify_npm_tree "$(npm_archive_path "$command_name" "$package")" "$expected" \
      "$NPM_RUNTIME_DIR/node_modules/$command_name" "$exclusions" || return 1
    canonical_command "$command_name" "$BIN_DIR/$command_name" || return 1
  done
  check_codebase_binary "$NPM_RUNTIME_DIR/node_modules/codebase-memory-mcp" || return 1
  bounded_setup_run 60 node "$ROOT/scripts/context-mode-runtime-check.mjs" \
    "$NPM_RUNTIME_DIR/node_modules/context-mode"
}

check_codebase_memory_command() {
  local command_path temporary status
  command_path=$1
  temporary=$(setup_scratch_dir codebase-memory)
  status=0
  if mkdir -p "$temporary/.cache/codebase-memory-mcp"; then
    HOME="$temporary" bounded_setup_run 60 "$command_path" cli list_projects || status=$?
  else
    status=1
  fi
  safe_remove_scratch_tree "$temporary"
  [ "$status" = 0 ]
}

check_codebase_memory_cli() {
  check_codebase_memory_command "$BIN_DIR/codebase-memory-mcp"
}

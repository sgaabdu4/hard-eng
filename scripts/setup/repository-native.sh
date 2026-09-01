#!/bin/bash

REPOSITORY_NATIVE_LAUNCHER=$ROOT/bin/hard-eng
REPOSITORY_NATIVE_COMMAND=$BIN_DIR/hard-eng

install_repository_native_launcher() {
  [ -f "$REPOSITORY_NATIVE_LAUNCHER" ] && [ ! -L "$REPOSITORY_NATIVE_LAUNCHER" ] && \
    [ -x "$REPOSITORY_NATIVE_LAUNCHER" ] ||
    { setup_fail "repository-native launcher is not an executable repository file"; return 1; }
  if [ -L "$REPOSITORY_NATIVE_COMMAND" ]; then
    [ "$REPOSITORY_NATIVE_COMMAND" -ef "$REPOSITORY_NATIVE_LAUNCHER" ] ||
      { setup_fail "hard-eng command link has another owner: $REPOSITORY_NATIVE_COMMAND"; return 1; }
    return 0
  fi
  [ ! -e "$REPOSITORY_NATIVE_COMMAND" ] ||
    { setup_fail "hard-eng command has another owner: $REPOSITORY_NATIVE_COMMAND"; return 1; }
  ln -s "$REPOSITORY_NATIVE_LAUNCHER" "$REPOSITORY_NATIVE_COMMAND" ||
    { setup_fail "could not create hard-eng command: $REPOSITORY_NATIVE_COMMAND"; return 1; }
}

check_repository_native_launcher() {
  [ -L "$REPOSITORY_NATIVE_COMMAND" ] &&
    [ "$REPOSITORY_NATIVE_COMMAND" -ef "$REPOSITORY_NATIVE_LAUNCHER" ] &&
    "$REPOSITORY_NATIVE_COMMAND" --version >/dev/null
}

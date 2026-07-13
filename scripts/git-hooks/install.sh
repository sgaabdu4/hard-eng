#!/bin/bash
set -eu

ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
HOOKS_DIR=${XDG_CONFIG_HOME:-"$HOME/.config"}/git/hard-eng-hooks
DISPATCH="$ROOT/scripts/git-hooks/dispatch.sh"
COPIER="$ROOT/scripts/git-hooks/copy-worktree-env.sh"
HOOKS='applypatch-msg pre-applypatch post-applypatch pre-commit pre-merge-commit prepare-commit-msg commit-msg post-commit pre-rebase post-checkout post-merge pre-push pre-receive update proc-receive post-receive post-update reference-transaction push-to-checkout pre-auto-gc post-rewrite sendemail-validate fsmonitor-watchman p4-changelist p4-prepare-changelist p4-post-changelist p4-pre-submit post-index-change'

check() {
  configured=$(git config --global --get core.hooksPath || true)
  [[ "$configured" == "$HOOKS_DIR" ]] || {
    printf 'global-hooks: core.hooksPath mismatch: %s\n' "${configured:-unset}" >&2
    return 1
  }
  effective=$(git config --get core.hooksPath || true)
  [[ "$effective" == "$HOOKS_DIR" ]] || {
    printf 'global-hooks: repository overrides core.hooksPath: %s\n' "${effective:-unset}" >&2
    return 1
  }
  [[ -L "$HOOKS_DIR/hard-eng-copy-worktree-env" && -x "$HOOKS_DIR/hard-eng-copy-worktree-env" ]] || {
    printf 'global-hooks: copier link missing\n' >&2
    return 1
  }
  [[ "$(readlink "$HOOKS_DIR/hard-eng-copy-worktree-env")" == "$COPIER" ]] || {
    printf 'global-hooks: copier target mismatch\n' >&2
    return 1
  }
  for hook in $HOOKS; do
    [[ -L "$HOOKS_DIR/$hook" && -x "$HOOKS_DIR/$hook" ]] || {
      printf 'global-hooks: hook link missing: %s\n' "$hook" >&2
      return 1
    }
    [[ "$(readlink "$HOOKS_DIR/$hook")" == "$DISPATCH" ]] || {
      printf 'global-hooks: hook target mismatch: %s\n' "$hook" >&2
      return 1
    }
  done
  printf 'global-hooks: PASS (%s)\n' "$HOOKS_DIR"
}

install_hooks() {
  configured=$(git config --global --get core.hooksPath || true)
  [[ -z "$configured" || "$configured" == "$HOOKS_DIR" ]] || {
    printf 'global-hooks: refusing to replace core.hooksPath=%s\n' "$configured" >&2
    return 1
  }

  mkdir -p "$HOOKS_DIR"
  ln -sfn "$COPIER" "$HOOKS_DIR/hard-eng-copy-worktree-env"
  for hook in $HOOKS; do
    path="$HOOKS_DIR/$hook"
    [[ ! -e "$path" || -L "$path" ]] || {
      printf 'global-hooks: refusing to replace %s\n' "$path" >&2
      return 1
    }
    ln -sfn "$DISPATCH" "$path"
  done
  git config --global core.hooksPath "$HOOKS_DIR"
  check
}

uninstall_hooks() {
  configured=$(git config --global --get core.hooksPath || true)
  if [[ "$configured" == "$HOOKS_DIR" ]]; then
    git config --global --unset core.hooksPath
  fi
  rm -f "$HOOKS_DIR/hard-eng-copy-worktree-env"
  for hook in $HOOKS; do
    [[ -L "$HOOKS_DIR/$hook" ]] && rm -f "$HOOKS_DIR/$hook"
  done
  rmdir "$HOOKS_DIR" 2>/dev/null || true
  printf 'global-hooks: removed\n'
}

case "${1:-install}" in
  install) install_hooks ;;
  check) check ;;
  uninstall) uninstall_hooks ;;
  *) printf 'usage: %s [install|check|uninstall]\n' "$0" >&2; exit 2 ;;
esac

#!/bin/bash
set -eu

ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-hooks.XXXXXX")
trap 'rm -rf "$TMP"' EXIT

repo="$TMP/repo"
worktree="$TMP/worktree"
hooks="$TMP/hooks"
mkdir -p "$repo" "$hooks"
git -C "$repo" init -q -b main
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
printf '.env*\n.native-hook-ran\n' > "$repo/.gitignore"
printf '.env\n' > "$repo/.worktreeinclude"
printf 'tracked\n' > "$repo/README.md"
printf 'SECRET=fixture\n' > "$repo/.env"
printf 'LOCAL=not-selected\n' > "$repo/.env.local"
git -C "$repo" add .gitignore .worktreeinclude README.md
git -C "$repo" commit -qm initial

use_global=0
if [[ "${1:-}" == "--installed" ]]; then
  installed=$(git config --global --get core.hooksPath || true)
  [[ -n "$installed" && -x "$installed/post-checkout" ]] || {
    printf 'global-hooks-test: installation missing\n' >&2
    exit 1
  }
  use_global=1
else
  ln -s "$ROOT/scripts/git-hooks/dispatch.sh" "$hooks/post-checkout"
  ln -s "$ROOT/scripts/git-hooks/dispatch.sh" "$hooks/pre-commit"
  ln -s "$ROOT/scripts/git-hooks/copy-worktree-env.sh" "$hooks/hard-eng-copy-worktree-env"
fi
printf '#!/bin/sh\ntouch .native-hook-ran\n' > "$repo/.git/hooks/post-checkout"
printf '#!/bin/sh\nexit 7\n' > "$repo/.git/hooks/pre-commit"
chmod +x "$repo/.git/hooks/post-checkout" "$repo/.git/hooks/pre-commit"

if [[ "$use_global" -eq 1 ]]; then
  git -C "$repo" worktree add -qd "$worktree" HEAD
else
  git -C "$repo" -c core.hooksPath="$hooks" worktree add -qd "$worktree" HEAD
fi
[[ "$(cat "$worktree/.env")" == 'SECRET=fixture' ]]
mode=$(stat -f '%Lp' "$worktree/.env" 2>/dev/null || stat -c '%a' "$worktree/.env")
[[ "$mode" == '600' ]]
[[ ! -e "$worktree/.env.local" ]]
[[ -e "$worktree/.native-hook-ran" ]]

if [[ "$use_global" -eq 1 ]]; then
  commit_command=(git -C "$worktree" commit --allow-empty -m blocked)
else
  commit_command=(git -C "$worktree" -c core.hooksPath="$hooks" commit --allow-empty -m blocked)
fi
if "${commit_command[@]}" >/dev/null 2>&1; then
  printf 'global-hooks-test: native pre-commit was bypassed\n' >&2
  exit 1
fi

if [[ "$use_global" -eq 1 ]]; then
  mkdir -p "$TMP/override-hooks"
  git -C "$repo" config core.hooksPath "$TMP/override-hooks"
  if (cd "$repo" && "$ROOT/scripts/git-hooks/install.sh" check) >/dev/null 2>&1; then
    printf 'global-hooks-test: repository hook override was not detected\n' >&2
    exit 1
  fi
fi

printf 'global-hooks-test: PASS\n'

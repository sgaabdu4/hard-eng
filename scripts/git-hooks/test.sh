#!/bin/bash
set -eu

# Fixture isolation: inherited repository variables would point these git calls
# at the invoking repository instead of the fixtures under $TMP.
unset $(git rev-parse --local-env-vars)

ROOT=$(cd "$(dirname "$0")/../.." && pwd -P)
TMP=$(mktemp -d "${TMPDIR:-/tmp}/hard-eng-hooks.XXXXXX")
trap 'rm -rf "$TMP"' EXIT
export GIT_CEILING_DIRECTORIES="$TMP"
if "$ROOT/scripts/git-hooks/publish-gate.sh" invalid >/dev/null 2>&1; then
  printf 'global-hooks-test: invalid publish-gate mode was accepted\n' >&2
  exit 1
fi

repo="$TMP/repo"
worktree="$TMP/worktree"
hooks="$TMP/hooks"
mkdir -p "$repo" "$hooks"
git -C "$repo" init -q -b main
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name Test
printf '.env*\n*.g.dart\nlocal.properties\n.native-hook-ran\n.worktree-setup-ran\n' > "$repo/.gitignore"
printf '.env\nlocal.properties\n**/*.g.dart\n' > "$repo/.worktreeinclude"
printf 'tracked\n' > "$repo/README.md"
printf 'SECRET=fixture\n' > "$repo/.env"
printf 'LOCAL=not-selected\n' > "$repo/.env.local"
printf 'sdk.dir=/fixture\n' > "$repo/local.properties"
mkdir -p "$repo/lib/generated"
printf 'generated\n' > "$repo/lib/generated/model.g.dart"
mkdir -p "$repo/scripts"
printf '#!/bin/sh\npwd -P > .worktree-setup-ran\n[ "${MUTATE_TRACKED:-0}" != 1 ] || printf dirty >> README.md\n' > "$repo/scripts/worktree-setup.sh"
chmod +x "$repo/scripts/worktree-setup.sh"
git -C "$repo" add .gitignore .worktreeinclude README.md scripts/worktree-setup.sh
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
[[ "$(cat "$worktree/.env")" == 'SECRET=fixture' ]] || {
  printf 'global-hooks-test: selected environment content mismatch\n' >&2
  exit 1
}
if stat -c '%a' "$worktree/.env" >/dev/null 2>&1; then
  mode=$(stat -c '%a' "$worktree/.env")
else
  mode=$(stat -f '%Lp' "$worktree/.env")
fi
[[ "$mode" == '600' ]] || { printf 'global-hooks-test: copied mode is %s\n' "$mode" >&2; exit 1; }
[[ ! -e "$worktree/.env.local" ]] || {
  printf 'global-hooks-test: unselected environment file was copied\n' >&2
  exit 1
}
[[ "$(cat "$worktree/local.properties")" == 'sdk.dir=/fixture' ]] || {
  printf 'global-hooks-test: selected local input mismatch\n' >&2
  exit 1
}
[[ "$(cat "$worktree/lib/generated/model.g.dart")" == 'generated' ]] || {
  printf 'global-hooks-test: selected generated input mismatch\n' >&2
  exit 1
}
[[ -e "$worktree/.native-hook-ran" ]] || {
  printf 'global-hooks-test: native post-checkout hook was not composed\n' >&2
  exit 1
}
expected_worktree=$(cd "$worktree" && pwd -P)
[[ "$(cat "$worktree/.worktree-setup-ran" 2>/dev/null)" == "$expected_worktree" ]] || {
  printf 'global-hooks-test: repository setup did not run in the selected worktree\n' >&2
  exit 1
}

head=$(git -C "$worktree" rev-parse HEAD)
rm -f "$repo/.worktree-setup-ran"
(cd "$repo" && "$hooks/post-checkout" 0000000000000000000000000000000000000000 "$head" 1)
[[ ! -e "$repo/.worktree-setup-ran" ]] || {
  printf 'global-hooks-test: primary checkout ran linked-worktree setup\n' >&2
  exit 1
}
rm "$worktree/.worktree-setup-ran"
(cd "$worktree" && "$hooks/post-checkout" "$head" "$head" 1)
[[ ! -e "$worktree/.worktree-setup-ran" ]] || {
  printf 'global-hooks-test: ordinary checkout reran repository setup\n' >&2
  exit 1
}
printf 'EXISTING=preserved\n' > "$worktree/.env"
(cd "$worktree" && "$ROOT/scripts/git-hooks/copy-worktree-env.sh" "$head" "$head" 1)
[[ "$(cat "$worktree/.env")" == 'EXISTING=preserved' ]] || {
  printf 'global-hooks-test: ordinary branch checkout overwrote existing input\n' >&2
  exit 1
}
rm "$worktree/.env"
(cd "$worktree" && "$ROOT/scripts/git-hooks/copy-worktree-env.sh" "$head" "$head" 1)
[[ ! -e "$worktree/.env" ]] || {
  printf 'global-hooks-test: ordinary branch checkout provisioned missing input\n' >&2
  exit 1
}

if (cd "$worktree" && MUTATE_TRACKED=1 "$hooks/post-checkout" 0000000000000000000000000000000000000000 "$head" 1) >/dev/null 2>&1; then
  printf 'global-hooks-test: tracked setup drift was accepted\n' >&2
  exit 1
fi
git -C "$worktree" -c core.hooksPath=/dev/null restore -- README.md

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

fake="$TMP/fake"
fake_linked="$TMP/fake-linked"
fake_hooks="$TMP/fake-hooks"
mkdir -p "$fake/scripts/git-hooks" "$fake_hooks"
cp "$ROOT/scripts/git-hooks/dispatch.sh" "$fake/scripts/git-hooks/dispatch.sh"
printf '#!/bin/sh\nprintf %%s "$1" > "$(git rev-parse --show-toplevel)/.gate-mode"\nexit 3\n' \
  > "$fake/scripts/git-hooks/publish-gate.sh"
chmod +x "$fake/scripts/git-hooks/dispatch.sh" "$fake/scripts/git-hooks/publish-gate.sh"
git -C "$fake" init -q -b main
git -C "$fake" config user.email test@example.com
git -C "$fake" config user.name Test
git -C "$fake" add scripts
git -C "$fake" -c core.hooksPath=/dev/null commit -qm baseline
ln -s "$fake/scripts/git-hooks/dispatch.sh" "$fake_hooks/pre-commit"
if git -C "$fake" -c core.hooksPath="$fake_hooks" commit --allow-empty -m gated >/dev/null 2>&1; then
  printf 'global-hooks-test: canonical publish gate did not block commit\n' >&2
  exit 1
fi
[[ "$(cat "$fake/.gate-mode" 2>/dev/null)" == 'commit' ]] || {
  printf 'global-hooks-test: canonical publish gate did not run with commit mode\n' >&2
  exit 1
}
git -C "$fake" -c core.hooksPath=/dev/null worktree add -qb linked "$fake_linked"
if git -C "$fake_linked" -c core.hooksPath="$fake_hooks" commit --allow-empty -m gated >/dev/null 2>&1; then
  printf 'global-hooks-test: linked checkout bypassed canonical publish gate\n' >&2
  exit 1
fi
[[ "$(cat "$fake_linked/.gate-mode" 2>/dev/null)" == 'commit' ]] || {
  printf 'global-hooks-test: linked checkout gate ran against the wrong checkout\n' >&2
  exit 1
}
rm "$fake_linked/scripts/git-hooks/publish-gate.sh"
if git -C "$fake_linked" -c core.hooksPath="$fake_hooks" commit --allow-empty -m missing-gate >/dev/null 2>&1; then
  printf 'global-hooks-test: linked checkout with missing gate was accepted\n' >&2
  exit 1
fi

printf 'global-hooks-test: PASS\n'

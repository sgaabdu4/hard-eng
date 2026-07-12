#!/usr/bin/env bash

set -euo pipefail

readonly SKILLS_CLI_VERSION="1.5.16"
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
readonly MODE="${1:---local}"

fail() {
  printf 'managed-skills: %s\n' "$1" >&2
  exit 1
}

lock_keys() {
  node <<'NODE'
const fs = require('fs');
const lock = JSON.parse(fs.readFileSync('.skill-lock.json', 'utf8'));
process.stdout.write(Object.keys(lock.skills || {}).sort().join('\n'));
NODE
}

validate_changed_paths() {
  local invalid=0
  local path

  while IFS= read -r -d '' path; do
    case "$path" in
      .skill-lock.json|skills/*) ;;
      *)
        printf 'managed-skills: updater touched forbidden path: %s\n' "$path" >&2
        invalid=1
        ;;
    esac
  done < <(
    git diff --name-only -z
    git diff --cached --name-only -z
    git ls-files --others --exclude-standard -z
  )

  [[ "$invalid" -eq 0 ]]
}

case "$MODE" in
  --local|--ci) ;;
  *) fail "usage: $0 [--local|--ci]" ;;
esac

cd "$ROOT"

[[ -f .skill-lock.json ]] || fail '.skill-lock.json is missing'
[[ -d skills ]] || fail 'skills/ is missing'
[[ -d "$HOME/.agents" ]] || fail '$HOME/.agents is missing'
[[ "$(cd "$HOME/.agents" && pwd -P)" == "$ROOT" ]] || fail '$HOME/.agents must resolve to this repository'
[[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]] || fail 'working tree must be clean'

node scripts/check-managed-skills.js
readonly BEFORE_KEYS="$(lock_keys)"

if [[ "$MODE" == '--local' ]]; then
  git fetch --prune origin
fi

npx --yes "skills@${SKILLS_CLI_VERSION}" update -g -y

node scripts/check-managed-skills.js
[[ "$(lock_keys)" == "$BEFORE_KEYS" ]] || fail 'the updater changed the lock allowlist'
validate_changed_paths || fail 'update escaped the managed path scope'

if [[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
  printf 'managed-skills: all locked skills are current\n'
else
  printf 'managed-skills: locked skill updates are ready\n'
  git status --short
fi

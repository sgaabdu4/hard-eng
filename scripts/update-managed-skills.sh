#!/usr/bin/env bash

set -euo pipefail

# Never resolve against an invoking hook's repository.
unset $(git rev-parse --local-env-vars)

readonly SKILLS_CLI_VERSION="1.5.22"
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

case "$MODE" in
  --local|--ci) ;;
  *) fail "usage: $0 [--local|--ci]" ;;
esac

cd "$ROOT"

[[ -f .skill-lock.json ]] || fail '.skill-lock.json is missing'
[[ -d skills ]] || fail 'skills/ is missing'
[[ -d "$HOME/.agents" ]] || fail '$HOME/.agents is missing'
[[ "$(cd "$HOME/.agents" && pwd -P)" == "$ROOT" ]] || fail '$HOME/.agents must resolve to this repository'
readonly STATE_HELPER="$ROOT/scripts/managed-skill-update-state.py"
[[ -f "$STATE_HELPER" ]] || fail 'managed-skill update state helper is missing'
BEFORE_LIFECYCLE_DIGEST="$(python3 "$STATE_HELPER" snapshot-before --repo "$ROOT")" || fail 'cannot capture starting lifecycle state'
readonly BEFORE_LIFECYCLE_DIGEST

node scripts/check-managed-skills.js
BEFORE_KEYS="$(lock_keys)" || fail 'cannot read the starting lock allowlist'
readonly BEFORE_KEYS

if [[ "$MODE" == '--local' ]]; then
  git fetch --prune origin
fi

set +e
npx --yes "skills@${SKILLS_CLI_VERSION}" update -g -y
UPDATE_EXIT=$?
set -e
readonly UPDATE_EXIT

AFTER_LIFECYCLE_DIGEST="$(python3 "$STATE_HELPER" snapshot-after --repo "$ROOT")" || fail 'cannot capture final lifecycle state'
readonly AFTER_LIFECYCLE_DIGEST
[[ "$AFTER_LIFECYCLE_DIGEST" == "$BEFORE_LIFECYCLE_DIGEST" ]] || fail 'the updater changed lifecycle state'
[[ "$UPDATE_EXIT" -eq 0 ]] || fail 'the skills CLI update failed'
[[ "$(lock_keys)" == "$BEFORE_KEYS" ]] || fail 'the updater changed the lock allowlist'
node scripts/check-managed-skills.js
MANAGED_CHANGE_STATE="$(python3 "$STATE_HELPER" validate-changes --repo "$ROOT")" || fail 'update escaped the managed path scope'
readonly MANAGED_CHANGE_STATE

if [[ "$MANAGED_CHANGE_STATE" == 'clean' ]]; then
  printf 'managed-skills: all locked skills are current\n'
else
  printf 'managed-skills: locked skill updates are ready\n'
  git status --short -- .skill-lock.json skills
fi

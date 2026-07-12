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

validate_state() {
  node <<'NODE'
const fs = require('fs');
const path = require('path');

const fail = (message) => {
  console.error(`managed-skills: ${message}`);
  process.exit(1);
};

let lock;
try {
  lock = JSON.parse(fs.readFileSync('.skill-lock.json', 'utf8'));
} catch (error) {
  fail(`invalid .skill-lock.json: ${error.message}`);
}

if (!lock.skills || typeof lock.skills !== 'object' || Array.isArray(lock.skills)) {
  fail('.skill-lock.json.skills must be an object');
}

const names = Object.keys(lock.skills).sort();
if (names.length === 0) fail('the lock contains no skills');

const entries = fs.readdirSync('skills', { withFileTypes: true });
const folders = entries.map((entry) => entry.name).sort();

if (JSON.stringify(folders) !== JSON.stringify(names)) {
  fail(`skills/ must equal lock keys; lock=[${names.join(', ')}] folders=[${folders.join(', ')}]`);
}

for (const name of names) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(name)) fail(`unsafe lock key: ${name}`);

  const root = path.join('skills', name);
  const stat = fs.lstatSync(root);
  if (!stat.isDirectory() || stat.isSymbolicLink()) fail(`${root} must be a plain directory`);
  if (!fs.existsSync(path.join(root, 'SKILL.md'))) fail(`${root}/SKILL.md is missing`);

  const item = lock.skills[name];
  if (!item || typeof item !== 'object') fail(`${name} lock metadata is invalid`);
  for (const field of ['source', 'sourceType', 'sourceUrl', 'skillPath', 'skillFolderHash']) {
    if (typeof item[field] !== 'string' || item[field].length === 0) {
      fail(`${name}.${field} is missing`);
    }
  }

  const pending = [root];
  while (pending.length > 0) {
    const current = pending.pop();
    for (const entry of fs.readdirSync(current, { withFileTypes: true })) {
      if (entry.name === '.git') fail(`${path.join(current, entry.name)} is forbidden`);
      if (entry.isDirectory()) pending.push(path.join(current, entry.name));
    }
  }
}
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

validate_state
readonly BEFORE_KEYS="$(lock_keys)"

if [[ "$MODE" == '--local' ]]; then
  git fetch --prune origin
fi

npx --yes "skills@${SKILLS_CLI_VERSION}" update -g -y

validate_state
[[ "$(lock_keys)" == "$BEFORE_KEYS" ]] || fail 'the updater changed the lock allowlist'
validate_changed_paths || fail 'update escaped the managed path scope'

if [[ -z "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
  printf 'managed-skills: all locked skills are current\n'
else
  printf 'managed-skills: locked skill updates are ready\n'
  git status --short
fi

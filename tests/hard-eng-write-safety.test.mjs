#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-hard-eng-write-safety.mjs');

function makeRepo(name) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), `${name}-`));
  fs.mkdirSync(path.join(root, 'scripts'), { recursive: true });
  assert.equal(spawnSync('git', ['init'], { cwd: root, encoding: 'utf8' }).status, 0);
  assert.equal(spawnSync('git', ['config', 'user.email', 'hard-eng@example.invalid'], { cwd: root, encoding: 'utf8' }).status, 0);
  assert.equal(spawnSync('git', ['config', 'user.name', 'Hard Eng Test'], { cwd: root, encoding: 'utf8' }).status, 0);
  return root;
}

function commitAll(root) {
  assert.equal(spawnSync('git', ['add', '.'], { cwd: root, encoding: 'utf8' }).status, 0);
  assert.equal(spawnSync('git', ['commit', '-m', 'scripts'], { cwd: root, encoding: 'utf8' }).status, 0);
}

function run(root, args = []) {
  return spawnSync('node', [script, ...args, root], { encoding: 'utf8' });
}

let root = makeRepo('hard-eng-write-safe');
fs.writeFileSync(path.join(root, 'scripts', 'apply-prod-schema.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  WRITE_ENABLED=1
fi
if [[ "$WRITE_ENABLED" != "1" ]]; then
  echo "dry-run: would update document"
  exit 0
fi
appwrite databases updateDocument "$@"
`);
commitAll(root);
let result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-unguarded-token-claims');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  WRITE_ENABLED=1
fi
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guarded write execution/);

for (const [name, body] of [
  ['inverted-shell-if', `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
if [[ "$WRITE_ENABLED" == "1" ]]; then
  exit 0
fi
appwrite users delete "$1"
`],
  ['inverted-shell-short-circuit', `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
[[ "$WRITE_ENABLED" == "1" ]] && exit 0
appwrite users delete "$1"
`],
  ['inverted-shell-disabled-value', `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
if [[ "$WRITE_ENABLED" != "0" ]]; then
  exit 0
fi
appwrite users delete "$1"
`],
  ['inverted-js-if', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
if (WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`],
  ['inverted-js-dry-run', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const dryRun = DRY_RUN !== '0';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
if (dryRun === false) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`],
]) {
  root = makeRepo(`hard-eng-write-${name}`);
  fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), body);
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${name} should reject inverted write guard`);
  assert.match(result.stderr, /guarded write execution/);
}

root = makeRepo('hard-eng-write-comment-claims');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
# dry run is default unless --write is passed.
# Writes use a reviewed input allowlist from --file and record approvalBoundaries.
# After --write, run read-back verification and audit the changed records.
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);
assert.match(result.stderr, /approval-boundary evidence/);

root = makeRepo('hard-eng-write-unsafe');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);
assert.match(result.stderr, /approval-boundary evidence/);

root = makeRepo('hard-eng-write-unsafe-multiline');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite \\
  users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

for (const [name, body] of [
  ['gh-api-method-equals', 'gh api repos/acme/demo --method=PATCH --field archived=true'],
  ['gh-api-spawn-sync-delete', "import { spawnSync } from 'node:child_process';\nspawnSync('gh', ['api', 'repos/acme/demo', '--method', 'DELETE']);"],
  ['appwrite-exec-file-delete', "import { execFileSync } from 'node:child_process';\nexecFileSync('appwrite', ['users', 'delete', id]);"],
  ['curl-request-delete', 'curl --request DELETE "https://api.example.invalid/users/$1"'],
  ['fetch-nested-url-delete', "await fetch(buildUrl(id), { method: 'DELETE' });"],
  ['graphql-mutation', "await graphql.query(`mutation DeleteUser { deleteUser(id: $id) { id } }`);"],
]) {
  root = makeRepo(`hard-eng-write-${name}`);
  fs.writeFileSync(path.join(root, 'scripts', 'mutate.mjs'), body);
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${name} should require write-safety proof`);
  assert.match(result.stderr, /dry-run default/, `${name} should report missing dry-run default`);
  assert.match(result.stderr, /explicit write flag/, `${name} should report missing explicit write flag`);
}

root = makeRepo('hard-eng-write-argv-safe');
fs.writeFileSync(path.join(root, 'scripts', 'archive-repo.mjs'), `#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
const DRY_RUN = process.env.DRY_RUN ?? '1';
let WRITE_ENABLED = false;
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
if (process.argv.includes('--write')) {
  WRITE_ENABLED = true;
}
if (!WRITE_ENABLED) {
  console.log(\`dry-run: would archive repo from \${reviewedInput}; \${DRY_RUN}; \${approvalBoundaries}; \${postWriteVerification}\`);
  process.exit(0);
}
spawnSync('gh', ['api', 'repos/acme/demo', '--method', 'PATCH']);
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

for (const scriptPath of [
  'hooks/mutate.js',
  'integrations/no-mistakes/scripts/mutate.mjs',
]) {
  root = makeRepo(`hard-eng-write-root-${scriptPath.replaceAll('/', '-')}`);
  fs.mkdirSync(path.dirname(path.join(root, scriptPath)), { recursive: true });
  fs.writeFileSync(path.join(root, scriptPath), 'gh api repos/acme/demo --method=DELETE\n');
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${scriptPath} should require write-safety proof`);
  assert.match(result.stderr, new RegExp(scriptPath.replaceAll('/', '\\/')));
  assert.match(result.stderr, /dry-run default/);
  assert.match(result.stderr, /explicit write flag/);
}

root = makeRepo('hard-eng-write-tests-noise');
fs.mkdirSync(path.join(root, 'tests'), { recursive: true });
fs.writeFileSync(path.join(root, 'tests', 'fixture.mjs'), 'gh api repos/acme/demo --method=DELETE\n');
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-regex-owner-noise');
fs.writeFileSync(path.join(root, 'scripts', 'validator.mjs'), `#!/usr/bin/env node
const appwriteDeletePattern = /\\bappwrite\\b.*\\bdelete\\b/i;
const approvalPatternSource = '\\\\b(?:deleted|delete)\\\\b.*\\\\bappwrite\\\\b';
const patterns = [
  /\\b(?:updated|update)\\b.*\\bappwrite\\b/,
];
console.log(appwriteDeletePattern, approvalPatternSource, patterns.length);
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-staged-bypass');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users list
`);
commitAll(root);
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
assert.equal(spawnSync('git', ['add', 'scripts/purge-users.sh'], { cwd: root, encoding: 'utf8' }).status, 0);
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users list
`);
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-head-bypass');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
commitAll(root);
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users list
`);
result = run(root, ['--head']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-rev-bypass');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
commitAll(root);
const unsafeWriteRev = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
appwrite users list
`);
commitAll(root);
result = run(root, ['--rev', unsafeWriteRev]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-readonly');
fs.writeFileSync(path.join(root, 'scripts', 'list-users.sh'), `#!/usr/bin/env bash
appwrite users list
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

console.log('hard-eng-write-safety-test: pass');

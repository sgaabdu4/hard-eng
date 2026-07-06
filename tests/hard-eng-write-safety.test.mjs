#!/usr/bin/env node
// HARD_ENG_LARGE_OWNER: dense write-safety behavior tests with focused coverage.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-hard-eng-write-safety.mjs');

assert.match(fs.readFileSync(script, 'utf8'), /HARD_ENG_(?:SCANNER|LARGE)_OWNER/);

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
  echo "dry-run: would update document; $approvalBoundaries"
  exit 0
fi
appwrite databases updateDocument "$reviewed_input" "$@"
appwrite databases getDocument "$reviewed_input" "$@" >/dev/null
echo "read-back verification complete"
`);
commitAll(root);
let result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-dry-run-guard-safe');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  DRY_RUN=0
fi
if [[ "$DRY_RUN" == "1" ]]; then
  echo "dry-run: would delete user; $approvalBoundaries"
  exit 0
fi
appwrite users delete "$reviewed_input" "$1"
appwrite users get "$reviewed_input" "$1" >/dev/null
echo "read-back verification complete"
`);
commitAll(root);
result = run(root);
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

root = makeRepo('hard-eng-write-flag-mentioned-only');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "$WRITE_ENABLED" != "1" ]]; then
  echo "dry-run: would delete user"
  exit 0
fi
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-dry-run-default-zero');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  DRY_RUN=0
fi
if [[ "$DRY_RUN" == "1" ]]; then
  echo "dry-run: would delete user"
  exit 0
fi
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /guarded write execution/);

root = makeRepo('hard-eng-write-enabled-default');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
WRITE_ENABLED=1
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  WRITE_ENABLED=1
fi
if [[ "$WRITE_ENABLED" != "1" ]]; then
  echo "dry-run: would delete user"
  exit 0
fi
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);

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

root = makeRepo('hard-eng-write-unrelated-shell-conditional');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  WRITE_ENABLED=1
fi
if [[ "\${CHECK_ONLY:-0}" == "1" ]]; then
  if [[ "$WRITE_ENABLED" != "1" ]]; then
    exit 0
  fi
fi
appwrite users delete "$1"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guarded write execution/);

for (const [name, body] of [
  ['detached-shell-helper', `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before WRITE_ENABLED=1"
post_write_verification="read-back verification"
guard_write() {
  if [[ "$WRITE_ENABLED" != "1" ]]; then
    return 0
  fi
}
appwrite users delete "$1"
`],
  ['detached-js-helper', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
function guardWrite() {
  if (!WRITE_ENABLED) {
    return;
  }
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`],
  ['detached-js-expression-helper', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
const guard = () => !WRITE_ENABLED && process.exit(0);
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`],
  ['detached-js-string-helper', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
const guard = "!WRITE_ENABLED && process.exit(0)";
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`],
  ['detached-js-exit-after-guard-branch', `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
if (!WRITE_ENABLED) {
  console.log('dry-run only');
}
const stop = () => {
  throw new Error('stop');
};
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
console.log(postWriteVerification);
`],
]) {
  root = makeRepo(`hard-eng-write-${name}`);
  fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), body);
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${name} should reject detached write guard`);
  assert.match(result.stderr, /guarded write execution/);
}

for (const [scriptPath, executable] of [
  ['codex/bin/codex-danger', true],
  ['tools/codex-danger', true],
  ['tools/shebang-danger', false],
]) {
  root = makeRepo(`hard-eng-write-extensionless-${scriptPath.replaceAll('/', '-')}`);
  fs.mkdirSync(path.dirname(path.join(root, scriptPath)), { recursive: true });
  fs.writeFileSync(path.join(root, scriptPath), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
  if (executable) fs.chmodSync(path.join(root, scriptPath), 0o755);
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${scriptPath} should require write-safety proof`);
  assert.match(result.stderr, new RegExp(scriptPath.replaceAll('/', '\\/')));
  assert.match(result.stderr, /dry-run default/);
  assert.match(result.stderr, /explicit write flag/);
}

root = makeRepo('hard-eng-write-extensionless-tests-noise');
fs.mkdirSync(path.join(root, 'tests'), { recursive: true });
fs.writeFileSync(path.join(root, 'tests', 'codex-danger'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
fs.chmodSync(path.join(root, 'tests', 'codex-danger'), 0o755);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-app-code-noise');
fs.mkdirSync(path.join(root, 'src', 'api'), { recursive: true });
fs.writeFileSync(path.join(root, 'src', 'api', 'client.ts'), `
export async function createComment(url: string, body: unknown) {
  return fetch(url, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });
}
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

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

root = makeRepo('hard-eng-write-prose-dry-run-default');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), `#!/usr/bin/env node
const WRITE_ENABLED = process.env.WRITE_ENABLED !== '0';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
console.log('dry-run by default');
if (!WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries, postWriteVerification), { method: 'DELETE' });
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);

root = makeRepo('hard-eng-write-detached-metadata');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
const postWriteVerification = 'read-back verification';
if (!WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(id), { method: 'DELETE' });
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /scoped allowlist or reviewed input/);
assert.match(result.stderr, /approval-boundary evidence/);
assert.match(result.stderr, /post-write verification/);

root = makeRepo('hard-eng-write-dry-run-default-detached-from-guard');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED !== '0';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
if (!WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries), { method: 'DELETE' });
await fetch(buildUrl(reviewedInput, allowlist));
console.log('read-back verification complete');
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);

root = makeRepo('hard-eng-write-effective-default-reassignment');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), `#!/usr/bin/env node
let WRITE_ENABLED = false;
WRITE_ENABLED = process.env.WRITE_ENABLED !== '0';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
if (!WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries), { method: 'DELETE' });
await fetch(buildUrl(reviewedInput, allowlist));
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);

root = makeRepo('hard-eng-write-log-only-verification');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.mjs'), `#!/usr/bin/env node
const DRY_RUN = process.env.DRY_RUN ?? '1';
const WRITE_ENABLED = process.env.WRITE_ENABLED === '1';
const reviewedInput = process.env.HARD_ENG_REVIEWED_INPUT ?? '--file reviewed-input.json';
const allowlist = 'reviewed input allowlist';
const approvalBoundaries = 'human approval required before WRITE_ENABLED=1';
if (!WRITE_ENABLED) {
  process.exit(0);
}
await fetch(buildUrl(reviewedInput, allowlist, approvalBoundaries), { method: 'DELETE' });
console.log('read-back verification complete');
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /post-write verification/);

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
  ['gh-api-default-post-field', 'gh api repos/acme/demo/issues/1/comments -f body=ok'],
  ['gh-api-default-post-raw-field', 'gh api repos/acme/demo/issues/1/comments --raw-field body=ok'],
  ['gh-api-default-post-input', 'gh api repos/acme/demo/import --input payload.json'],
  ['gh-api-spawn-sync-delete', "import { spawnSync } from 'node:child_process';\nspawnSync('gh', ['api', 'repos/acme/demo', '--method', 'DELETE']);"],
  ['gh-api-argv-default-post-field', "import { execFileSync } from 'node:child_process';\nexecFileSync('gh', ['api', 'repos/acme/demo/issues/1/comments', '-f', 'body=ok']);"],
  ['gh-api-dynamic-argv-delete', "import { execFileSync } from 'node:child_process';\nconst args = ['api', 'repos/acme/demo', '--method', 'DELETE'];\nexecFileSync('gh', args);"],
  ['gh-api-dynamic-command-delete', "import { execFileSync } from 'node:child_process';\nconst bin = 'gh';\nexecFileSync(bin, ['api', 'repos/acme/demo', '--method', 'DELETE']);"],
  ['appwrite-sdk-upsert-row', "tablesDB.upsertRow(databaseId, tableId, rowId, data);"],
  ['appwrite-sdk-create-rows', "tablesDB.createRows(databaseId, tableId, rows);"],
  ['appwrite-exec-file-delete', "import { execFileSync } from 'node:child_process';\nexecFileSync('appwrite', ['users', 'delete', id]);"],
  ['appwrite-execsync-template-delete', "import { execSync } from 'node:child_process';\nconst bin = 'appwrite';\nexecSync(`${bin} users delete ${id}`);"],
  ['appwrite-execsync-unknown-command-delete', "import { execSync } from 'node:child_process';\nconst bin = process.argv[2];\nexecSync(`${bin} users delete ${id}`);"],
  ['appwrite-unresolved-subprocess-command-delete', "import { spawnSync } from 'node:child_process';\nconst bin = process.argv[2] || 'appwrite';\nspawnSync(bin, ['users', 'delete', id]);"],
  ['appwrite-unresolved-command-global-option-delete', "import { spawnSync } from 'node:child_process';\nconst bin = process.argv[2] || 'appwrite';\nconst projectId = 'project';\nspawnSync(bin, ['--project-id', projectId, 'users', 'delete', id]);"],
  ['gh-api-unresolved-subprocess-command-field', "import { execFileSync } from 'node:child_process';\nconst bin = process.argv[2] || 'gh';\nexecFileSync(bin, ['api', 'repos/acme/demo/issues/1/comments', '-f', 'body=ok']);"],
  ['curl-unresolved-subprocess-command-delete', "import { spawnSync } from 'node:child_process';\nconst bin = process.argv[2] || 'curl';\nspawnSync(bin, ['--request', 'DELETE', url]);"],
  ['curl-unresolved-subprocess-command-attached-post', "import { spawnSync } from 'node:child_process';\nconst bin = process.argv[2] || 'curl';\nspawnSync(bin, ['-XPOST', url]);"],
  ['appwrite-dynamic-argv-delete', "import { spawnSync } from 'node:child_process';\nconst args = ['users', 'delete', id];\nspawnSync('appwrite', args);"],
  ['appwrite-dynamic-argv-concat-expression-delete', "import { spawnSync } from 'node:child_process';\nconst args = ['users'].concat(['delete', id]);\nspawnSync('appwrite', args);"],
  ['appwrite-direct-argv-concat-expression-delete', "import { spawnSync } from 'node:child_process';\nspawnSync('appwrite', ['users'].concat(['delete', id]));"],
  ['appwrite-dynamic-command-delete', "import { spawnSync } from 'node:child_process';\nconst bin = 'appwrite';\nspawnSync(bin, ['users', 'delete', id]);"],
  ['appwrite-unknown-argv', "import { spawnSync } from 'node:child_process';\nconst args = process.argv.slice(2);\nspawnSync('appwrite', args);"],
  ['appwrite-shell-command-variable-delete', "#!/usr/bin/env bash\nbin=appwrite\n\"${bin}\" users delete \"$1\""],
  ['appwrite-shell-dynamic-default-command-delete', "#!/usr/bin/env bash\nbin=\"${APPWRITE_BIN:-appwrite}\"\n\"$bin\" users delete \"$1\""],
  ['aw-shell-command-variable-delete', "#!/usr/bin/env bash\nbin=aw\n$bin users delete \"$1\""],
  ['curl-request-delete', 'curl --request DELETE "https://api.example.invalid/users/$1"'],
  ['curl-data-default-post', 'curl --data \'{"archived":true}\' "https://api.example.invalid/users/$1"'],
  ['curl-json-default-post', 'curl --json \'{"archived":true}\' "https://api.example.invalid/users/$1"'],
  ['curl-form-default-post', 'curl --form "avatar=@avatar.png" "https://api.example.invalid/users/$1"'],
  ['curl-shell-command-variable-delete', "#!/usr/bin/env bash\nbin=curl\n\"$bin\" --request DELETE \"https://api.example.invalid/users/$1\""],
  ['curl-spawn-sync-attached-post', "import { spawnSync } from 'node:child_process';\nspawnSync('curl', ['-XPOST', 'https://api.example.invalid/users/1']);"],
  ['curl-spawn-sync-json-default-post', "import { spawnSync } from 'node:child_process';\nspawnSync('curl', ['--json', JSON.stringify({ archived: true }), 'https://api.example.invalid/users/1']);"],
  ['fetch-nested-url-delete', "await fetch(buildUrl(id), { method: 'DELETE' });"],
  ['fetch-shorthand-delete', "const method = 'DELETE';\nawait fetch(buildUrl(id), { method });"],
  ['fetch-options-object-delete', "const options = { method: 'DELETE' };\nawait fetch(buildUrl(id), options);"],
  ['fetch-options-object-shorthand-delete', "const method = 'DELETE';\nconst options = { method };\nawait fetch(buildUrl(id), options);"],
  ['fetch-options-post-assignment-delete', "const options = {};\noptions.method = 'DELETE';\nawait fetch(buildUrl(id), options);"],
  ['fetch-dynamic-method', "const method = process.argv[2];\nawait fetch(buildUrl(id), { method });"],
  ['fetch-unresolved-options', "await fetch(buildUrl(id), requestOptions());"],
  ['fetch-spread-options', "await fetch(buildUrl(id), { ...requestOptions() });"],
  ['graphql-mutation', "await graphql.query(`mutation DeleteUser { deleteUser(id: $id) { id } }`);"],
  ['appwrite-argv-builder-push-delete', "import { spawnSync } from 'node:child_process';\nconst args = ['users'];\nargs.push('delete', id);\nspawnSync('appwrite', args);"],
  ['appwrite-argv-builder-concat-delete', "import { spawnSync } from 'node:child_process';\nlet args = ['users'];\nargs = args.concat(['delete', id]);\nspawnSync('appwrite', args);"],
  ['gh-api-argv-builder-push-delete', "import { execFileSync } from 'node:child_process';\nconst args = ['api', 'repos/acme/demo'];\nargs.push('--method', 'DELETE');\nexecFileSync('gh', args);"],
  ['gh-api-shell-command-variable-delete', "#!/usr/bin/env bash\nbin='gh'\n\"$bin\" api repos/acme/demo --method DELETE"],
  ['gh-api-partial-argv-unknown', "import { execFileSync } from 'node:child_process';\nconst args = ['api', repo];\nargs.push(...process.argv.slice(2));\nexecFileSync('gh', args);"],
  ['curl-partial-argv-unknown', "import { spawnSync } from 'node:child_process';\nconst args = ['https://api.example.invalid/users'];\nargs.push(...process.argv.slice(2));\nspawnSync('curl', args);"],
]) {
  root = makeRepo(`hard-eng-write-${name}`);
  fs.writeFileSync(path.join(root, 'scripts', 'mutate.mjs'), body);
  commitAll(root);
  result = run(root);
  assert.notEqual(result.status, 0, `${name} should require write-safety proof`);
  assert.match(result.stderr, /dry-run default/, `${name} should report missing dry-run default`);
  assert.match(result.stderr, /explicit write flag/, `${name} should report missing explicit write flag`);
}

root = makeRepo('hard-eng-write-curl-get-data-readonly');
fs.writeFileSync(path.join(root, 'scripts', 'query-users.sh'), `#!/usr/bin/env bash
curl -G --data-urlencode "email=$1" "https://api.example.invalid/users"
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-curl-argv-get-data-readonly');
fs.writeFileSync(path.join(root, 'scripts', 'query-users.mjs'), `#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
spawnSync('curl', ['-G', '--data-urlencode', \`email=\${process.argv[2]}\`, 'https://api.example.invalid/users']);
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-curl-shell-variable-get-data-readonly');
fs.writeFileSync(path.join(root, 'scripts', 'query-users.sh'), `#!/usr/bin/env bash
bin=curl
"$bin" -G --data-urlencode "email=$1" "https://api.example.invalid/users"
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-gh-api-field-get-readonly');
fs.writeFileSync(path.join(root, 'scripts', 'query-repo.sh'), `#!/usr/bin/env bash
gh api repos/acme/demo/issues --method GET -f state=open
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-execsync-template-readonly-noise');
fs.writeFileSync(path.join(root, 'scripts', 'status.mjs'), `#!/usr/bin/env node
import { execSync } from 'node:child_process';
const bin = 'git';
execSync(\`\${bin} status\`);
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-loop-detached-guard');
fs.writeFileSync(path.join(root, 'scripts', 'purge-users.sh'), `#!/usr/bin/env bash
DRY_RUN="\${DRY_RUN:-1}"
WRITE_ENABLED=0
reviewed_input="\${HARD_ENG_REVIEWED_INPUT:---file reviewed-input.json}"
allowlist="reviewed input allowlist"
approvalBoundaries="human approval required before --write"
post_write_verification="read-back verification"
if [[ "\${1:-}" == "--write" ]]; then
  WRITE_ENABLED=1
fi
for check in once; do
  if [[ "$WRITE_ENABLED" != "1" ]]; then
    echo "dry-run: would delete user; $approvalBoundaries"
    exit 0
  fi
done
appwrite users delete "$reviewed_input" "$1"
appwrite users get "$reviewed_input" "$1" >/dev/null
echo "read-back verification complete"
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /guarded write execution/);

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
spawnSync('gh', ['api', 'repos/acme/demo', '--method', 'PATCH', '--field', \`reviewedInput=\${reviewedInput}\`]);
spawnSync('gh', ['api', 'repos/acme/demo']);
console.log(\`read-back verification complete: \${postWriteVerification}\`);
`);
commitAll(root);
result = run(root);
assert.equal(result.status, 0, result.stderr);

root = makeRepo('hard-eng-write-python-subprocess-multiline');
fs.writeFileSync(path.join(root, 'scripts', 'mutate.py'), `#!/usr/bin/env python3
import subprocess
subprocess.run([
    'appwrite',
    'users',
    'delete',
    user_id,
])
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-python-subprocess-tuple-multiline');
fs.writeFileSync(path.join(root, 'scripts', 'mutate.py'), `#!/usr/bin/env python3
import subprocess
subprocess.run((
    'appwrite',
    'users',
    'delete',
    user_id,
))
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-python-subprocess-alias-multiline');
fs.writeFileSync(path.join(root, 'scripts', 'mutate.py'), `#!/usr/bin/env python3
import subprocess as sp
sp.run([
    'appwrite',
    'users',
    'delete',
    user_id,
])
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-python-subprocess-keyword-args');
fs.writeFileSync(path.join(root, 'scripts', 'mutate.py'), `#!/usr/bin/env python3
import subprocess
subprocess.run(args=[
    'appwrite',
    'users',
    'delete',
    user_id,
])
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

root = makeRepo('hard-eng-write-python-subprocess-shell-fstring');
fs.writeFileSync(path.join(root, 'scripts', 'mutate.py'), `#!/usr/bin/env python3
import subprocess
bin = os.environ.get('APPWRITE_BIN')
subprocess.run(f'{bin} users delete {user_id}', shell=True)
`);
commitAll(root);
result = run(root);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /dry-run default/);
assert.match(result.stderr, /explicit write flag/);

for (const scriptPath of [
  'hooks/mutate.js',
  'tools/mutate.ts',
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

root = makeRepo('hard-eng-write-extensionless-staged-bypass');
fs.mkdirSync(path.join(root, 'codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(root, 'codex', 'bin', 'codex-danger'), `#!/usr/bin/env bash
appwrite users list
`);
fs.chmodSync(path.join(root, 'codex', 'bin', 'codex-danger'), 0o755);
commitAll(root);
fs.writeFileSync(path.join(root, 'codex', 'bin', 'codex-danger'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
assert.equal(spawnSync('git', ['add', 'codex/bin/codex-danger'], { cwd: root, encoding: 'utf8' }).status, 0);
result = run(root, ['--staged']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /codex\/bin\/codex-danger/);
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

root = makeRepo('hard-eng-write-extensionless-rev-bypass');
fs.mkdirSync(path.join(root, 'codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(root, 'codex', 'bin', 'codex-danger'), `#!/usr/bin/env bash
appwrite users delete "$1"
`);
fs.chmodSync(path.join(root, 'codex', 'bin', 'codex-danger'), 0o755);
commitAll(root);
const unsafeExtensionlessRev = spawnSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).stdout.trim();
fs.writeFileSync(path.join(root, 'codex', 'bin', 'codex-danger'), `#!/usr/bin/env bash
appwrite users list
`);
commitAll(root);
result = run(root, ['--rev', unsafeExtensionlessRev]);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /codex\/bin\/codex-danger/);
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

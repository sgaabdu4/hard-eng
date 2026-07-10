#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { hasNoMistakesPostReceiveHook, repairHookText } from '../../../integrations/no-mistakes/scripts/repair-gate-hook.mjs';

const sampleHook = `#!/bin/sh
LOG="$(pwd)/notify-push.log"
notify_failed=0
while read oldrev newrev refname; do
  set -- --gate "$(pwd)" \\
    --ref "$refname" \\
    --old "$oldrev" \\
    --new "$newrev"
done
exec notify-push --gate "$(pwd)"
`;

const repaired = repairHookText(sampleHook);
assert.equal(repaired.changed, true);
assert.ok(repaired.text.includes('GATE_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"'));
assert.ok(repaired.text.includes('LOG="$GATE_DIR/notify-push.log"'));
assert.ok(repaired.text.includes('--gate "$GATE_DIR"'));
assert.ok(!repaired.text.includes('--gate "$(pwd)"'));

const secondPass = repairHookText(repaired.text);
assert.equal(secondPass.changed, false, 'repair must be idempotent');

const sparseHook = `#!/bin/sh
while read oldrev newrev refname; do
  set -- --gate "$(pwd)" --ref "$refname"
done
`;
const sparseRepair = repairHookText(sparseHook);
assert.equal(sparseRepair.changed, true);
assert.ok(sparseRepair.text.includes('GATE_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"'));
assert.ok(sparseRepair.text.includes('--gate "$GATE_DIR"'));
assert.ok(!sparseRepair.text.includes('--gate "$(pwd)"'));
assert.equal(repairHookText(sparseRepair.text).changed, false, 'sparse repair must be idempotent');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-nm-gate-'));
const gate = path.join(tmp, 'example.git');
const hooks = path.join(gate, 'hooks');
spawnSync('git', ['init', '-q', '--bare', gate], { encoding: 'utf8' });
const hookPath = path.join(hooks, 'post-receive');
fs.writeFileSync(hookPath, sampleHook, { mode: 0o755 });

const script = path.join(process.cwd(), 'integrations/no-mistakes/scripts/repair-gate-hook.mjs');
const result = spawnSync(process.execPath, [script, '--gate', gate], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /post-receive=repaired/);

const diskText = fs.readFileSync(hookPath, 'utf8');
assert.ok(diskText.includes('--gate "$GATE_DIR"'));
assert.ok(!diskText.includes('--gate "$(pwd)"'));

const aliasedScript = path.join(tmp, 'repair-gate-hook-alias.mjs');
fs.copyFileSync(script, aliasedScript);
const aliasedResult = spawnSync(process.execPath, [aliasedScript, '--gate', gate], { encoding: 'utf8' });
assert.equal(aliasedResult.status, 0, aliasedResult.stderr);
assert.match(aliasedResult.stdout, /post-receive=clean/);

const repo = path.join(tmp, 'repo');
const syncGate = path.join(tmp, 'sync.git');
fs.mkdirSync(repo);
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: repo, encoding: 'utf8' });
spawnSync('git', ['init', '-q', '--bare', syncGate], { encoding: 'utf8' });
fs.writeFileSync(path.join(syncGate, 'hooks', 'post-receive'), '#!/usr/bin/env sh\nexec notify-push --gate "$PWD"\n', { mode: 0o755 });
spawnSync('git', ['remote', 'add', 'no-mistakes', syncGate], { cwd: repo, encoding: 'utf8' });
const sourcePrePush = path.join(repo, '.git', 'hooks', 'pre-push');
fs.writeFileSync(sourcePrePush, '#!/usr/bin/env sh\necho proven pre-push\n', { mode: 0o755 });
const syncResult = spawnSync(process.execPath, [script, repo], { encoding: 'utf8' });
assert.equal(syncResult.status, 0, syncResult.stderr || syncResult.stdout);
const gatePrePush = path.join(syncGate, 'hooks', 'pre-push');
assert.ok((fs.statSync(gatePrePush).mode & 0o111) !== 0, 'synchronized gate pre-push hook must be executable');
assert.match(fs.readFileSync(gatePrePush, 'utf8'), /Managed by hard-eng no-mistakes gate dispatcher/);
const directHookResult = spawnSync(gatePrePush, [], { cwd: repo, encoding: 'utf8' });
assert.equal(directHookResult.status, 0, directHookResult.stderr);
assert.match(directHookResult.stdout, /proven pre-push/);

const huskyRepo = path.join(tmp, 'husky-repo');
const huskyGate = path.join(tmp, 'husky-sync.git');
fs.mkdirSync(huskyRepo);
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: huskyRepo, encoding: 'utf8' });
spawnSync('git', ['init', '-q', '--bare', huskyGate], { encoding: 'utf8' });
fs.writeFileSync(path.join(huskyGate, 'hooks', 'post-receive'), '#!/usr/bin/env sh\nexec notify-push --gate "$PWD"\n', { mode: 0o755 });
spawnSync('git', ['remote', 'add', 'no-mistakes', huskyGate], { cwd: huskyRepo, encoding: 'utf8' });
spawnSync('git', ['config', 'core.hooksPath', '.husky/_'], { cwd: huskyRepo, encoding: 'utf8' });
const marker = path.join(huskyRepo, 'husky-hook-ran');
fs.mkdirSync(path.join(huskyRepo, '.husky', '_'), { recursive: true });
fs.writeFileSync(path.join(huskyRepo, '.husky', '_', 'pre-push'), '#!/usr/bin/env sh\n. "$(dirname "$0")/h"\n', { mode: 0o755 });
fs.writeFileSync(path.join(huskyRepo, '.husky', '_', 'h'), '#!/usr/bin/env sh\nexec "$(dirname "$(dirname "$0")")/$(basename "$0")" "$@"\n', { mode: 0o755 });
fs.writeFileSync(path.join(huskyRepo, '.husky', 'pre-push'), `#!/usr/bin/env sh\nprintf ran > ${JSON.stringify(marker)}\n`, { mode: 0o755 });
const huskySyncResult = spawnSync(process.execPath, [script, huskyRepo], { encoding: 'utf8' });
assert.equal(huskySyncResult.status, 0, huskySyncResult.stderr || huskySyncResult.stdout);
const huskyGatePrePush = path.join(huskyGate, 'hooks', 'pre-push');
const huskyHookResult = spawnSync(huskyGatePrePush, [], { cwd: huskyRepo, encoding: 'utf8' });
assert.equal(huskyHookResult.status, 0, huskyHookResult.stderr);
assert.equal(fs.readFileSync(marker, 'utf8'), 'ran');

for (const [name, text, expected] of [
  ['echo-spoof', '#!/usr/bin/env sh\necho notify-push --gate "$PWD"\n', false],
  ['unreachable', '#!/usr/bin/env sh\nexit 0\nexec notify-push --gate "$PWD"\n', false],
  ['unreachable-branch', '#!/usr/bin/env sh\nif false\nthen\n  exec notify-push --gate "$PWD"\nfi\n', false],
  ['masked-failure', '#!/usr/bin/env sh\nnotify-push --gate "$PWD" || true\n', false],
  ['guarded-failure', '#!/usr/bin/env sh\nnotify-push --gate "$PWD" || exit $?\n', true],
  ['direct-exec', '#!/usr/bin/env sh\nexec notify-push --gate "$PWD"\n', true],
]) {
  const candidateGate = path.join(tmp, `${name}.git`);
  spawnSync('git', ['init', '-q', '--bare', candidateGate], { encoding: 'utf8' });
  fs.writeFileSync(path.join(candidateGate, 'hooks', 'post-receive'), text, { mode: 0o755 });
  assert.equal(hasNoMistakesPostReceiveHook(candidateGate), expected, name);
}

const untrustedRepo = path.join(tmp, 'untrusted-repo');
const untrustedGate = path.join(tmp, 'untrusted.git');
fs.mkdirSync(untrustedRepo);
spawnSync('git', ['init', '-q', '-b', 'main'], { cwd: untrustedRepo, encoding: 'utf8' });
spawnSync('git', ['init', '-q', '--bare', untrustedGate], { encoding: 'utf8' });
spawnSync('git', ['remote', 'add', 'no-mistakes', untrustedGate], { cwd: untrustedRepo, encoding: 'utf8' });
fs.writeFileSync(path.join(untrustedGate, 'hooks', 'post-receive'), '#!/usr/bin/env sh\nexit 0\n', { mode: 0o755 });
const untrustedTarget = path.join(untrustedGate, 'hooks', 'pre-push');
fs.writeFileSync(untrustedTarget, '#!/usr/bin/env sh\necho preserve-me\n', { mode: 0o755 });
fs.writeFileSync(path.join(untrustedRepo, '.git', 'hooks', 'pre-push'), '#!/usr/bin/env sh\necho source\n', { mode: 0o755 });
const untrustedResult = spawnSync(process.execPath, [script, untrustedRepo], { encoding: 'utf8' });
assert.notEqual(untrustedResult.status, 0, 'an unowned gate must be rejected');
assert.equal(fs.readFileSync(untrustedTarget, 'utf8'), '#!/usr/bin/env sh\necho preserve-me\n');

console.log('no-mistakes gate hook: pass');

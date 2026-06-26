#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { repairHookText } from '../../../integrations/no-mistakes/scripts/repair-gate-hook.mjs';

const sampleHook = `#!/bin/sh
LOG="$(pwd)/notify-push.log"
notify_failed=0
while read oldrev newrev refname; do
  set -- --gate "$(pwd)" \\
    --ref "$refname" \\
    --old "$oldrev" \\
    --new "$newrev"
done
`;

const repaired = repairHookText(sampleHook);
assert.equal(repaired.changed, true);
assert.ok(repaired.text.includes('GATE_DIR="$(cd "$(dirname "$0")/.." && pwd -P)"'));
assert.ok(repaired.text.includes('LOG="$GATE_DIR/notify-push.log"'));
assert.ok(repaired.text.includes('--gate "$GATE_DIR"'));
assert.ok(!repaired.text.includes('--gate "$(pwd)"'));

const secondPass = repairHookText(repaired.text);
assert.equal(secondPass.changed, false, 'repair must be idempotent');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-nm-gate-'));
const gate = path.join(tmp, 'example.git');
const hooks = path.join(gate, 'hooks');
fs.mkdirSync(hooks, { recursive: true });
const hookPath = path.join(hooks, 'post-receive');
fs.writeFileSync(hookPath, sampleHook, { mode: 0o755 });

const script = path.join(process.cwd(), 'integrations/no-mistakes/scripts/repair-gate-hook.mjs');
const result = spawnSync(process.execPath, [script, '--gate', gate], { encoding: 'utf8' });
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /no-mistakes-gate-hook: repaired/);

const diskText = fs.readFileSync(hookPath, 'utf8');
assert.ok(diskText.includes('--gate "$GATE_DIR"'));
assert.ok(!diskText.includes('--gate "$(pwd)"'));

console.log('no-mistakes gate hook: pass');

#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-no-mistakes-review-'));
const home = path.join(tmp, 'home');
const nmHome = path.join(tmp, 'nm-home');
const hardEngHome = path.join(tmp, '.agents');
const realBinary = path.join(tmp, 'bin', 'no-mistakes');
const repairScript = path.join(hardEngHome, 'integrations', 'no-mistakes', 'scripts', 'repair-gate-hook.mjs');
const logPath = path.join(tmp, 'calls.log');
fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(repairScript), { recursive: true });
fs.mkdirSync(home, { recursive: true });
fs.writeFileSync(realBinary, '#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$LOG_PATH"\n', { mode: 0o755 });
fs.writeFileSync(repairScript, '#!/usr/bin/env node\nprocess.exit(99);\n');

let result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'unset ROOT',
  'source scripts/setup-runtime.sh',
  '[[ "$ROOT" == "$PWD" ]]',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: { ...process.env, HOME: home },
});
assert.equal(result.status, 0, result.stderr || result.stdout);

result = spawnSync(path.join(repo, 'scripts', 'no-mistakes-wrapper.sh'), ['init'], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    HOME: home,
    HARD_ENG_HOME: hardEngHome,
    HARD_ENG_NO_MISTAKES_REAL_BIN: realBinary,
    LOG_PATH: logPath,
    NM_HOME: nmHome,
    PATH: '/bin:/usr/bin',
  },
});
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.match(result.stderr, /skipping repair hook because node is not on PATH/);
assert.equal(fs.readFileSync(logPath, 'utf8').trim(), 'init');

console.log('no-mistakes review comments: pass');

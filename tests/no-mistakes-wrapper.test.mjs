#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const wrapper = path.join(repo, 'scripts', 'no-mistakes-wrapper.sh');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-no-mistakes-wrapper-'));
const realHome = path.join(tmp, 'home');
const nmHome = path.join(tmp, 'nm-home');
const hardEngHome = path.join(tmp, '.agents');
const realBinary = path.join(nmHome, 'bin', 'no-mistakes');
const logPath = path.join(tmp, 'calls.jsonl');
const repairPath = path.join(hardEngHome, 'integrations', 'no-mistakes', 'scripts', 'repair-gate-hook.mjs');
const worktree = path.join(tmp, 'repo');

fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(repairPath), { recursive: true });
fs.mkdirSync(realHome, { recursive: true });
fs.mkdirSync(worktree, { recursive: true });

fs.writeFileSync(realBinary, `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({argv: process.argv.slice(1), home: process.env.HOME, codexHome: process.env.CODEX_HOME || "", nmHome: process.env.NM_HOME || ""}) + "\\n")' "$@"
`, { mode: 0o755 });

fs.writeFileSync(repairPath, `#!/usr/bin/env node
import fs from 'node:fs';
fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({repair: process.argv[2]}) + "\\n");
`, { mode: 0o755 });

function run(args) {
  return spawnSync(wrapper, args, {
    cwd: worktree,
    encoding: 'utf8',
    env: {
      ...process.env,
      HOME: realHome,
      NM_HOME: nmHome,
      HARD_ENG_HOME: hardEngHome,
      LOG_PATH: logPath,
    },
  });
}

function output(result) {
  return result.error?.message || result.stderr || result.stdout || 'command failed';
}

let result = run(['status']);
assert.equal(result.status, 0, output(result));

let calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls, [
  {
    argv: ['status'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

fs.writeFileSync(logPath, '');
result = run(['init', '--fork-url', 'git@github.com:example/fork.git']);
assert.equal(result.status, 0, output(result));

calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls.length, 2);
assert.deepEqual(calls[0].argv, ['init', '--fork-url', 'git@github.com:example/fork.git']);
assert.notEqual(calls[0].home, realHome);
assert.match(calls[0].home, /hard-eng-no-mistakes-home/);
assert.equal(path.resolve(calls[0].codexHome), path.join(path.resolve(calls[0].home), '.codex'));
assert.equal(calls[0].nmHome, nmHome);
assert.equal(fs.realpathSync(calls[1].repair), fs.realpathSync(worktree));
assert.equal(fs.existsSync(calls[0].home), false, 'temporary agent home should be removed after init');

fs.writeFileSync(logPath, '');
result = run(['init', '--help']);
assert.equal(result.status, 0, output(result));

calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls, [
  {
    argv: ['init', '--help'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

console.log('no-mistakes wrapper: pass');

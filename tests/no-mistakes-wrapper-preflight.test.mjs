#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = process.cwd();
const wrapper = path.join(repo, 'scripts', 'no-mistakes-wrapper.sh');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-no-mistakes-preflight-'));
const realHome = path.join(tmp, 'home');
const nmHome = path.join(tmp, 'nm-home');
const hardEngHome = path.join(tmp, '.agents');
const realBinary = path.join(nmHome, 'bin', 'no-mistakes');
const worktreeReadyPath = path.join(hardEngHome, 'scripts', 'ensure-worktree-ready.sh');
const qualityGatePath = path.join(hardEngHome, 'scripts', 'check-project-quality-gates.mjs');
const logPath = path.join(tmp, 'calls.jsonl');
const gitWorktree = path.join(tmp, 'git-repo');
const plainWorktree = path.join(tmp, 'plain-repo');

fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(qualityGatePath), { recursive: true });
fs.mkdirSync(realHome, { recursive: true });
fs.mkdirSync(gitWorktree, { recursive: true });
fs.mkdirSync(plainWorktree, { recursive: true });

fs.writeFileSync(realBinary, `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({argv: process.argv.slice(1), home: process.env.HOME, codexHome: process.env.CODEX_HOME || "", nmHome: process.env.NM_HOME || ""}) + "\\n")' "$@"
`, { mode: 0o755 });

fs.writeFileSync(qualityGatePath, `#!/usr/bin/env node
import fs from 'node:fs';
fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({qualityGate: process.argv.slice(2), cwd: process.cwd()}) + "\\n");
if (process.env.QUALITY_GATE_FAIL === '1') process.exit(23);
`, { mode: 0o755 });

fs.writeFileSync(worktreeReadyPath, `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({worktreeReady: process.argv.slice(1), cwd: process.cwd()}) + "\\n"); if (process.env.WORKTREE_READY_FAIL === "1") process.exit(22);' -- "$@"
`, { mode: 0o755 });

const gitInit = spawnSync('git', ['init'], {
  cwd: gitWorktree,
  encoding: 'utf8',
});
assert.equal(gitInit.status, 0, gitInit.stderr || gitInit.stdout);

function envWith(overrides = {}) {
  const env = {
    ...process.env,
    HOME: realHome,
    NM_HOME: nmHome,
    HARD_ENG_HOME: hardEngHome,
    HARD_ENG_NO_MISTAKES_REAL_BIN: realBinary,
    LOG_PATH: logPath,
    ...overrides,
  };
  for (const [key, value] of Object.entries(overrides)) {
    if (value === null) delete env[key];
  }
  return env;
}

function run(cwd, args, overrides = {}) {
  return spawnSync(wrapper, args, {
    cwd,
    encoding: 'utf8',
    env: envWith(overrides),
  });
}

function output(result) {
  return result.error?.message || result.stderr || result.stdout || 'command failed';
}

function calls() {
  const text = fs.existsSync(logPath) ? fs.readFileSync(logPath, 'utf8').trim() : '';
  if (!text) return [];
  return text.split('\n').map((line) => JSON.parse(line));
}

function resetLog() {
  fs.writeFileSync(logPath, '');
}

const expectedQualityGateArgs = ['--require-push-gate', fs.realpathSync(gitWorktree)];
const expectedWorktreeReadyArgs = ['--check', '--require-pre-push', fs.realpathSync(gitWorktree)];

resetLog();
let result = run(gitWorktree, ['axi', 'run', '--intent', 'ship']);
assert.equal(result.status, 0, output(result));
assert.deepEqual(calls(), [
  {
    worktreeReady: expectedWorktreeReadyArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
  {
    qualityGate: expectedQualityGateArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
  {
    argv: ['axi', 'run', '--intent', 'ship'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

resetLog();
result = run(gitWorktree, ['rerun', '--last']);
assert.equal(result.status, 0, output(result));
assert.deepEqual(calls(), [
  {
    worktreeReady: expectedWorktreeReadyArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
  {
    qualityGate: expectedQualityGateArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
  {
    argv: ['rerun', '--last'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

resetLog();
result = run(gitWorktree, ['axi', 'run'], { WORKTREE_READY_FAIL: '1' });
assert.equal(result.status, 22, result.stderr || result.stdout);
assert.match(result.stderr, /worktree readiness failed before no-mistakes/);
assert.deepEqual(calls(), [
  {
    worktreeReady: expectedWorktreeReadyArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
]);

resetLog();
result = run(gitWorktree, ['axi', 'run'], { QUALITY_GATE_FAIL: '1' });
assert.equal(result.status, 23, result.stderr || result.stdout);
assert.match(result.stderr, /deterministic quality gate failed before no-mistakes/);
assert.deepEqual(calls(), [
  {
    worktreeReady: expectedWorktreeReadyArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
  {
    qualityGate: expectedQualityGateArgs,
    cwd: fs.realpathSync(gitWorktree),
  },
]);

resetLog();
result = run(gitWorktree, ['axi', 'run'], { HARD_ENG_NO_MISTAKES_SKIP_PREFLIGHT: '1' });
assert.equal(result.status, 0, output(result));
assert.deepEqual(calls(), [
  {
    argv: ['axi', 'run'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

resetLog();
result = run(gitWorktree, ['axi', 'status']);
assert.equal(result.status, 0, output(result));
assert.deepEqual(calls(), [
  {
    argv: ['axi', 'status'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

resetLog();
result = run(plainWorktree, ['axi', 'run']);
assert.equal(result.status, 0, output(result));
assert.deepEqual(calls(), [
  {
    argv: ['axi', 'run'],
    home: realHome,
    codexHome: '',
    nmHome,
  },
]);

console.log('no-mistakes wrapper preflight: pass');

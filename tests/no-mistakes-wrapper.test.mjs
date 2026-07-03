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
const generatedHome = path.join(tmp, 'generated-home');
const generatedNmHome = path.join(tmp, 'generated-nm-home');
const generatedHardEngHome = path.join(tmp, 'generated-agents');
const generatedBinary = path.join(generatedNmHome, 'bin', 'no-mistakes');
const generatedWrapper = path.join(tmp, 'generated-bin', 'no-mistakes');
const generatedRepairPath = path.join(generatedHardEngHome, 'integrations', 'no-mistakes', 'scripts', 'repair-gate-hook.mjs');

fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(repairPath), { recursive: true });
fs.mkdirSync(path.dirname(generatedBinary), { recursive: true });
fs.mkdirSync(path.dirname(generatedWrapper), { recursive: true });
fs.mkdirSync(path.dirname(generatedRepairPath), { recursive: true });
fs.mkdirSync(realHome, { recursive: true });
fs.mkdirSync(generatedHome, { recursive: true });
fs.mkdirSync(worktree, { recursive: true });

const fakeBinary = `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({argv: process.argv.slice(1), home: process.env.HOME, codexHome: process.env.CODEX_HOME || "", nmHome: process.env.NM_HOME || ""}) + "\\n")' "$@"
`;

fs.writeFileSync(realBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(generatedBinary, fakeBinary, { mode: 0o755 });

const fakeRepair = `#!/usr/bin/env node
import fs from 'node:fs';
fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({repair: process.argv[2]}) + "\\n");
`;

fs.writeFileSync(repairPath, fakeRepair, { mode: 0o755 });
fs.writeFileSync(generatedRepairPath, fakeRepair, { mode: 0o755 });

function envWith(base, overrides = {}) {
  const env = { ...base, ...overrides };
  for (const [key, value] of Object.entries(overrides)) {
    if (value === null) delete env[key];
  }
  return env;
}

function runCommand(command, args, env) {
  return spawnSync(command, args, {
    cwd: worktree,
    encoding: 'utf8',
    env,
  });
}

function run(args, overrides = {}) {
  return runCommand(wrapper, args, envWith({
    ...process.env,
      HOME: realHome,
      NM_HOME: nmHome,
      HARD_ENG_HOME: hardEngHome,
      LOG_PATH: logPath,
    }, overrides));
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
result = run(['status'], { NM_HOME: null, NO_MISTAKES_HOME: nmHome });
assert.equal(result.status, 0, output(result));

calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
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

const installResult = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'install_no_mistakes_wrapper "$LINK_PATH" "$REAL_BIN" "$ROOT/scripts/no-mistakes-wrapper.sh" "$NM_DEFAULT" "$HE_DEFAULT"',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    ROOT: repo,
    LINK_PATH: generatedWrapper,
    REAL_BIN: generatedBinary,
    NM_DEFAULT: generatedNmHome,
    HE_DEFAULT: generatedHardEngHome,
  },
});
assert.equal(installResult.status, 0, installResult.stderr || installResult.stdout);

fs.writeFileSync(logPath, '');
result = runCommand(generatedWrapper, ['init'], envWith({
  ...process.env,
  HOME: generatedHome,
  LOG_PATH: logPath,
}, {
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
  HARD_ENG_HOME: null,
}));
assert.equal(result.status, 0, output(result));

calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls.length, 2);
assert.deepEqual(calls[0].argv, ['init']);
assert.equal(calls[0].nmHome, generatedNmHome);
assert.notEqual(calls[0].home, generatedHome);
assert.equal(fs.realpathSync(calls[1].repair), fs.realpathSync(worktree));

console.log('no-mistakes wrapper: pass');

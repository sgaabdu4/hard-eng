#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const helper = path.join(repo, 'scripts', 'no-mistakes-wrapper-install.sh');
const wrapperSource = path.join(repo, 'scripts', 'no-mistakes-wrapper.sh');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'no-mistakes-wrapper-refresh-'));
const logPath = path.join(tmp, 'calls.jsonl');
const helperText = fs.readFileSync(helper, 'utf8');

assert.match(
  helperText,
  /local [^\n]*\bembedded_home=""(?:\s|$)/,
  'refresh locals read under set -u must be initialized explicitly for Bash 5',
);

function binary(file, label) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({label: ${JSON.stringify(label)}, nmHome: process.env.NM_HOME}) + "\\n")'
`, { mode: 0o755 });
}

function runHelper(command, env) {
  const childEnv = { ...process.env, HELPER: helper, ROOT: repo, ...env };
  for (const [key, value] of Object.entries(env)) {
    if (value === null) delete childEnv[key];
  }
  return spawnSync('bash', ['-c', `set -euo pipefail\nsource "$HELPER"\n${command}`], {
    cwd: repo,
    encoding: 'utf8',
    env: childEnv,
  });
}

function runWrapper(file, home) {
  fs.writeFileSync(logPath, '');
  const env = { ...process.env, HOME: home, LOG_PATH: logPath };
  delete env.NM_HOME;
  delete env.NO_MISTAKES_HOME;
  const result = spawnSync(file, ['status'], { cwd: repo, encoding: 'utf8', env });
  assert.equal(result.status, 0, result.stderr || result.stdout);
  return JSON.parse(fs.readFileSync(logPath, 'utf8').trim());
}

const freshHome = path.join(tmp, 'fresh-home');
const freshNmHome = path.join(freshHome, '.no-mistakes');
const freshBinary = path.join(freshNmHome, 'bin', 'no-mistakes');
const freshLinkDir = path.join(freshHome, '.local', 'bin');
const freshCommand = path.join(freshLinkDir, 'no-mistakes');
binary(freshBinary, 'fresh');
let result = runHelper('refresh_no_mistakes_wrapper "$REAL_BIN"', {
  HOME: freshHome,
  NO_MISTAKES_LINK_DIR: freshLinkDir,
  REAL_BIN: freshBinary,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
});
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.match(fs.readFileSync(freshCommand, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);
assert.deepEqual(runWrapper(freshCommand, freshHome), { label: 'fresh', nmHome: fs.realpathSync(freshNmHome) });

const rawHome = path.join(tmp, 'raw-home');
const rawNmHome = path.join(tmp, 'raw-nm-home');
const rawStateHome = path.join(tmp, 'raw-state-home');
const rawLinkDir = path.join(tmp, 'raw-bin');
const rawCommand = path.join(rawLinkDir, 'no-mistakes');
binary(rawCommand, 'raw');
result = runHelper('refresh_no_mistakes_wrapper "$REAL_BIN"', {
  HOME: rawHome,
  NO_MISTAKES_HOME: rawNmHome,
  NO_MISTAKES_LINK_DIR: rawLinkDir,
  REAL_BIN: rawCommand,
  NM_HOME: rawStateHome,
});
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.match(fs.readFileSync(rawCommand, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);
assert.equal(fs.existsSync(path.join(rawNmHome, 'bin', 'no-mistakes')), true);
assert.deepEqual(runWrapper(rawCommand, rawHome), { label: 'raw', nmHome: rawStateHome });

const customHome = path.join(tmp, 'custom-home');
const customNmHome = path.join(tmp, 'custom-state');
const customBinary = path.join(customNmHome, 'bin', 'no-mistakes');
const customLinkDir = path.join(tmp, 'custom-bin');
const customCommand = path.join(customLinkDir, 'no-mistakes');
binary(customBinary, 'custom');
result = runHelper('install_no_mistakes_wrapper "$LINK_PATH" "$REAL_BIN" "$WRAPPER_SOURCE" "$NM_HOME_VALUE" "$ROOT"', {
  HOME: customHome,
  LINK_PATH: customCommand,
  REAL_BIN: customBinary,
  WRAPPER_SOURCE: wrapperSource,
  NM_HOME_VALUE: customNmHome,
});
assert.equal(result.status, 0, result.stderr || result.stdout);
result = runHelper('refresh_no_mistakes_wrapper "$REAL_BIN"', {
  HOME: customHome,
  NO_MISTAKES_LINK_DIR: customLinkDir,
  REAL_BIN: customBinary,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
});
assert.equal(result.status, 0, result.stderr || result.stdout);
assert.deepEqual(runWrapper(customCommand, customHome), { label: 'custom', nmHome: customNmHome });

console.log('no-mistakes-wrapper-refresh-behavior: pass');

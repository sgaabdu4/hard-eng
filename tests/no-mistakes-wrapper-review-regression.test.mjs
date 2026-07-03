#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-no-mistakes-review-'));

const sourceRuntime = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'unset ROOT',
  'source "$SETUP_RUNTIME"',
  'type install_or_update_no_mistakes >/dev/null',
  'printf "%s\\n" "$ROOT"',
].join('\n')], {
  cwd: tmp,
  encoding: 'utf8',
  env: {
    ...process.env,
    HOME: path.join(tmp, 'source-home'),
    SETUP_RUNTIME: path.join(repo, 'scripts', 'setup-runtime.sh'),
    HARD_ENG_SKIP_NO_MISTAKES: '1',
    HARD_ENG_SKIP_TREEHOUSE: '1',
  },
});
assert.equal(sourceRuntime.status, 0, sourceRuntime.stderr || sourceRuntime.stdout);
assert.equal(sourceRuntime.stdout.trim(), repo);

const home = path.join(tmp, 'home');
const nmHome = path.join(tmp, 'nm-home');
const hardEngHome = path.join(tmp, 'hard-eng');
const realBinary = path.join(nmHome, 'bin', 'no-mistakes');
const repairScript = path.join(hardEngHome, 'integrations', 'no-mistakes', 'scripts', 'repair-gate-hook.mjs');
const logPath = path.join(tmp, 'calls.log');
const worktree = path.join(tmp, 'worktree');

fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(repairScript), { recursive: true });
fs.mkdirSync(home, { recursive: true });
fs.mkdirSync(worktree, { recursive: true });
fs.writeFileSync(realBinary, `#!/bin/sh
printf '%s|%s|%s\\n' "$1" "$HOME" "$NM_HOME" >> "$LOG_PATH"
`, { mode: 0o755 });
fs.writeFileSync(repairScript, 'throw new Error("node should be unavailable");\n');

const initWithoutNode = spawnSync('bash', [path.join(repo, 'scripts', 'no-mistakes-wrapper.sh'), 'init'], {
  cwd: worktree,
  encoding: 'utf8',
  env: {
    ...process.env,
    HOME: home,
    NM_HOME: nmHome,
    HARD_ENG_HOME: hardEngHome,
    HARD_ENG_NO_MISTAKES_REAL_BIN: realBinary,
    LOG_PATH: logPath,
    PATH: '/usr/bin:/bin',
  },
});
assert.equal(initWithoutNode.status, 0, initWithoutNode.stderr || initWithoutNode.stdout);
assert.match(initWithoutNode.stderr, /skipping repair hook because node is not on PATH/);
const [command, isolatedHome, loggedNmHome] = fs.readFileSync(logPath, 'utf8').trim().split('|');
assert.equal(command, 'init');
assert.notEqual(isolatedHome, home, 'init must still use an isolated agent HOME');
assert.equal(loggedNmHome, nmHome);

console.log('no-mistakes wrapper review regressions: pass');

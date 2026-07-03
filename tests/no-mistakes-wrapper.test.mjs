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
const refreshHome = path.join(tmp, 'refresh-home');
const refreshNmHome = path.join(tmp, 'refresh nm-home');
const refreshHardEngHome = path.join(tmp, 'refresh agents');
const refreshBinary = path.join(refreshNmHome, 'bin', 'no-mistakes');
const refreshLinkDir = path.join(tmp, 'refresh-bin');
const refreshWrapper = path.join(refreshLinkDir, 'no-mistakes');
const refreshRepairPath = path.join(refreshHardEngHome, 'integrations', 'no-mistakes', 'scripts', 'repair-gate-hook.mjs');
const setupPathHome = path.join(tmp, 'setup-path-home');
const setupPathNmHome = path.join(tmp, 'setup-path-nm-home');
const setupPathBin = path.join(tmp, 'setup-path-bin');
const setupPathBinary = path.join(setupPathBin, 'no-mistakes');
const setupPathLinkDir = path.join(tmp, 'setup-path-link-dir');
const setupPathWrapper = path.join(setupPathLinkDir, 'no-mistakes');
const setupDirectHome = path.join(tmp, 'setup-direct-home');
const setupDirectNmHome = path.join(tmp, 'setup-direct-nm-home');
const setupDirectLinkDir = path.join(tmp, 'setup-direct-link-dir');
const setupDirectWrapper = path.join(setupDirectLinkDir, 'no-mistakes');
const setupPrecedenceHome = path.join(tmp, 'setup-precedence-home');
const setupPrecedenceDefaultBinary = path.join(setupPrecedenceHome, '.no-mistakes', 'bin', 'no-mistakes');
const setupPrecedenceActiveNmHome = path.join(tmp, 'setup-precedence-active', '.no-mistakes');
const setupPrecedenceActiveBinary = path.join(setupPrecedenceActiveNmHome, 'bin', 'no-mistakes');
const setupPrecedenceLinkDir = path.join(tmp, 'setup-precedence-link-dir');
const setupPrecedenceWrapper = path.join(setupPrecedenceLinkDir, 'no-mistakes');
const customLinkHome = path.join(tmp, 'custom-link-home');
const customLinkNmHome = path.join(tmp, 'custom link nm-home');
const customLinkRealBinary = path.join(customLinkNmHome, 'bin', 'no-mistakes');
const legacyLinkNmHome = path.join(tmp, 'legacy link nm-home');
const legacyLinkRealBinary = path.join(legacyLinkNmHome, 'bin', 'no-mistakes');
const customLinkDir = path.join(tmp, 'custom-link-bin');
const customLinkWrapper = path.join(customLinkDir, 'no-mistakes');
const staleLinkHome = path.join(tmp, 'stale-link-home');
const staleDefaultBinary = path.join(staleLinkHome, '.no-mistakes', 'bin', 'no-mistakes');
const staleActiveNmHome = path.join(tmp, 'stale-active', '.no-mistakes');
const staleActiveBinary = path.join(staleActiveNmHome, 'bin', 'no-mistakes');
const staleLinkDir = path.join(tmp, 'stale-link-bin');
const staleWrapper = path.join(staleLinkDir, 'no-mistakes');
const pathOnlyHome = path.join(tmp, 'path-only-home');
const pathOnlyDefaultNmHome = path.join(pathOnlyHome, '.no-mistakes');
const pathOnlyPrefix = path.join(tmp, 'opt', 'homebrew');
const pathOnlyBinary = path.join(pathOnlyPrefix, 'bin', 'no-mistakes');
const pathOnlyLinkDir = path.join(tmp, 'path-only-link-bin');
const pathOnlyWrapper = path.join(pathOnlyLinkDir, 'no-mistakes');
const pathOnlyStateHome = path.join(tmp, 'path-only-state-home');
const samePathHome = path.join(tmp, 'same-path-home');
const samePathNmHome = path.join(tmp, 'same-path-nm-home');
const samePathBinary = path.join(samePathNmHome, 'bin', 'no-mistakes');

fs.mkdirSync(path.dirname(realBinary), { recursive: true });
fs.mkdirSync(path.dirname(repairPath), { recursive: true });
fs.mkdirSync(path.dirname(generatedBinary), { recursive: true });
fs.mkdirSync(path.dirname(generatedWrapper), { recursive: true });
fs.mkdirSync(path.dirname(generatedRepairPath), { recursive: true });
fs.mkdirSync(path.dirname(refreshBinary), { recursive: true });
fs.mkdirSync(path.dirname(refreshWrapper), { recursive: true });
fs.mkdirSync(path.dirname(refreshRepairPath), { recursive: true });
fs.mkdirSync(path.dirname(setupPathBinary), { recursive: true });
fs.mkdirSync(path.dirname(setupPathWrapper), { recursive: true });
fs.mkdirSync(path.dirname(setupDirectWrapper), { recursive: true });
fs.mkdirSync(path.dirname(setupPrecedenceDefaultBinary), { recursive: true });
fs.mkdirSync(path.dirname(setupPrecedenceActiveBinary), { recursive: true });
fs.mkdirSync(path.dirname(setupPrecedenceWrapper), { recursive: true });
fs.mkdirSync(path.dirname(customLinkRealBinary), { recursive: true });
fs.mkdirSync(path.dirname(legacyLinkRealBinary), { recursive: true });
fs.mkdirSync(path.dirname(customLinkWrapper), { recursive: true });
fs.mkdirSync(path.dirname(staleDefaultBinary), { recursive: true });
fs.mkdirSync(path.dirname(staleActiveBinary), { recursive: true });
fs.mkdirSync(path.dirname(staleWrapper), { recursive: true });
fs.mkdirSync(path.dirname(pathOnlyBinary), { recursive: true });
fs.mkdirSync(path.dirname(pathOnlyWrapper), { recursive: true });
fs.mkdirSync(path.dirname(samePathBinary), { recursive: true });
fs.mkdirSync(realHome, { recursive: true });
fs.mkdirSync(generatedHome, { recursive: true });
fs.mkdirSync(refreshHome, { recursive: true });
fs.mkdirSync(setupPathHome, { recursive: true });
fs.mkdirSync(setupDirectHome, { recursive: true });
fs.mkdirSync(setupPrecedenceHome, { recursive: true });
fs.mkdirSync(customLinkHome, { recursive: true });
fs.mkdirSync(staleLinkHome, { recursive: true });
fs.mkdirSync(pathOnlyHome, { recursive: true });
fs.mkdirSync(samePathHome, { recursive: true });
fs.mkdirSync(worktree, { recursive: true });

function fakeBinaryScript(label = '') {
  const binaryField = label ? `binary: ${JSON.stringify(label)}, ` : '';
  return `#!/usr/bin/env bash
set -euo pipefail
node -e 'const fs=require("fs"); fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({${binaryField}argv: process.argv.slice(1), home: process.env.HOME, codexHome: process.env.CODEX_HOME || "", nmHome: process.env.NM_HOME || ""}) + "\\n")' "$@"
`;
}

const fakeBinary = fakeBinaryScript();

fs.writeFileSync(realBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(generatedBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(refreshBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(setupPathBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(setupDirectWrapper, fakeBinary, { mode: 0o755 });
fs.writeFileSync(setupPrecedenceDefaultBinary, fakeBinaryScript('setup-default'), { mode: 0o755 });
fs.writeFileSync(setupPrecedenceActiveBinary, fakeBinaryScript('setup-active'), { mode: 0o755 });
fs.writeFileSync(customLinkRealBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(legacyLinkRealBinary, fakeBinary, { mode: 0o755 });
fs.writeFileSync(staleDefaultBinary, fakeBinaryScript('stale-default'), { mode: 0o755 });
fs.writeFileSync(staleActiveBinary, fakeBinaryScript('stale-active'), { mode: 0o755 });
fs.writeFileSync(pathOnlyBinary, fakeBinaryScript('path-only-active'), { mode: 0o755 });
fs.writeFileSync(samePathBinary, fakeBinaryScript('same-path'), { mode: 0o755 });

const fakeRepair = `#!/usr/bin/env node
import fs from 'node:fs';
fs.appendFileSync(process.env.LOG_PATH, JSON.stringify({repair: process.argv[2]}) + "\\n");
`;

fs.writeFileSync(repairPath, fakeRepair, { mode: 0o755 });
fs.writeFileSync(generatedRepairPath, fakeRepair, { mode: 0o755 });
fs.writeFileSync(refreshRepairPath, fakeRepair, { mode: 0o755 });

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

const samePathInstall = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'install_no_mistakes_wrapper "$REAL_BIN" "$REAL_BIN" "$ROOT/scripts/no-mistakes-wrapper.sh" "$NM_DEFAULT" "$HE_DEFAULT"',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    ROOT: repo,
    REAL_BIN: samePathBinary,
    NM_DEFAULT: samePathNmHome,
    HE_DEFAULT: hardEngHome,
    HARD_ENG_REPLACE_NO_MISTAKES_COMMAND: '1',
  },
});
assert.notEqual(samePathInstall.status, 0, samePathInstall.stderr || samePathInstall.stdout);
assert.doesNotMatch(fs.readFileSync(samePathBinary, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);

fs.writeFileSync(logPath, '');
result = runCommand(samePathBinary, ['status'], envWith({
  ...process.env,
  HOME: samePathHome,
  LOG_PATH: logPath,
}, {
  NM_HOME: samePathNmHome,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'same-path');

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

const setupManagedHome = path.join(tmp, 'setup-managed-home');
fs.mkdirSync(setupManagedHome, { recursive: true });
fs.writeFileSync(logPath, '');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/setup-runtime.sh"',
  'run_no_mistakes_with_isolated_agent_home "$MANAGED_WRAPPER" init',
].join('\n')], {
  cwd: worktree,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: setupManagedHome,
    MANAGED_WRAPPER: generatedWrapper,
    LOG_PATH: logPath,
  }, {
    HARD_ENG_HOME: null,
    NM_HOME: null,
    NO_MISTAKES_HOME: null,
  }),
});
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls.length, 2);
assert.equal(calls[0].nmHome, generatedNmHome);
assert.notEqual(calls[0].home, setupManagedHome);
assert.equal(fs.realpathSync(calls[1].repair), fs.realpathSync(worktree));

const setupRawHome = path.join(tmp, 'setup-raw-home');
fs.mkdirSync(setupRawHome, { recursive: true });
fs.writeFileSync(logPath, '');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/setup-runtime.sh"',
  'run_no_mistakes_with_isolated_agent_home "$REAL_BIN" init',
].join('\n')], {
  cwd: worktree,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: setupRawHome,
    REAL_BIN: generatedBinary,
    LOG_PATH: logPath,
    NO_MISTAKES_HOME: generatedNmHome,
  }, {
    HARD_ENG_HOME: null,
    NM_HOME: null,
  }),
});
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls.length, 1);
assert.deepEqual(calls[0].argv, ['init']);
assert.equal(path.resolve(calls[0].codexHome), path.join(path.resolve(calls[0].home), '.codex'));
assert.equal(calls[0].nmHome, generatedNmHome);
assert.notEqual(calls[0].home, setupRawHome);

fs.writeFileSync(logPath, '');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/setup-runtime.sh"',
  'install_or_update_no_mistakes',
].join('\n')], {
  cwd: worktree,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: setupPathHome,
    PATH: `${setupPathBin}:${process.env.PATH}`,
    NO_MISTAKES_HOME: setupPathNmHome,
    NO_MISTAKES_LINK_DIR: setupPathLinkDir,
    LOG_PATH: logPath,
  }, {
    HARD_ENG_HOME: null,
    NM_HOME: null,
  }),
});
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls[0].argv, ['update', '--yes']);
assert.equal(fs.lstatSync(setupPathWrapper).isSymbolicLink(), false, 'setup must replace a PATH upstream command with the managed wrapper');

fs.writeFileSync(logPath, '');
result = runCommand(setupPathWrapper, ['status'], envWith({
  ...process.env,
  HOME: setupPathHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls, [
  {
    argv: ['status'],
    home: setupPathHome,
    codexHome: '',
    nmHome: setupPathNmHome,
  },
]);

fs.writeFileSync(logPath, '');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/setup-runtime.sh"',
  'install_or_update_no_mistakes',
].join('\n')], {
  cwd: worktree,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: setupDirectHome,
    PATH: `${setupDirectLinkDir}:${process.env.PATH}`,
    NO_MISTAKES_HOME: setupDirectNmHome,
    NO_MISTAKES_LINK_DIR: setupDirectLinkDir,
    LOG_PATH: logPath,
  }, {
    HARD_ENG_HOME: null,
    NM_HOME: null,
  }),
});
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls[0].argv, ['update', '--yes']);
assert.match(fs.readFileSync(setupDirectWrapper, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);
assert.equal(fs.existsSync(path.join(setupDirectNmHome, 'bin', 'no-mistakes')), true);

fs.writeFileSync(logPath, '');
result = runCommand(setupDirectWrapper, ['status'], envWith({
  ...process.env,
  HOME: setupDirectHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls, [
  {
    argv: ['status'],
    home: setupDirectHome,
    codexHome: '',
    nmHome: setupDirectNmHome,
  },
]);

fs.writeFileSync(logPath, '');
result = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/setup-runtime.sh"',
  'install_or_update_no_mistakes',
].join('\n')], {
  cwd: worktree,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: setupPrecedenceHome,
    PATH: `${path.dirname(setupPrecedenceActiveBinary)}:${process.env.PATH}`,
    NO_MISTAKES_LINK_DIR: setupPrecedenceLinkDir,
    LOG_PATH: logPath,
  }, {
    HARD_ENG_HOME: null,
    HARD_ENG_NO_MISTAKES_REAL_BIN: null,
    NM_HOME: null,
    NO_MISTAKES_HOME: null,
  }),
});
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'setup-active', 'setup must update the active no-mistakes command when no home is configured');
assert.deepEqual(calls[0].argv, ['update', '--yes']);
assert.match(fs.readFileSync(setupPrecedenceWrapper, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);

fs.writeFileSync(logPath, '');
result = runCommand(setupPrecedenceWrapper, ['status'], envWith({
  ...process.env,
  HOME: setupPrecedenceHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'setup-active', 'setup wrapper must keep the active command state');
assert.equal(calls[0].nmHome, fs.realpathSync(setupPrecedenceActiveNmHome));

fs.symlinkSync(legacyLinkRealBinary, customLinkWrapper);
const customLinkResult = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'refresh_no_mistakes_wrapper',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    ROOT: repo,
    HOME: customLinkHome,
    NO_MISTAKES_LINK_DIR: customLinkDir,
    NO_MISTAKES_HOME: customLinkNmHome,
    HARD_ENG_HOME: hardEngHome,
  },
});
assert.equal(customLinkResult.status, 0, customLinkResult.stderr || customLinkResult.stdout);
assert.equal(fs.lstatSync(customLinkWrapper).isSymbolicLink(), false, 'custom NO_MISTAKES_HOME must migrate old direct no-mistakes symlinks');

fs.writeFileSync(logPath, '');
result = runCommand(customLinkWrapper, ['status'], envWith({
  ...process.env,
  HOME: customLinkHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.deepEqual(calls, [
  {
    argv: ['status'],
    home: customLinkHome,
    codexHome: '',
    nmHome: customLinkNmHome,
  },
]);

fs.symlinkSync(staleActiveBinary, staleWrapper);
const staleLinkResult = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'refresh_no_mistakes_wrapper',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: staleLinkHome,
    NO_MISTAKES_LINK_DIR: staleLinkDir,
  }, {
    HARD_ENG_HOME: null,
    HARD_ENG_NO_MISTAKES_REAL_BIN: null,
    NM_HOME: null,
    NO_MISTAKES_HOME: null,
  }),
});
assert.equal(staleLinkResult.status, 0, staleLinkResult.stderr || staleLinkResult.stdout);
assert.equal(fs.lstatSync(staleWrapper).isSymbolicLink(), false, 'direct no-mistakes symlinks must migrate to the wrapper');

fs.writeFileSync(logPath, '');
result = runCommand(staleWrapper, ['status'], envWith({
  ...process.env,
  HOME: staleLinkHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'stale-active', 'refresh must preserve the active direct symlink target over stale default state');
assert.equal(calls[0].nmHome, fs.realpathSync(staleActiveNmHome));

const pathOnlyResult = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'refresh_no_mistakes_wrapper',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: pathOnlyHome,
    PATH: `${path.dirname(pathOnlyBinary)}:${process.env.PATH}`,
    NO_MISTAKES_LINK_DIR: pathOnlyLinkDir,
  }, {
    HARD_ENG_HOME: null,
    HARD_ENG_NO_MISTAKES_REAL_BIN: null,
    NM_HOME: null,
    NO_MISTAKES_HOME: null,
  }),
});
assert.equal(pathOnlyResult.status, 0, pathOnlyResult.stderr || pathOnlyResult.stdout);
assert.match(fs.readFileSync(pathOnlyWrapper, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);

fs.writeFileSync(logPath, '');
result = runCommand(pathOnlyWrapper, ['status'], envWith({
  ...process.env,
  HOME: pathOnlyHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'path-only-active', 'refresh must wrap active PATH no-mistakes commands');
assert.equal(calls[0].nmHome, pathOnlyDefaultNmHome, 'PATH binaries must keep the normal no-mistakes state home');

fs.writeFileSync(logPath, '');
result = runCommand(pathOnlyWrapper, ['status'], envWith({
  ...process.env,
  HOME: pathOnlyHome,
  LOG_PATH: logPath,
  NM_HOME: pathOnlyStateHome,
}, {
  HARD_ENG_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'path-only-active', 'NM_HOME must not replace the baked real binary');
assert.equal(calls[0].nmHome, pathOnlyStateHome);

fs.writeFileSync(logPath, '');
result = runCommand(pathOnlyWrapper, ['status'], envWith({
  ...process.env,
  HOME: pathOnlyHome,
  LOG_PATH: logPath,
  NO_MISTAKES_HOME: pathOnlyStateHome,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls[0].binary, 'path-only-active', 'NO_MISTAKES_HOME must not replace the baked real binary');
assert.equal(calls[0].nmHome, pathOnlyStateHome);

const refreshInstall = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'install_no_mistakes_wrapper "$LINK_PATH" "$REAL_BIN" "$ROOT/scripts/no-mistakes-wrapper.sh" "$NM_DEFAULT" "$HE_DEFAULT"',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: {
    ...process.env,
    ROOT: repo,
    LINK_PATH: refreshWrapper,
    REAL_BIN: refreshBinary,
    NM_DEFAULT: refreshNmHome,
    HE_DEFAULT: refreshHardEngHome,
  },
});
assert.equal(refreshInstall.status, 0, refreshInstall.stderr || refreshInstall.stdout);

const refreshWrapperLines = fs.readFileSync(refreshWrapper, 'utf8').split('\n');
fs.writeFileSync(refreshWrapper, `${refreshWrapperLines.slice(0, 5).join('\n')}\nexit 93\n`);
fs.chmodSync(refreshWrapper, 0o755);

const refreshResult = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'refresh_no_mistakes_wrapper',
].join('\n')], {
  cwd: repo,
  encoding: 'utf8',
  env: envWith({
    ...process.env,
    ROOT: repo,
    HOME: refreshHome,
    NO_MISTAKES_LINK_DIR: refreshLinkDir,
  }, {
    HARD_ENG_HOME: null,
    HARD_ENG_NO_MISTAKES_REAL_BIN: null,
    NM_HOME: null,
    NO_MISTAKES_HOME: null,
  }),
});
assert.equal(refreshResult.status, 0, refreshResult.stderr || refreshResult.stdout);

fs.writeFileSync(logPath, '');
result = runCommand(refreshWrapper, ['init'], envWith({
  ...process.env,
  HOME: refreshHome,
  LOG_PATH: logPath,
}, {
  HARD_ENG_HOME: null,
  NM_HOME: null,
  NO_MISTAKES_HOME: null,
}));
assert.equal(result.status, 0, output(result));
calls = fs.readFileSync(logPath, 'utf8').trim().split('\n').map((line) => JSON.parse(line));
assert.equal(calls.length, 2);
assert.equal(calls[0].nmHome, refreshNmHome);
assert.notEqual(calls[0].home, refreshHome);
assert.equal(fs.realpathSync(calls[1].repair), fs.realpathSync(worktree));

const wrapperInstallText = fs.readFileSync(path.join(repo, 'scripts', 'no-mistakes-wrapper-install.sh'), 'utf8');
assert.match(wrapperInstallText, /mktemp "\$target_dir\/\.no-mistakes-wrapper\./, 'wrapper writes must use a same-directory temp file');
assert.ok(!wrapperInstallText.includes('rm -f "$link_path"'), 'wrapper install must not unlink the active command before replacement');

console.log('no-mistakes wrapper: pass');

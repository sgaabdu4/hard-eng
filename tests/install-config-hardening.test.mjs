#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-install-hardening-'));
const fakeRoot = path.join(tmp, '.agents');
const fakeBin = path.join(tmp, 'bin');
const launchctlLog = path.join(tmp, 'launchctl.log');
const currentCron = path.join(tmp, 'current-cron');
const outputCron = path.join(tmp, 'output-cron');

function mkdir(relativePath) {
  fs.mkdirSync(path.join(fakeRoot, relativePath), { recursive: true });
}

for (const relativePath of ['scripts', 'codex/bin', 'codex', 'skills']) mkdir(relativePath);
fs.mkdirSync(fakeBin, { recursive: true });

for (const relativePath of [
  'scripts/install.sh',
  'codex/bin/codex-watchdog',
  'codex/bin/codex-health',
  'codex/bin/codex-context-mode-health',
  'codex/bin/codex-cleanup',
  'codex/bin/codex-update-stack',
]) {
  const target = path.join(fakeRoot, relativePath);
  fs.copyFileSync(path.join(repo, relativePath), target);
  fs.chmodSync(target, 0o755);
}

fs.writeFileSync(path.join(fakeRoot, 'AGENTS.md'), '# Agent Rules\n');
fs.writeFileSync(path.join(fakeRoot, 'mcp-config.json'), '{}\n');
fs.writeFileSync(path.join(fakeRoot, 'codex', 'hooks.json'), '{}\n');
fs.writeFileSync(path.join(fakeRoot, 'scripts', 'install-mcp-tools.sh'), [
  '#!/usr/bin/env bash',
  'set -euo pipefail',
  '[[ "${HARD_ENG_SKIP_NPM_INSTALL:-}" == "1" ]]',
  '',
].join('\n'));
fs.writeFileSync(path.join(fakeRoot, 'scripts', 'strip-context-mode-hooks.mjs'), 'process.exit(0);\n');
fs.writeFileSync(path.join(fakeRoot, 'scripts', 'manage-skills.mjs'), 'process.exit(0);\n');
fs.chmodSync(path.join(fakeRoot, 'scripts', 'install-mcp-tools.sh'), 0o755);
fs.chmodSync(path.join(fakeRoot, 'scripts', 'strip-context-mode-hooks.mjs'), 0o755);
fs.chmodSync(path.join(fakeRoot, 'scripts', 'manage-skills.mjs'), 0o755);

fs.writeFileSync(path.join(fakeBin, 'launchctl'), [
  '#!/usr/bin/env bash',
  '[[ -n "${HARD_ENG_FAKE_LAUNCHCTL_LOG:-}" ]] && printf "%s\\n" "$*" >> "$HARD_ENG_FAKE_LAUNCHCTL_LOG"',
  'exit 0',
  '',
].join('\n'));
fs.writeFileSync(path.join(fakeBin, 'crontab'), [
  '#!/usr/bin/env bash',
  'set -euo pipefail',
  'if [[ "${1:-}" == "-l" ]]; then',
  '  [[ -f "${HARD_ENG_FAKE_CRON_CURRENT:-}" ]] || exit 1',
  '  cat "$HARD_ENG_FAKE_CRON_CURRENT"',
  '  exit 0',
  'fi',
  'cp "$1" "$HARD_ENG_FAKE_CRON_OUT"',
  '',
].join('\n'));
fs.writeFileSync(path.join(fakeBin, 'uname'), '#!/usr/bin/env bash\nprintf "Darwin\\n"\n');
fs.writeFileSync(path.join(fakeBin, 'codex'), [
  '#!/usr/bin/env bash',
  'if [[ "${1:-}" == "doctor" ]]; then',
  '  printf \'{"overallStatus":"ok","codexVersion":"test","checks":{"mcp.config":{"details":{"configured servers":0}}}}\\n\'',
  '  exit 0',
  'fi',
  'exit 0',
  '',
].join('\n'));
fs.chmodSync(path.join(fakeBin, 'launchctl'), 0o755);
fs.chmodSync(path.join(fakeBin, 'crontab'), 0o755);
fs.chmodSync(path.join(fakeBin, 'uname'), 0o755);
fs.chmodSync(path.join(fakeBin, 'codex'), 0o755);
const gitInit = spawnSync('git', ['init'], { cwd: fakeRoot, encoding: 'utf8' });
assert.equal(gitInit.status, 0, gitInit.stderr || gitInit.stdout);

function legacyConfig() {
  return [
    'theme = "keep"',
    'approval_policy = "never"',
    'sandbox_mode = "danger-full-access"',
    '[features]',
    'hooks = true',
    'keep_feature = true',
    '[mcp_servers.codebase-memory-mcp]',
    'command = "/old/codebase-memory-mcp"',
    '[mcp_servers.context-mode]',
    'command = "context-mode"',
    '[mcp_servers.context-mode.env]',
    'CONTEXT_MODE_PLATFORM = "codex"',
    '[mcp_servers.dart]',
    'command = "dart"',
    '[profile.keep]',
    'value = 1',
    '',
  ].join('\n');
}

function baseEnv(home, overrides = {}) {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (key.startsWith('HARD_ENG_')) delete env[key];
  }
  return {
    ...env,
    HOME: home,
    PATH: `${fakeBin}:${process.env.PATH}`,
    HARD_ENG_FAKE_LAUNCHCTL_LOG: launchctlLog,
    HARD_ENG_FAKE_CRON_CURRENT: currentCron,
    HARD_ENG_FAKE_CRON_OUT: outputCron,
    HARD_ENG_SKIP_PREREQ_INSTALL: '1',
    HARD_ENG_SKIP_NPM_INSTALL: '1',
    HARD_ENG_SKIP_SUBMODULE_INIT: '1',
    HARD_ENG_SKIP_MCP_CONFIG: '1',
    HARD_ENG_SKIP_CRON: '1',
    ...overrides,
  };
}

function runInstall(home, overrides = {}) {
  const result = spawnSync('bash', [path.join(fakeRoot, 'scripts', 'install.sh')], {
    cwd: fakeRoot,
    env: baseEnv(home, overrides),
    encoding: 'utf8',
    timeout: 120000,
  });
  assert.equal(result.status, 0, result.stderr || result.stdout);
}

function writeManagedBin(home, name) {
  const target = path.join(home, '.codex', 'bin', name);
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, '#!/usr/bin/env bash\n# Managed by hard-eng installer.\n');
  fs.chmodSync(target, 0o755);
}

function writeLaunchAgent(home) {
  const target = path.join(home, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist');
  fs.mkdirSync(path.dirname(target), { recursive: true });
  fs.writeFileSync(target, '<plist version="1.0"><dict><key>Label</key><string>dev.hard-eng.codex-watchdog</string></dict></plist>\n');
}

const safeHome = path.join(tmp, 'safe-home');
fs.mkdirSync(path.join(safeHome, '.codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(safeHome, '.codex', 'config.toml'), legacyConfig());
fs.symlinkSync(path.join(fakeRoot, 'mcp-config.json'), path.join(safeHome, '.codex', 'mcp-config.json'));
fs.writeFileSync(
  path.join(safeHome, '.codex', 'bin', 'codex-update-stack'),
  '#!/usr/bin/env bash\n# Managed by hard-eng installer.\n',
);
fs.chmodSync(path.join(safeHome, '.codex', 'bin', 'codex-update-stack'), 0o755);

runInstall(safeHome);

const safeConfig = fs.readFileSync(path.join(safeHome, '.codex', 'config.toml'), 'utf8');
assert.match(safeConfig, /theme = "keep"/);
assert.match(safeConfig, /keep_feature = true/);
assert.match(safeConfig, /\[profile\.keep\]/);
assert.match(safeConfig, /default_mode_request_user_input = true/);
assert.doesNotMatch(safeConfig, /approval_policy = "never"|sandbox_mode = "danger-full-access"/);
assert.doesNotMatch(safeConfig, /mcp_servers\.(codebase-memory-mcp|context-mode|dart)/);
assert.equal(fs.existsSync(path.join(safeHome, '.codex', 'mcp-config.json')), false);
assert.equal(fs.existsSync(path.join(safeHome, '.codex', 'bin', 'codex-update-stack')), false);
assert.equal(fs.existsSync(path.join(safeHome, '.codex', 'bin', 'codex-health')), true);

const refreshHome = path.join(tmp, 'refresh-home');
fs.mkdirSync(path.join(refreshHome, '.codex'), { recursive: true });
fs.writeFileSync(path.join(refreshHome, '.codex', 'config.toml'), legacyConfig());
fs.writeFileSync(currentCron, [
  '# BEGIN hard-eng auto-sync',
  '* * * * * keep auto-sync',
  '# END hard-eng auto-sync',
  '# BEGIN hard-eng codex-stack-update',
  '* * * * * keep codex-update-stack',
  '# END hard-eng codex-stack-update',
  '',
].join('\n'));
fs.rmSync(outputCron, { force: true });
runInstall(refreshHome);
assert.equal(fs.existsSync(outputCron), false, 'skip cron refresh must not rewrite crontab');

const safeSkipHome = path.join(tmp, 'safe-skip-home');
fs.mkdirSync(path.join(safeSkipHome, '.codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(safeSkipHome, '.codex', 'config.toml'), legacyConfig());
for (const name of ['codex-watchdog', 'codex-health', 'codex-context-mode-health', 'codex-cleanup', 'codex-update-stack']) {
  writeManagedBin(safeSkipHome, name);
}
writeLaunchAgent(safeSkipHome);
fs.writeFileSync(currentCron, [
  '0 0 * * * /usr/bin/true',
  '# BEGIN hard-eng auto-sync',
  '* * * * * old auto-sync',
  '# END hard-eng auto-sync',
  '# BEGIN hard-eng codex-stack-update',
  '* * * * * old codex-update-stack',
  '# END hard-eng codex-stack-update',
  '',
].join('\n'));
fs.rmSync(outputCron, { force: true });

fs.writeFileSync(launchctlLog, '');
runInstall(safeSkipHome, { HARD_ENG_SKIP_WATCHDOG: '1', HARD_ENG_REMOVE_MANAGED_CRON: '1' });

for (const name of ['codex-watchdog', 'codex-health', 'codex-context-mode-health', 'codex-cleanup', 'codex-update-stack']) {
  assert.equal(fs.existsSync(path.join(safeSkipHome, '.codex', 'bin', name)), false, `${name} must be removed`);
}
assert.equal(fs.existsSync(path.join(safeSkipHome, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist')), false);
assert.match(fs.readFileSync(launchctlLog, 'utf8'), /bootout gui\/\d+\/dev\.hard-eng\.codex-watchdog/);
const cleanedCron = fs.readFileSync(outputCron, 'utf8');
assert.match(cleanedCron, /\/usr\/bin\/true/);
assert.doesNotMatch(cleanedCron, /hard-eng auto-sync|hard-eng codex-stack-update|old codex-update-stack/);
const safeHook = fs.readFileSync(path.join(fakeRoot, '.git', 'hooks', 'pre-push'), 'utf8');
assert.ok(!safeHook.includes('__HARD_ENG_INSTALL_REFRESH_ENV__'));
assert.ok(safeHook.includes('HARD_ENG_SKIP_MCP_CONFIG=1 \\'));
assert.ok(safeHook.includes('HARD_ENG_SKIP_WATCHDOG=1 \\'));
assert.ok(!safeHook.includes('HARD_ENG_TRUSTED_WORKSTATION=1 \\'));

const trustedHome = path.join(tmp, 'trusted-home');
fs.mkdirSync(path.join(trustedHome, '.codex'), { recursive: true });
fs.writeFileSync(path.join(trustedHome, '.codex', 'config.toml'), legacyConfig());
writeLaunchAgent(trustedHome);
fs.writeFileSync(launchctlLog, '');
runInstall(trustedHome, { HARD_ENG_TRUSTED_WORKSTATION: '1', HARD_ENG_SKIP_SHELL_PATH_UPDATE: '1' });

const trustedConfig = fs.readFileSync(path.join(trustedHome, '.codex', 'config.toml'), 'utf8');
assert.match(trustedConfig, /approval_policy = "never"/);
assert.match(trustedConfig, /sandbox_mode = "danger-full-access"/);
assert.doesNotMatch(trustedConfig, /mcp_servers\.(codebase-memory-mcp|context-mode|dart)/);
assert.equal(fs.existsSync(path.join(trustedHome, '.codex', 'bin', 'codex-update-stack')), true);
assert.match(
  fs.readFileSync(path.join(trustedHome, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist'), 'utf8'),
  /<key>HARD_ENG_TRUSTED_WORKSTATION<\/key>\s*<string>1<\/string>/,
);
const trustedPlist = fs.readFileSync(path.join(trustedHome, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist'), 'utf8');
for (const key of ['HARD_ENG_SKIP_PREREQ_INSTALL', 'HARD_ENG_SKIP_NPM_INSTALL', 'HARD_ENG_SKIP_MCP_CONFIG', 'HARD_ENG_SKIP_SHELL_PATH_UPDATE']) {
  assert.match(trustedPlist, new RegExp(`<key>${key}<\\/key>\\s*<string>1<\\/string>`));
}
assert.match(fs.readFileSync(launchctlLog, 'utf8'), /bootout gui\/\d+\/dev\.hard-eng\.codex-watchdog[\s\S]*bootstrap gui\/\d+/);
const trustedHook = fs.readFileSync(path.join(fakeRoot, '.git', 'hooks', 'pre-push'), 'utf8');
assert.ok(trustedHook.includes('HARD_ENG_TRUSTED_WORKSTATION=1 \\'));
assert.ok(trustedHook.includes('HARD_ENG_SKIP_MCP_CONFIG=1 \\'));
assert.ok(trustedHook.includes('HARD_ENG_SKIP_SHELL_PATH_UPDATE=1 \\'));

fs.writeFileSync(path.join(trustedHome, '.codex', 'bin', 'codex-context-mode-health'), '#!/bin/sh\nexit 0\n');
fs.chmodSync(path.join(trustedHome, '.codex', 'bin', 'codex-context-mode-health'), 0o755);
const healthEnv = { ...process.env, HOME: trustedHome, PATH: `${fakeBin}:${process.env.PATH}` };
for (const key of Object.keys(healthEnv)) {
  if (key.startsWith('HARD_ENG_')) delete healthEnv[key];
}
const healthResult = spawnSync(path.join(trustedHome, '.codex', 'bin', 'codex-health'), {
  cwd: repo,
  env: healthEnv,
  encoding: 'utf8',
  timeout: 120000,
});
assert.equal(healthResult.status, 0, healthResult.stderr || healthResult.stdout);
assert.match(healthResult.stdout, /manual update repair:/);
for (const key of ['HARD_ENG_TRUSTED_WORKSTATION', 'HARD_ENG_SKIP_PREREQ_INSTALL', 'HARD_ENG_SKIP_NPM_INSTALL', 'HARD_ENG_SKIP_MCP_CONFIG', 'HARD_ENG_SKIP_SHELL_PATH_UPDATE']) {
  assert.match(healthResult.stdout, new RegExp(`${key}=1`));
}

const stackRoot = path.join(tmp, 'stack-root');
const capture = path.join(tmp, 'stack-env.txt');
fs.mkdirSync(path.join(stackRoot, 'scripts'), { recursive: true });
fs.writeFileSync(path.join(stackRoot, 'scripts', 'install.sh'), [
  '#!/usr/bin/env bash',
  'env | grep -E "^HARD_ENG_(TRUSTED_WORKSTATION|SKIP_(PREREQ_INSTALL|NPM_INSTALL|MCP_CONFIG|SHELL_PATH_UPDATE))=" | sort > "$HARD_ENG_CAPTURE"',
  'exit 42',
  '',
].join('\n'));
fs.chmodSync(path.join(stackRoot, 'scripts', 'install.sh'), 0o755);
const repairEnv = { ...healthEnv, HARD_ENG_ROOT: stackRoot, HARD_ENG_CAPTURE: capture };
const repairResult = spawnSync('bash', [path.join(repo, 'codex', 'bin', 'codex-update-stack'), '--repair'], {
  cwd: repo,
  env: repairEnv,
  encoding: 'utf8',
});
assert.equal(repairResult.status, 42, repairResult.stderr || repairResult.stdout);
const capturedRepairEnv = fs.readFileSync(capture, 'utf8');
for (const key of ['HARD_ENG_TRUSTED_WORKSTATION', 'HARD_ENG_SKIP_PREREQ_INSTALL', 'HARD_ENG_SKIP_NPM_INSTALL', 'HARD_ENG_SKIP_MCP_CONFIG', 'HARD_ENG_SKIP_SHELL_PATH_UPDATE']) {
  assert.match(capturedRepairEnv, new RegExp(`${key}=1`));
}

const stackEnv = { ...process.env, HOME: path.join(tmp, 'stack-home') };
delete stackEnv.HARD_ENG_TRUSTED_WORKSTATION;
const stackResult = spawnSync('bash', [path.join(repo, 'codex', 'bin', 'codex-update-stack')], {
  cwd: repo,
  env: stackEnv,
  encoding: 'utf8',
});
assert.equal(stackResult.status, 1);
assert.match(stackResult.stderr, /trusted-workstation-only/);

const stackHelp = spawnSync('bash', [path.join(repo, 'codex', 'bin', 'codex-update-stack'), '--help'], {
  cwd: repo,
  env: stackEnv,
  encoding: 'utf8',
});
assert.equal(stackHelp.status, 0, stackHelp.stderr);

console.log('install-config-hardening-test: pass');

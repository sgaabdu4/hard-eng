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

fs.writeFileSync(path.join(fakeBin, 'launchctl'), '#!/usr/bin/env bash\nexit 0\n');
fs.writeFileSync(path.join(fakeBin, 'uname'), '#!/usr/bin/env bash\nprintf "Darwin\\n"\n');
fs.chmodSync(path.join(fakeBin, 'launchctl'), 0o755);
fs.chmodSync(path.join(fakeBin, 'uname'), 0o755);

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

const safeHome = path.join(tmp, 'safe-home');
fs.mkdirSync(path.join(safeHome, '.codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(safeHome, '.codex', 'config.toml'), legacyConfig());
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
assert.equal(fs.existsSync(path.join(safeHome, '.codex', 'bin', 'codex-update-stack')), false);
assert.equal(fs.existsSync(path.join(safeHome, '.codex', 'bin', 'codex-health')), true);

const safeSkipHome = path.join(tmp, 'safe-skip-home');
fs.mkdirSync(path.join(safeSkipHome, '.codex', 'bin'), { recursive: true });
fs.writeFileSync(path.join(safeSkipHome, '.codex', 'config.toml'), legacyConfig());
fs.writeFileSync(
  path.join(safeSkipHome, '.codex', 'bin', 'codex-update-stack'),
  '#!/usr/bin/env bash\n# Managed by hard-eng installer.\n',
);
fs.chmodSync(path.join(safeSkipHome, '.codex', 'bin', 'codex-update-stack'), 0o755);

runInstall(safeSkipHome, { HARD_ENG_SKIP_WATCHDOG: '1' });

assert.equal(fs.existsSync(path.join(safeSkipHome, '.codex', 'bin', 'codex-update-stack')), false);

const trustedHome = path.join(tmp, 'trusted-home');
fs.mkdirSync(path.join(trustedHome, '.codex'), { recursive: true });
fs.writeFileSync(path.join(trustedHome, '.codex', 'config.toml'), legacyConfig());
runInstall(trustedHome, { HARD_ENG_TRUSTED_WORKSTATION: '1' });

const trustedConfig = fs.readFileSync(path.join(trustedHome, '.codex', 'config.toml'), 'utf8');
assert.match(trustedConfig, /approval_policy = "never"/);
assert.match(trustedConfig, /sandbox_mode = "danger-full-access"/);
assert.doesNotMatch(trustedConfig, /mcp_servers\.(codebase-memory-mcp|context-mode|dart)/);
assert.equal(fs.existsSync(path.join(trustedHome, '.codex', 'bin', 'codex-update-stack')), true);
assert.match(
  fs.readFileSync(path.join(trustedHome, 'Library', 'LaunchAgents', 'dev.hard-eng.codex-watchdog.plist'), 'utf8'),
  /<key>HARD_ENG_TRUSTED_WORKSTATION<\/key>\s*<string>1<\/string>/,
);

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

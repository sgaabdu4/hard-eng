#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-setup-smoke-'));
const home = path.join(tmp, 'home');
const fakeBin = path.join(tmp, 'bin');
fs.mkdirSync(home, { recursive: true });
fs.mkdirSync(fakeBin, { recursive: true });

for (const name of ['launchctl', 'crontab']) {
  const file = path.join(fakeBin, name);
  fs.writeFileSync(file, '#!/usr/bin/env bash\nexit 0\n');
  fs.chmodSync(file, 0o755);
}

function baseEnv(homeDir, overrides = {}) {
  const env = { ...process.env };
  for (const key of Object.keys(env)) {
    if (key.startsWith('HARD_ENG_')) delete env[key];
  }
  return {
    ...env,
    HOME: homeDir,
    HARD_ENG_HOME: repo,
    PATH: `${fakeBin}:${process.env.PATH}`,
    ...overrides,
  };
}

const env = baseEnv(home, {
  HARD_ENG_SKILLS: 'he-plan,no-mistakes',
  HARD_ENG_SKIP_PREREQ_INSTALL: '1',
  HARD_ENG_SKIP_NPM_INSTALL: '1',
  HARD_ENG_SKIP_SUBMODULE_INIT: '1',
  HARD_ENG_SKIP_WATCHDOG: '1',
  HARD_ENG_SKIP_CRON: '1',
  HARD_ENG_SKIP_NO_MISTAKES: '1',
  HARD_ENG_SKIP_NO_MISTAKES_INIT: '1',
  HARD_ENG_SKIP_TREEHOUSE: '1',
  HARD_ENG_SKIP_WORKTREE_READY: '1',
});

const result = spawnSync('bash', [path.join(repo, 'scripts', 'setup.sh'), '--skills-only'], {
  cwd: repo,
  env,
  encoding: 'utf8',
  timeout: 120000,
});
assert.equal(result.status, 0, result.stderr || result.stdout);

function assertLink(relativePath, target) {
  const absolutePath = path.join(home, relativePath);
  assert.ok(fs.lstatSync(absolutePath).isSymbolicLink(), `${relativePath} must be a symlink`);
  assert.equal(fs.readlinkSync(absolutePath), target);
}

assertLink('.codex/AGENTS.md', path.join(repo, 'AGENTS.md'));
assertLink('.codex/hooks.json', path.join(repo, 'codex', 'hooks.json'));
assertLink('.codex/skills/he-plan', path.join(repo, 'skills', 'he-plan'));
assertLink('.codex/skills/no-mistakes', path.join(repo, 'skills', 'no-mistakes'));
assert.equal(fs.existsSync(path.join(home, '.codex', 'skills', 'he-verify')), false);
const codexConfig = fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8');
assert.match(codexConfig, /default_mode_request_user_input = true/);
assert.doesNotMatch(codexConfig, /mcp_servers\.codebase-memory-mcp/);
assert.doesNotMatch(codexConfig, /approval_policy = "never"|sandbox_mode = "danger-full-access"/);
assert.equal(fs.existsSync(path.join(home, '.codex', 'bin', 'codebase-memory-mcp')), false);
assert.deepEqual(
  JSON.parse(fs.readFileSync(path.join(home, '.config', 'hard-eng', 'skills.json'), 'utf8')),
  { selection: 'he-plan,no-mistakes' },
);
assert.equal(fs.existsSync(path.join(home, '.cache', 'hard-eng')), false);

const defaultHome = path.join(tmp, 'default-home');
fs.mkdirSync(defaultHome, { recursive: true });
const defaultResult = spawnSync('bash', [path.join(repo, 'scripts', 'setup.sh')], {
  cwd: repo,
  env: baseEnv(defaultHome, {
    HARD_ENG_SKIP_SUBMODULE_INIT: '1',
  }),
  encoding: 'utf8',
  timeout: 120000,
});
assert.equal(defaultResult.status, 0, defaultResult.stderr || defaultResult.stdout);

function assertDefaultLink(relativePath, target) {
  const absolutePath = path.join(defaultHome, relativePath);
  assert.ok(fs.lstatSync(absolutePath).isSymbolicLink(), `${relativePath} must be a symlink in default safe setup`);
  assert.equal(fs.readlinkSync(absolutePath), target);
}

assertDefaultLink('.codex/AGENTS.md', path.join(repo, 'AGENTS.md'));
assertDefaultLink('.codex/hooks.json', path.join(repo, 'codex', 'hooks.json'));
assertDefaultLink('.codex/skills/he-plan', path.join(repo, 'skills', 'he-plan'));
assertDefaultLink('.codex/skills/he-verify', path.join(repo, 'skills', 'he-verify'));
const defaultCodexConfig = fs.readFileSync(path.join(defaultHome, '.codex', 'config.toml'), 'utf8');
assert.match(defaultCodexConfig, /default_mode_request_user_input = true/);
assert.doesNotMatch(defaultCodexConfig, /mcp_servers\.codebase-memory-mcp/);
assert.doesNotMatch(defaultCodexConfig, /approval_policy = "never"|sandbox_mode = "danger-full-access"/);
assert.equal(fs.existsSync(path.join(defaultHome, '.codex', 'bin', 'codex-watchdog')), false);
assert.equal(fs.existsSync(path.join(defaultHome, '.codex', 'bin', 'codebase-memory-mcp')), false);
assert.equal(fs.existsSync(path.join(defaultHome, '.zshenv')), false);
assert.equal(fs.existsSync(path.join(defaultHome, '.cache', 'hard-eng')), false);

console.log('setup-isolated-install-test: pass');

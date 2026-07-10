#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-uninstall-'));
const fakeRoot = path.join(tmp, '.agents');
const home = path.join(tmp, 'home');
const bin = path.join(tmp, 'bin');
const protectedRepo = path.join(tmp, 'protected-repo');
const protectedHook = path.join(protectedRepo, '.git', 'hooks', 'pre-push');
fs.mkdirSync(path.join(fakeRoot, 'scripts'), { recursive: true });
fs.mkdirSync(path.join(home, '.codex'), { recursive: true });
fs.mkdirSync(path.join(home, '.copilot'), { recursive: true });
fs.mkdirSync(bin, { recursive: true });

const cleanGitEnv = { ...process.env };
const localGitEnv = spawnSync('git', ['rev-parse', '--local-env-vars'], { encoding: 'utf8' });
for (const name of localGitEnv.stdout.trim().split(/\s+/).filter(Boolean)) delete cleanGitEnv[name];
const protectedInit = spawnSync('git', ['init', '-q', '-b', 'main', protectedRepo], {
  encoding: 'utf8',
  env: cleanGitEnv,
});
assert.equal(protectedInit.status, 0, protectedInit.stderr);
fs.writeFileSync(protectedHook, '#!/usr/bin/env sh\n# Managed by hard-eng installer.\n', { mode: 0o755 });

fs.copyFileSync(path.join(repo, 'scripts', 'uninstall.sh'), path.join(fakeRoot, 'scripts', 'uninstall.sh'));
fs.chmodSync(path.join(fakeRoot, 'scripts', 'uninstall.sh'), 0o755);
fs.copyFileSync(path.join(repo, 'scripts', 'no-mistakes-wrapper-install.sh'), path.join(fakeRoot, 'scripts', 'no-mistakes-wrapper-install.sh'));
fs.writeFileSync(path.join(fakeRoot, 'scripts', 'manage-skills.mjs'), '#!/usr/bin/env node\nprocess.exit(0);\n');
fs.chmodSync(path.join(fakeRoot, 'scripts', 'manage-skills.mjs'), 0o755);
for (const name of ['crontab', 'launchctl']) {
  fs.writeFileSync(path.join(bin, name), '#!/usr/bin/env bash\nexit 0\n');
  fs.chmodSync(path.join(bin, name), 0o755);
}

fs.writeFileSync(path.join(home, '.codex', 'config.toml'), [
  'theme = "keep"',
  'approval_policy = "never"',
  'sandbox_mode = "danger-full-access"',
  '[features]',
  'hooks = true',
  'default_mode_request_user_input = true',
  'keep_feature = true',
  '[mcp_servers.codebase-memory-mcp]',
  'command = "/tmp/codebase-memory-mcp"',
  '[mcp_servers.codebase-memory-mcp.tools.search_code]',
  'approval_mode = "approve"',
  '[mcp_servers.context-mode]',
  'command = "context-mode"',
  '[mcp_servers.context-mode.env]',
  'CONTEXT_MODE_PLATFORM = "codex"',
  '[mcp_servers.context-mode.tools.ctx_execute]',
  'approval_mode = "approve"',
  '[mcp_servers.dart]',
  'command = "dart"',
  '[mcp_servers.dart.tools.read_package_uris]',
  'approval_mode = "approve"',
  '[profile.keep]',
  'value = 1',
  '',
].join('\n'));

for (const rel of ['.codex/settings.json', '.copilot/settings.json']) {
  fs.writeFileSync(path.join(home, rel), JSON.stringify({
    permissions: {
      allow: [
        `Read(${home}/.codex/skills/**)`,
        `Read(${fakeRoot}/skills/**)`,
        `Read(${fakeRoot}/vendor/skill-upstreams/**)`,
        'Read(/tmp/keep/**)',
      ],
    },
  }, null, 2));
}

const customNmHome = path.join(tmp, 'custom nm-home');
const customRealBinary = path.join(customNmHome, 'bin', 'no-mistakes');
const noMistakesLink = path.join(home, '.local', 'bin', 'no-mistakes');
fs.mkdirSync(path.dirname(customRealBinary), { recursive: true });
fs.mkdirSync(path.dirname(noMistakesLink), { recursive: true });
fs.writeFileSync(customRealBinary, '#!/usr/bin/env bash\nexit 0\n', { mode: 0o755 });
const wrapperInstall = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'install_no_mistakes_wrapper "$LINK_PATH" "$REAL_BIN" "$ROOT/scripts/no-mistakes-wrapper.sh" "$NM_DEFAULT" "$HE_DEFAULT"',
].join('\n')], {
  cwd: repo,
  env: {
    ...process.env,
    ROOT: repo,
    LINK_PATH: noMistakesLink,
    REAL_BIN: customRealBinary,
    NM_DEFAULT: customNmHome,
    HE_DEFAULT: fakeRoot,
  },
  encoding: 'utf8',
});
assert.equal(wrapperInstall.status, 0, wrapperInstall.stderr || wrapperInstall.stdout);

const result = spawnSync('bash', ['scripts/uninstall.sh', '--yes'], {
  cwd: fakeRoot,
  env: {
    ...cleanGitEnv,
    HOME: home,
    PATH: `${bin}:${process.env.PATH}`,
    GIT_DIR: path.join(protectedRepo, '.git'),
    GIT_WORK_TREE: protectedRepo,
  },
  encoding: 'utf8',
});
assert.equal(result.status, 0, result.stderr);
assert.ok(fs.existsSync(protectedHook), 'uninstall must ignore inherited Git context from a calling hook');

const config = fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8');
assert.match(config, /theme = "keep"/);
assert.match(config, /\[profile\.keep\]/);
assert.match(config, /keep_feature = true/);
assert.doesNotMatch(config, /approval_policy = "never"|sandbox_mode = "danger-full-access"|mcp_servers\.(codebase-memory-mcp|context-mode|dart)/);

for (const rel of ['.codex/settings.json', '.copilot/settings.json']) {
  const settings = JSON.parse(fs.readFileSync(path.join(home, rel), 'utf8'));
  assert.deepEqual(settings.permissions.allow, ['Read(/tmp/keep/**)']);
}

assert.equal(fs.lstatSync(noMistakesLink).isSymbolicLink(), true, 'uninstall must restore the upstream no-mistakes symlink');
assert.equal(fs.readlinkSync(noMistakesLink), customRealBinary);

const missingNmHome = path.join(tmp, 'missing nm-home');
const missingRealBinary = path.join(missingNmHome, 'bin', 'no-mistakes');
fs.rmSync(noMistakesLink, { force: true });
const missingInstall = spawnSync('bash', ['-c', [
  'set -euo pipefail',
  'source "$ROOT/scripts/no-mistakes-wrapper-install.sh"',
  'install_no_mistakes_wrapper "$LINK_PATH" "$REAL_BIN" "$ROOT/scripts/no-mistakes-wrapper.sh" "$NM_DEFAULT" "$HE_DEFAULT"',
].join('\n')], {
  cwd: repo,
  env: {
    ...process.env,
    ROOT: repo,
    LINK_PATH: noMistakesLink,
    REAL_BIN: missingRealBinary,
    NM_DEFAULT: missingNmHome,
    HE_DEFAULT: fakeRoot,
  },
  encoding: 'utf8',
});
assert.equal(missingInstall.status, 0, missingInstall.stderr || missingInstall.stdout);
assert.match(fs.readFileSync(noMistakesLink, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);

const missingResult = spawnSync('bash', ['scripts/uninstall.sh', '--yes'], {
  cwd: fakeRoot,
  env: { ...process.env, HOME: home, PATH: `${bin}:${process.env.PATH}` },
  encoding: 'utf8',
});
assert.equal(missingResult.status, 0, missingResult.stderr);
assert.match(missingResult.stderr, /Preserving managed no-mistakes wrapper because upstream binary is missing/);
assert.match(fs.readFileSync(noMistakesLink, 'utf8'), /Managed by hard-eng no-mistakes wrapper/);

console.log('uninstall-config-cleanup-test: pass');

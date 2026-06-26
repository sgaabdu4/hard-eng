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
fs.mkdirSync(path.join(fakeRoot, 'scripts'), { recursive: true });
fs.mkdirSync(path.join(home, '.codex'), { recursive: true });
fs.mkdirSync(path.join(home, '.copilot'), { recursive: true });
fs.mkdirSync(bin, { recursive: true });

fs.copyFileSync(path.join(repo, 'scripts', 'uninstall.sh'), path.join(fakeRoot, 'scripts', 'uninstall.sh'));
fs.chmodSync(path.join(fakeRoot, 'scripts', 'uninstall.sh'), 0o755);
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
  '[mcp_servers.context-mode]',
  'command = "context-mode"',
  '[mcp_servers.context-mode.env]',
  'CONTEXT_MODE_PLATFORM = "codex"',
  '[mcp_servers.dart]',
  'command = "dart"',
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

const result = spawnSync('bash', ['scripts/uninstall.sh', '--yes'], {
  cwd: fakeRoot,
  env: { ...process.env, HOME: home, PATH: `${bin}:${process.env.PATH}` },
  encoding: 'utf8',
});
assert.equal(result.status, 0, result.stderr);

const config = fs.readFileSync(path.join(home, '.codex', 'config.toml'), 'utf8');
assert.match(config, /theme = "keep"/);
assert.match(config, /\[profile\.keep\]/);
assert.match(config, /keep_feature = true/);
assert.doesNotMatch(config, /approval_policy = "never"|sandbox_mode = "danger-full-access"|mcp_servers\.context-mode|mcp_servers\.dart/);

for (const rel of ['.codex/settings.json', '.copilot/settings.json']) {
  const settings = JSON.parse(fs.readFileSync(path.join(home, rel), 'utf8'));
  assert.deepEqual(settings.permissions.allow, ['Read(/tmp/keep/**)']);
}

console.log('uninstall-config-cleanup-test: pass');

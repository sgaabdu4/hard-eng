#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import os from 'node:os';
import { spawnSync } from 'node:child_process';

const home = process.env.HOME;
const canonical = path.join(home, '.agents', 'codex', 'hooks.json');
const hooks = JSON.parse(fs.readFileSync(canonical, 'utf8')).hooks;
const serializedHooks = JSON.stringify(hooks);
const scrubber = path.join(home, '.agents', 'scripts', 'strip-context-mode-hooks.mjs');
const scrubberText = fs.readFileSync(scrubber, 'utf8');
const installScript = fs.readFileSync(path.join(home, '.agents', 'scripts', 'install.sh'), 'utf8');

assert.ok(hooks.PreToolUse, 'PreToolUse hook must exist');
assert.equal(hooks.SessionStart, undefined, 'SessionStart hook must stay disabled');
assert.equal(hooks.PreCompact, undefined, 'PreCompact hook must stay disabled');
assert.equal(hooks.UserPromptSubmit, undefined, 'UserPromptSubmit hook must stay disabled');
assert.equal(hooks.Stop, undefined, 'Stop hook must stay disabled');
assert.equal(hooks.PostToolUse, undefined, 'global PostToolUse hook must stay disabled');

const serializedPreToolUse = JSON.stringify(hooks.PreToolUse);
assert.ok(
  serializedPreToolUse.includes('security-pretooluse.js'),
  'security PreToolUse hook must stay wired',
);
assert.ok(
  !serializedHooks.includes('context-mode hook'),
  'context-mode hooks must stay stripped from Codex hooks',
);
assert.ok(
  !fs.existsSync(path.join(home, '.agents', 'hooks', 'codex-sessionstart-quiet.js')),
  'quiet SessionStart wrapper must stay deleted',
);
assert.ok(
  installScript.includes('install_codex_hooks_config'),
  'new-system setup must force canonical Codex hook config',
);
assert.ok(
  installScript.includes('strip-context-mode-hooks.mjs'),
  'install must strip context-mode hooks after setup/upgrade drift',
);
for (const target of [
  "'.codex', 'settings.json'",
  "'.claude', 'settings.json'",
  "'.claude', 'settings.local.json'",
  "'.copilot', 'settings.json'",
  "'.pi', 'agent', 'settings.json'",
]) {
  assert.ok(scrubberText.includes(target), `scrubber must cover ${target}`);
}

const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'codex-hooks-strip-'));
const pollutedHooks = path.join(tmpDir, 'hooks.json');
const pollutedSettings = path.join(tmpDir, 'settings.json');
fs.writeFileSync(
  pollutedHooks,
  JSON.stringify(
    {
      hooks: {
        PreToolUse: [
          {
            matcher: '.*',
            hooks: [
              { type: 'command', command: 'node "$HOME/.agents/hooks/security-pretooluse.js"' },
              { type: 'command', command: 'context-mode hook codex pretooluse' },
            ],
          },
        ],
        Stop: [
          {
            matcher: '',
            hooks: [{ type: 'command', command: 'context-mode hook codex stop' }],
          },
        ],
      },
    },
    null,
    2,
  ),
);
fs.writeFileSync(
  pollutedSettings,
  JSON.stringify(
    {
      hooks: {
        UserPromptSubmit: [
          {
            matcher: '',
            hooks: [
              { type: 'command', command: 'context-mode hook claude userpromptsubmit' },
              { type: 'command', command: 'node "$HOME/.agents/hooks/security-pretooluse.js"' },
            ],
          },
        ],
      },
      permissions: { allow: ['Read(/tmp/example)'] },
    },
    null,
    2,
  ),
);

const scrubRun = spawnSync('node', [scrubber, pollutedHooks, pollutedSettings], {
  encoding: 'utf8',
});
assert.equal(scrubRun.status, 0, `strip-context-mode-hooks failed: ${scrubRun.stderr}`);
const cleanedHooks = JSON.parse(fs.readFileSync(pollutedHooks, 'utf8')).hooks;
assert.ok(!JSON.stringify(cleanedHooks).includes('context-mode hook'), 'scrubber must remove context-mode hooks');
assert.ok(JSON.stringify(cleanedHooks.PreToolUse).includes('security-pretooluse.js'), 'scrubber must keep security hooks');
assert.equal(cleanedHooks.Stop, undefined, 'scrubber must remove empty hook events');
const cleanedSettings = JSON.parse(fs.readFileSync(pollutedSettings, 'utf8'));
assert.ok(!JSON.stringify(cleanedSettings).includes('context-mode hook'), 'scrubber must clean non-Codex settings');
assert.ok(JSON.stringify(cleanedSettings.hooks.UserPromptSubmit).includes('security-pretooluse.js'), 'scrubber must preserve non-Codex hooks');
assert.deepEqual(cleanedSettings.permissions.allow, ['Read(/tmp/example)'], 'scrubber must not touch non-hook settings');

const installed = path.join(home, '.codex', 'hooks.json');
if (fs.existsSync(installed)) {
  const stat = fs.lstatSync(installed);
  assert.ok(stat.isSymbolicLink(), `${installed} must be a symlink`);
  assert.equal(fs.realpathSync(installed), fs.realpathSync(canonical), `${installed} must point to ${canonical}`);
}

console.log('codex-hooks-contract: pass');

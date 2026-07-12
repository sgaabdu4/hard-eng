import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createCodexPluginClient } from '../../plugins/hard-eng/runtime/lib/codex-plugin.mjs';

const sourceRoot = path.resolve('.');
const optionalNames = [
  'hard-eng-flutter', 'hard-eng-appwrite', 'hard-eng-web',
  'hard-eng-sentry', 'hard-eng-delivery', 'hard-eng-authoring',
];

function installedHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-codex-plugin-'));
  const target = path.join(home, '.agents', 'plugins', 'hard-eng', '.codex-plugin');
  fs.mkdirSync(target, { recursive: true });
  fs.copyFileSync(path.join(sourceRoot, 'plugins', 'hard-eng', '.codex-plugin', 'plugin.json'), path.join(target, 'plugin.json'));
  return home;
}

function fakeRun({ installed = false, version = '1.0.0', conflict = false, hooks = true } = {}) {
  const state = { installed, version, conflict, hooks };
  const run = (args, { home }) => {
    if (args.join(' ') === 'features list') {
      return { status: 0, stdout: `hooks stable ${state.hooks}\nplugin_hooks removed false\n`, stderr: '', error: null };
    }
    if (args[0] === 'plugin' && args[1] === 'add') {
      state.installed = true;
      state.version = '1.0.0';
      return { status: 0, stdout: '{"pluginId":"hard-eng@personal"}', stderr: '', error: null };
    }
    if (args[0] === 'plugin' && args[1] === 'remove') {
      state.installed = false;
      return { status: 0, stdout: '{"pluginId":"hard-eng@personal"}', stderr: '', error: null };
    }
    if (args.slice(0, 3).join(' ') === 'plugin list --available') {
      const source = path.join(home, '.agents', 'plugins');
      const core = {
        pluginId: 'hard-eng@personal', name: 'hard-eng', marketplaceName: 'personal',
        version: state.version, installed: state.installed, enabled: state.installed,
        source: { source: 'local', path: path.join(source, 'hard-eng') },
      };
      const optional = optionalNames.map((name) => ({
        pluginId: `${name}@personal`, name, marketplaceName: 'personal', version: '1.0.0',
        installed: false, enabled: false, source: { source: 'local', path: path.join(source, name) },
      }));
      const other = state.conflict ? [{
        pluginId: 'hard-eng@other', name: 'hard-eng', installed: true, enabled: true,
        version: '9.0.0', source: { source: 'local', path: path.join(home, 'other') },
      }] : [];
      const value = state.installed
        ? { installed: [core, ...other], available: optional }
        : { installed: other, available: [core, ...optional] };
      return { status: 0, stdout: JSON.stringify(value), stderr: '', error: null };
    }
    return { status: 2, stdout: '', stderr: 'unsupported fake command', error: null };
  };
  return { state, run };
}

test('Codex plugin reconciliation installs, verifies, updates, and removes the exact core owner', () => {
  const fake = fakeRun({ installed: false, version: '0.9.0' });
  const client = createCodexPluginClient({ run: fake.run, env: { PATH: process.env.PATH } });
  const home = installedHome();
  assert.equal(client.inspect(home).status, 'FAIL');

  const installed = client.reconcile(home, true);
  assert.equal(installed.status, 'PASS');
  assert.equal(installed.action, 'add');
  assert.equal(client.inspect(home).status, 'PASS');

  fake.state.version = '0.9.0';
  assert.equal(client.reconcile(home, true).status, 'PASS');
  assert.equal(client.inspect(home).core.version_matches, true);

  assert.equal(client.reconcile(home, false).status, 'PASS');
  assert.equal(client.inspect(home).core.installed, false);
});

test('Codex plugin reconciliation fails closed on another hard-eng owner or disabled hooks', () => {
  const conflict = fakeRun({ conflict: true });
  const conflicting = createCodexPluginClient({ run: conflict.run });
  const home = installedHome();
  assert.throws(() => conflicting.reconcile(home, true), /another hard-eng plugin owner/i);

  const hooksOff = fakeRun({ hooks: false });
  const disabled = createCodexPluginClient({ run: hooksOff.run });
  assert.throws(() => disabled.reconcile(home, true), /approved state/i);
  assert.equal(disabled.inspect(home).hooks_feature, false);
});

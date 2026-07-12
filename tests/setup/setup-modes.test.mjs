import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makePluginClient } from '../fixtures/plugin-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const pluginClient = makePluginClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { ...options, pluginClient });
}

function home(prefix) {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

function manifest(targetHome) {
  return JSON.parse(fs.readFileSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8'));
}

test('install is dry-run-first, approval-bound, idempotent, and hash-owned', () => {
  const targetHome = home('hard-eng-setup-install-');
  const dry = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  assert.equal(dry.status, 'DRY_RUN');
  assert.match(dry.plan_digest, /^[a-f0-9]{64}$/);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents')), false);

  const approval = runSetup(['install', '--home', targetHome], { sourceRoot, now: NOW });
  assert.equal(approval.status, 'APPROVAL_REQUIRED');
  assert.equal(approval.plan_digest, dry.plan_digest);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents')), false);

  const installed = runSetup([
    'install', '--home', targetHome, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW });
  assert.equal(installed.status, 'PASS');
  assert.ok(installed.changed > 0);
  assert.match(installed.rollback_bundle, /^[a-f0-9]{64}$/);
  assert.equal(
    fs.readFileSync(path.join(targetHome, '.agents', 'AGENTS.md'), 'utf8'),
    fs.readFileSync(path.join(sourceRoot, 'AGENTS.md'), 'utf8'),
  );
  const codexAgents = path.join(targetHome, '.codex', 'AGENTS.md');
  assert.equal(fs.lstatSync(codexAgents).isSymbolicLink(), true);
  assert.equal(fs.realpathSync(codexAgents), fs.realpathSync(path.join(targetHome, '.agents', 'AGENTS.md')));
  assert.equal(fs.statSync(path.join(targetHome, '.local', 'bin', 'he')).mode & 0o777, 0o755);
  const owned = manifest(targetHome);
  assert.equal(owned.schema, 'hard-eng/install-manifest/v1');
  assert.equal(owned.status, 'installed');
  assert.ok(owned.entries.length > 20);
  assert.equal(owned.entries.find((entry) => entry.path === '.codex/AGENTS.md').expected_type, 'symlink');
  assert.ok(owned.entries.every((entry) => !path.isAbsolute(entry.path)));
  assert.doesNotMatch(fs.readFileSync(path.join(targetHome, '.local', 'bin', 'he'), 'utf8'), new RegExp(sourceRoot));

  const again = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 1 });
  const repeated = runSetup([
    'install', '--home', targetHome, '--confirm', again.plan_digest,
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(repeated.status, 'PASS');
  assert.equal(repeated.changed, 0);

  const launcher = path.join(targetHome, '.local', 'bin', 'he');
  fs.chmodSync(launcher, 0o644);
  const repair = runSetup(['update', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 2 });
  assert.equal(repair.operations.find((operation) => operation.path === '.local/bin/he').action, 'write');
  runSetup(['update', '--home', targetHome, '--confirm', repair.plan_digest], { sourceRoot, now: NOW + 2 });
  assert.equal(fs.statSync(launcher).mode & 0o777, 0o755);
});

test('a successful install keeps a private approval-bound live rollback bundle', () => {
  const targetHome = home('hard-eng-setup-live-rollback-');
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  const applied = runSetup([
    'install', '--home', targetHome, '--confirm', install.plan_digest,
  ], { sourceRoot, now: NOW });
  assert.equal(pluginClient.inspect(targetHome).core.installed, true);
  const bundleRoot = path.join(targetHome, '.agents', '.hard-eng-install', 'backups', applied.rollback_bundle);
  assert.equal(fs.statSync(bundleRoot).mode & 0o777, 0o700);
  assert.equal(fs.statSync(path.join(bundleRoot, 'receipt.json')).mode & 0o777, 0o600);

  const dry = runSetup([
    'rollback', '--home', targetHome, '--backup', applied.rollback_bundle, '--dry-run',
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(dry.status, 'DRY_RUN');
  assert.equal(dry.mode, 'rollback');
  assert.ok(dry.operations.some((operation) => operation.path === '.local/bin/he' && operation.action === 'remove-created'));
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), true);

  const manifestBeforeRollback = fs.readFileSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8');
  assert.throws(() => runSetup([
    'rollback', '--home', targetHome, '--backup', applied.rollback_bundle, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 1, failAfter: 1 }), /injected rollback failure/i);
  assert.equal(pluginClient.inspect(targetHome).core.installed, true);
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), true);
  assert.equal(
    fs.readFileSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8'),
    manifestBeforeRollback,
  );

  const restored = runSetup([
    'rollback', '--home', targetHome, '--backup', applied.rollback_bundle, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(restored.status, 'PASS');
  assert.equal(pluginClient.inspect(targetHome).core.installed, false);
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', 'plugins', 'hard-eng')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json')), false);
  assert.equal(fs.existsSync(path.join(bundleRoot, 'receipt.json')), true);

  const reinstall = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 2 });
  const reapplied = runSetup([
    'install', '--home', targetHome, '--confirm', reinstall.plan_digest,
  ], { sourceRoot, now: NOW + 2 });
  assert.equal(reapplied.status, 'PASS');
  assert.equal(pluginClient.inspect(targetHome).core.installed, true);
  assert.notEqual(reapplied.rollback_bundle, applied.rollback_bundle);
});

test('rollback refuses target drift and leaves the approved bundle untouched', () => {
  const targetHome = home('hard-eng-setup-rollback-drift-');
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  const applied = runSetup([
    'install', '--home', targetHome, '--confirm', install.plan_digest,
  ], { sourceRoot, now: NOW });
  const launcher = path.join(targetHome, '.local', 'bin', 'he');
  fs.appendFileSync(launcher, '# local drift\n');
  assert.throws(() => runSetup([
    'rollback', '--home', targetHome, '--backup', applied.rollback_bundle, '--dry-run',
  ], { sourceRoot, now: NOW + 1 }), /changed after cutover/i);
  assert.match(fs.readFileSync(launcher, 'utf8'), /local drift/);
  assert.equal(
    fs.existsSync(path.join(targetHome, '.agents', '.hard-eng-install', 'backups', applied.rollback_bundle, 'receipt.json')),
    true,
  );
});

test('update refuses modified owned files and rolls back an interrupted switch', () => {
  const targetHome = home('hard-eng-setup-update-');
  const installPlan = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', installPlan.plan_digest], { sourceRoot, now: NOW });
  const targetAgents = path.join(targetHome, '.agents', 'AGENTS.md');
  fs.appendFileSync(targetAgents, '\nuser change\n');
  assert.throws(() => runSetup(['update', '--home', targetHome, '--dry-run'], {
    sourceRoot, now: NOW + 1,
  }), /modified owned file/i);
  assert.match(fs.readFileSync(targetAgents, 'utf8'), /user change/);

  const cleanHome = home('hard-eng-setup-rollback-');
  const first = runSetup(['install', '--home', cleanHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', cleanHome, '--confirm', first.plan_digest], { sourceRoot, now: NOW });
  const beforeAgents = fs.readFileSync(path.join(cleanHome, '.agents', 'AGENTS.md'), 'utf8');
  const beforeManifest = fs.readFileSync(path.join(cleanHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8');
  const alternate = home('hard-eng-setup-source-');
  fs.cpSync(path.join(sourceRoot, 'plugins'), path.join(alternate, 'plugins'), { recursive: true });
  fs.mkdirSync(path.join(alternate, 'scripts'), { recursive: true });
  for (const file of ['AGENTS.md', 'THIRD_PARTY_NOTICES.md', 'package.json']) {
    fs.copyFileSync(path.join(sourceRoot, file), path.join(alternate, file));
  }
  fs.appendFileSync(path.join(alternate, 'AGENTS.md'), '\nUpdated source fixture.\n');
  const update = runSetup(['update', '--home', cleanHome, '--dry-run'], { sourceRoot: alternate, now: NOW + 2 });
  assert.throws(() => runSetup([
    'update', '--home', cleanHome, '--confirm', update.plan_digest,
  ], { sourceRoot: alternate, now: NOW + 2, failAfter: 1 }), /injected transaction failure/i);
  assert.equal(fs.readFileSync(path.join(cleanHome, '.agents', 'AGENTS.md'), 'utf8'), beforeAgents);
  assert.equal(fs.readFileSync(path.join(cleanHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8'), beforeManifest);
});

test('uninstall removes only matching owned files and preserves installer/run state by default', () => {
  const targetHome = home('hard-eng-setup-uninstall-');
  const install = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
  const dry = runSetup(['uninstall', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 1 });
  assert.equal(dry.status, 'DRY_RUN');
  const removed = runSetup([
    'uninstall', '--home', targetHome, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(removed.status, 'PASS');
  assert.equal(pluginClient.inspect(targetHome).core.installed, false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', 'plugins', 'hard-eng')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.codex', 'AGENTS.md')), false);
  assert.equal(manifest(targetHome).status, 'uninstalled');
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', '.hard-eng-install')), true);
});

test('setup rejects symlinked parent directories instead of escaping the selected home', () => {
  const targetHome = home('hard-eng-setup-symlink-home-');
  const outside = home('hard-eng-setup-symlink-outside-');
  fs.symlinkSync(outside, path.join(targetHome, '.agents'));
  assert.throws(() => runSetup(['install', '--home', targetHome, '--dry-run'], {
    sourceRoot, now: NOW,
  }), /symlink|unsafe/i);
  assert.deepEqual(fs.readdirSync(outside), []);
});

test('installer-private manifest, transaction, and backup paths cannot follow a symlink', () => {
  const targetHome = home('hard-eng-setup-state-symlink-home-');
  const outside = home('hard-eng-setup-state-symlink-outside-');
  fs.mkdirSync(path.join(targetHome, '.agents'), { recursive: true });
  fs.symlinkSync(outside, path.join(targetHome, '.agents', '.hard-eng-install'));

  assert.throws(() => runSetup(['install', '--home', targetHome, '--dry-run'], {
    sourceRoot, now: NOW,
  }), /symlink|unsafe/i);
  assert.deepEqual(fs.readdirSync(outside), []);
});

test('personal marketplace merge preserves unrelated plugins through install and uninstall', () => {
  const targetHome = home('hard-eng-setup-marketplace-');
  const file = path.join(targetHome, '.agents', 'plugins', 'marketplace.json');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify({
    name: 'personal',
    interface: { displayName: 'My Personal Plugins' },
    plugins: [{
      name: 'personal-tool',
      source: { source: 'local', path: './.agents/plugins/personal-tool' },
      policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
      category: 'Developer Tools',
    }],
  }, null, 2)}\n`);

  const dry = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', targetHome, '--confirm', dry.plan_digest], { sourceRoot, now: NOW });
  let marketplace = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.ok(marketplace.plugins.some((entry) => entry.name === 'personal-tool'));
  assert.ok(marketplace.plugins.some((entry) => entry.name === 'hard-eng'));

  const remove = runSetup(['uninstall', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 1 });
  runSetup(['uninstall', '--home', targetHome, '--confirm', remove.plan_digest], { sourceRoot, now: NOW + 1 });
  marketplace = JSON.parse(fs.readFileSync(file, 'utf8'));
  assert.deepEqual(marketplace.plugins.map((entry) => entry.name), ['personal-tool']);
  assert.equal(marketplace.interface.displayName, 'My Personal Plugins');
});

test('personal marketplace merge refuses an unowned hard-eng name collision', () => {
  const targetHome = home('hard-eng-setup-marketplace-conflict-');
  const file = path.join(targetHome, '.agents', 'plugins', 'marketplace.json');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, `${JSON.stringify({
    name: 'personal',
    plugins: [{
      name: 'hard-eng',
      source: { source: 'local', path: './somewhere-else/hard-eng' },
      policy: { installation: 'AVAILABLE', authentication: 'ON_INSTALL' },
    }],
  })}\n`);
  assert.throws(() => runSetup(['install', '--home', targetHome, '--dry-run'], {
    sourceRoot, now: NOW,
  }), /hard-eng.*owner|collision/i);
});

const realCodexAvailable = spawnSync('codex', ['--version'], { encoding: 'utf8' }).status === 0;

test('real Codex CLI discovers, activates, and removes the isolated core plugin', {
  skip: realCodexAvailable ? false : 'Codex CLI is unavailable in this test environment.',
}, () => {
  const targetHome = home('hard-eng-setup-real-codex-');
  const dry = baseRunSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW });
  const installed = baseRunSetup([
    'install', '--home', targetHome, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW });
  assert.equal(installed.status, 'PASS');

  const env = { ...process.env, HOME: targetHome };
  delete env.CODEX_HOME;
  const listed = spawnSync('codex', ['plugin', 'list', '--available', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(listed.status, 0, listed.stderr);
  const inventory = JSON.parse(listed.stdout);
  const core = inventory.installed.find((entry) => entry.pluginId === 'hard-eng@personal');
  assert.equal(core?.enabled, true);
  assert.equal(fs.realpathSync(core.source.path), fs.realpathSync(path.join(targetHome, '.agents', 'plugins', 'hard-eng')));
  assert.ok(inventory.available.filter((entry) => entry.name.startsWith('hard-eng-')).every((entry) => !entry.installed && !entry.enabled));

  const remove = baseRunSetup(['uninstall', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 1 });
  baseRunSetup(['uninstall', '--home', targetHome, '--confirm', remove.plan_digest], { sourceRoot, now: NOW + 1 });
  const after = spawnSync('codex', ['plugin', 'list', '--available', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(after.status, 0, after.stderr);
  assert.equal(JSON.parse(after.stdout).installed.some((entry) => entry.pluginId === 'hard-eng@personal'), false);
});

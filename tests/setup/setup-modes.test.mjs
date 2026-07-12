import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makeWiringClient } from '../fixtures/wiring-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const wiringClient = makeWiringClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { ...options, wiringClient });
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
  assert.equal(owned.version, JSON.parse(fs.readFileSync(path.join(sourceRoot, 'package.json'), 'utf8')).version);
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
  assert.equal(wiringClient.inspect(targetHome).configured, true);
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
  assert.equal(wiringClient.inspect(targetHome).configured, true);
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), true);
  assert.equal(
    fs.readFileSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json'), 'utf8'),
    manifestBeforeRollback,
  );

  const restored = runSetup([
    'rollback', '--home', targetHome, '--backup', applied.rollback_bundle, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(restored.status, 'PASS');
  assert.equal(wiringClient.inspect(targetHome).configured, false);
  assert.equal(fs.existsSync(path.join(targetHome, '.local', 'bin', 'he')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', 'runtime', 'server.mjs')), false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', '.hard-eng-install', 'manifest.json')), false);
  assert.equal(fs.existsSync(path.join(bundleRoot, 'receipt.json')), true);

  const reinstall = runSetup(['install', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 2 });
  const reapplied = runSetup([
    'install', '--home', targetHome, '--confirm', reinstall.plan_digest,
  ], { sourceRoot, now: NOW + 2 });
  assert.equal(reapplied.status, 'PASS');
  assert.equal(wiringClient.inspect(targetHome).configured, true);
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
  assert.equal(wiringClient.inspect(targetHome).configured, false);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents', 'runtime', 'server.mjs')), false);
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

test('setup refuses an unexpected hard_eng MCP owner before producing an approval plan', () => {
  const targetHome = home('hard-eng-setup-wiring-conflict-');
  const conflict = {
    inspect: () => ({
      status: 'CONFLICT', configured: true, owned: false,
      evidence_digest: 'a'.repeat(64),
    }),
    reconcile: () => {
      throw new Error('must not reconcile a conflict');
    },
  };
  assert.throws(() => baseRunSetup(['install', '--home', targetHome, '--dry-run'], {
    sourceRoot, now: NOW, wiringClient: conflict,
  }), /unexpected hard_eng owner/i);
  assert.equal(fs.existsSync(path.join(targetHome, '.agents')), false);
});

const realCodexAvailable = spawnSync('codex', ['--version'], { encoding: 'utf8' }).status === 0;

test('real Codex CLI discovers and removes the standalone hard_eng MCP owner', {
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
  const listed = spawnSync('codex', ['mcp', 'get', 'hard_eng', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(listed.status, 0, listed.stderr);
  const entry = JSON.parse(listed.stdout);
  assert.equal(entry.enabled, true);
  assert.equal(entry.transport.type, 'stdio');
  assert.equal(entry.transport.command, 'node');
  assert.deepEqual(entry.transport.args, [path.join(targetHome, '.agents', 'runtime', 'server.mjs')]);

  const remove = baseRunSetup(['uninstall', '--home', targetHome, '--dry-run'], { sourceRoot, now: NOW + 1 });
  baseRunSetup(['uninstall', '--home', targetHome, '--confirm', remove.plan_digest], { sourceRoot, now: NOW + 1 });
  const after = spawnSync('codex', ['mcp', 'list', '--json'], {
    env, encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(after.status, 0, after.stderr);
  assert.equal(JSON.parse(after.stdout).some((candidate) => candidate.name === 'hard_eng'), false);
});

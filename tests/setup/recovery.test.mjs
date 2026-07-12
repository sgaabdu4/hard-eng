import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { inspectSetupRecovery } from '../../runtime/lib/setup-recovery.mjs';
import { makeWiringClient } from '../fixtures/wiring-client-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const wiringClient = makeWiringClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { sourceRoot, now: NOW, wiringClient, ...options });
}

test('SIGKILL leaves a durable journal and exact-confirm recovery restores the prior generation', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-setup-crash-'));
  const dry = runSetup(['install', '--home', home, '--dry-run']);
  const worker = path.resolve('tests/fixtures/setup-crash-worker.mjs');
  const crashed = spawnSync(process.execPath, [worker, sourceRoot, home, dry.plan_digest], {
    encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(crashed.signal, 'SIGKILL');
  assert.equal(inspectSetupRecovery(home).status, 'RECOVERY_REQUIRED');
  assert.equal(fs.existsSync(path.join(home, '.agents', '.gitignore')), true);

  const recovery = runSetup(['recover', '--home', home, '--dry-run']);
  assert.equal(recovery.status, 'DRY_RUN');
  assert.ok(recovery.operations.some((entry) => entry.action === 'remove-created'));
  assert.throws(() => runSetup([
    'recover', '--home', home, '--confirm', '0'.repeat(64),
  ]), /confirmation digest/i);
  assert.equal(fs.existsSync(path.join(home, '.agents', '.gitignore')), true);

  const restored = runSetup([
    'recover', '--home', home, '--confirm', recovery.plan_digest,
  ]);
  assert.equal(restored.status, 'PASS');
  assert.equal(inspectSetupRecovery(home).status, 'PASS');
  assert.equal(fs.existsSync(path.join(home, '.agents', '.gitignore')), false);
  assert.equal(fs.existsSync(path.join(home, '.agents', '.worktreeinclude')), false);
  assert.equal(fs.existsSync(path.join(home, '.agents', '.hard-eng-install', 'manifest.json')), false);
  assert.equal(wiringClient.inspect(home).configured, false);

  const reinstall = runSetup(['install', '--home', home, '--dry-run'], { now: NOW + 1 });
  assert.equal(runSetup([
    'install', '--home', home, '--confirm', reinstall.plan_digest,
  ], { now: NOW + 1 }).status, 'PASS');
});

test('SIGKILL during rollback recovers the cutover generation before rollback can be retried', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-rollback-crash-'));
  const install = runSetup(['install', '--home', home, '--dry-run']);
  const installed = runSetup(['install', '--home', home, '--confirm', install.plan_digest]);
  const manifestFile = path.join(home, '.agents', '.hard-eng-install', 'manifest.json');
  const manifestBefore = fs.readFileSync(manifestFile, 'utf8');
  const rollback = runSetup(['rollback', '--home', home, '--backup', installed.rollback_bundle, '--dry-run']);
  const worker = path.resolve('tests/fixtures/setup-rollback-crash-worker.mjs');
  const crashed = spawnSync(process.execPath, [
    worker, sourceRoot, home, installed.rollback_bundle, rollback.plan_digest,
  ], { encoding: 'utf8', timeout: 20_000 });
  assert.equal(crashed.signal, 'SIGKILL');
  assert.equal(inspectSetupRecovery(home).status, 'RECOVERY_REQUIRED');

  const recovery = runSetup(['recover', '--home', home, '--dry-run']);
  const restored = runSetup(['recover', '--home', home, '--confirm', recovery.plan_digest]);
  assert.equal(restored.status, 'PASS');
  assert.equal(fs.readFileSync(manifestFile, 'utf8'), manifestBefore);
  assert.equal(fs.existsSync(path.join(home, '.agents', 'AGENTS.md')), true);
  assert.equal(wiringClient.inspect(home).configured, true);

  const retry = runSetup(['rollback', '--home', home, '--backup', installed.rollback_bundle, '--dry-run']);
  assert.equal(runSetup([
    'rollback', '--home', home, '--backup', installed.rollback_bundle, '--confirm', retry.plan_digest,
  ]).status, 'PASS');
});

test('recovery rejects hostile previous-manifest paths before reading outside its transaction', () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-hostile-journal-'));
  const dry = runSetup(['install', '--home', home, '--dry-run']);
  const worker = path.resolve('tests/fixtures/setup-crash-worker.mjs');
  const crashed = spawnSync(process.execPath, [worker, sourceRoot, home, dry.plan_digest], {
    encoding: 'utf8', timeout: 20_000,
  });
  assert.equal(crashed.signal, 'SIGKILL');
  const stateRoot = path.join(home, '.agents', '.hard-eng-install');
  const transaction = fs.readdirSync(stateRoot).find((entry) => entry.startsWith('transaction-'));
  assert.ok(transaction);
  const journalFile = path.join(stateRoot, transaction, 'journal.json');
  const journal = JSON.parse(fs.readFileSync(journalFile, 'utf8'));
  journal.previous_manifest = {
    present: true,
    hash: 'a'.repeat(64),
    backup: '../outside',
  };
  fs.writeFileSync(journalFile, `${JSON.stringify(journal)}\n`, { mode: 0o600 });

  assert.throws(
    () => runSetup(['recover', '--home', home, '--dry-run']),
    /previous-manifest backup is invalid/i,
  );
  assert.equal(inspectSetupRecovery(home).status, 'RECOVERY_REQUIRED');
});

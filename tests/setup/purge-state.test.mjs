import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createInitialRun } from '../../runtime/lib/state-machine.mjs';
import { createRun, ensureStore } from '../../runtime/lib/store.mjs';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makeWiringClient } from '../fixtures/wiring-client-fixture.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const wiringClient = makeWiringClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { ...options, wiringClient });
}

function installedHome() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-purge-home-'));
  const dry = runSetup(['install', '--home', home, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', home, '--confirm', dry.plan_digest], { sourceRoot, now: NOW });
  return home;
}

function stateRoot() {
  const repo = makeRepo('hard-eng-purge-repo-');
  const store = ensureStore(repo);
  createRun(store, createInitialRun({
    repoId: store.repoId, checkoutId: store.checkoutId, taskHash: 'a'.repeat(64),
    objective: 'Preserve or explicitly purge state',
    intent: {
      kind: 'direct', digest: 'b'.repeat(64), acceptance: ['fixture'], scope: ['state'],
      non_goals: [], justification: 'Bounded purge fixture',
    },
    now: NOW,
    runId: 'he-purge-fixture',
  }));
  return store.root;
}

test('uninstall preserves checkpoints and purge-state is a separate exact-confirm operation', () => {
  let home = installedHome();
  let root = stateRoot();
  const ordinary = runSetup(['uninstall', '--home', home, '--dry-run'], { sourceRoot, now: NOW + 1 });
  runSetup(['uninstall', '--home', home, '--confirm', ordinary.plan_digest], { sourceRoot, now: NOW + 1 });
  assert.equal(fs.existsSync(root), true);

  root = stateRoot();
  assert.throws(() => runSetup(['uninstall', '--home', home, '--purge-state', '--dry-run'], {
    sourceRoot, now: NOW + 2,
  }), /separate.*purge-state/i);
  const dry = runSetup([
    'purge-state', '--home', home, '--state-root', root, '--dry-run',
  ], { sourceRoot, now: NOW + 2 });
  assert.equal(dry.status, 'DRY_RUN');
  assert.equal(fs.existsSync(root), true);
  assert.equal(dry.state_purge.length, 1);
  const purged = runSetup([
    'purge-state', '--home', home, '--state-root', root,
    '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 2 });
  assert.equal(purged.status, 'PASS');
  assert.equal(fs.existsSync(root), false);
});

test('state changes after dry-run cancel purge instead of deleting newer checkpoints', () => {
  const home = installedHome();
  const root = stateRoot();
  const dry = runSetup([
    'purge-state', '--home', home, '--state-root', root, '--dry-run',
  ], { sourceRoot, now: NOW + 3 });
  fs.writeFileSync(path.join(root, 'runs', 'newer.json'), '{}\n');
  assert.throws(() => runSetup([
    'purge-state', '--home', home, '--state-root', root,
    '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 3 }), /confirmation digest|state.*changed/i);
  assert.equal(fs.existsSync(root), true);
});

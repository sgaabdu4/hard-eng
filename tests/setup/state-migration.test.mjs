import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';
import { createRun, ensureStore } from '../../plugins/hard-eng/runtime/lib/store.mjs';
import { runSetup as baseRunSetup } from '../../scripts/setup.mjs';
import { makePluginClient } from '../fixtures/plugin-client-fixture.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';

const sourceRoot = path.resolve('.');
const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const pluginClient = makePluginClient();

function runSetup(argv, options = {}) {
  return baseRunSetup(argv, { ...options, pluginClient });
}

function fixture() {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-state-migrate-home-'));
  const install = runSetup(['install', '--home', home, '--dry-run'], { sourceRoot, now: NOW });
  runSetup(['install', '--home', home, '--confirm', install.plan_digest], { sourceRoot, now: NOW });
  const repo = makeRepo('hard-eng-state-migrate-repo-');
  const store = ensureStore(repo);
  createRun(store, createInitialRun({
    repoId: store.repoId, checkoutId: store.checkoutId, taskHash: 'a'.repeat(64),
    objective: 'Validate explicit state migration', runId: 'he-state-migrate',
    intent: {
      kind: 'direct', digest: 'b'.repeat(64), acceptance: ['state remains exact'], scope: ['state'],
      non_goals: [], justification: 'Bounded schema fixture',
    },
    now: NOW,
  }));
  return { home, store };
}

test('update validates explicitly named current state roots without scanning or rewriting them', () => {
  const { home, store } = fixture();
  const runFile = path.join(store.runsDir, 'he-state-migrate.json');
  const before = fs.readFileSync(runFile, 'utf8');
  const dry = runSetup([
    'update', '--home', home, '--state-root', store.root, '--dry-run',
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(dry.state_migration[0].status, 'current');
  const result = runSetup([
    'update', '--home', home, '--state-root', store.root, '--confirm', dry.plan_digest,
  ], { sourceRoot, now: NOW + 1 });
  assert.equal(result.status, 'PASS');
  assert.equal(result.migrated_state_roots, 0);
  assert.equal(fs.readFileSync(runFile, 'utf8'), before);
});

test('unknown or future run schema is refused before setup mutation', () => {
  const { home, store } = fixture();
  const runFile = path.join(store.runsDir, 'he-state-migrate.json');
  const value = JSON.parse(fs.readFileSync(runFile, 'utf8'));
  fs.writeFileSync(runFile, `${JSON.stringify({ ...value, schema: 'hard-eng/run/v2' })}\n`);
  const agentsBefore = fs.readFileSync(path.join(home, '.agents', 'AGENTS.md'), 'utf8');
  assert.throws(() => runSetup([
    'update', '--home', home, '--state-root', store.root, '--dry-run',
  ], { sourceRoot, now: NOW + 2 }), /future|unknown.*schema/i);
  assert.equal(fs.readFileSync(path.join(home, '.agents', 'AGENTS.md'), 'utf8'), agentsBefore);
});

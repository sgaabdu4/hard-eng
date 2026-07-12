import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { createInitialRun } from '../../runtime/lib/state-machine.mjs';
import {
  attachStateMigration,
  attachStatePurge,
} from '../../runtime/lib/setup-state.mjs';
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

test('live cutover state operations bind the canonical cutover receipt without a legacy schema field', () => {
  const plan = {
    schema: 'hard-eng/setup-plan/v1',
    mode: 'migrate',
    purge_state: false,
    codex_mcp_action: 'cutover',
    codex_mcp: {
      before_status: 'MIGRATION_REQUIRED',
      before_evidence_digest: 'f'.repeat(64),
      desired_configured: true,
    },
    live_cutover: true,
    codex_cutover: { schema: 'hard-eng/codex-cutover/v1', evidence_digest: 'c'.repeat(64) },
    target_home_digest: 'a'.repeat(64),
    source_version: '1.0.0',
    source_digest: 'b'.repeat(64),
    existing_manifest_hash: '9'.repeat(64),
    operations: [],
  };
  const descriptors = [{ public: { root_digest: 'd'.repeat(64), content_digest: 'e'.repeat(64) } }];
  for (const attached of [
    attachStateMigration(plan, descriptors),
    attachStatePurge(plan, descriptors),
  ]) {
    assert.deepEqual(attached.codex_cutover, plan.codex_cutover);
    assert.deepEqual(attached.codex_mcp, plan.codex_mcp);
    assert.equal(attached.codex_mcp_action, 'cutover');
    assert.equal(attached.source_version, '1.0.0');
    assert.equal(attached.existing_manifest_hash, '9'.repeat(64));
    assert.equal(Object.hasOwn(attached, 'legacy'), false);
    assert.match(attached.plan_digest, /^[a-f0-9]{64}$/);
  }
});

import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCheckRegistry, runCheckRegistry } from '../../runtime/lib/check-registry.mjs';
import { signCheckReceipt, verifyCheckReceipt } from '../../runtime/lib/check-receipt.mjs';
import { runShipPreflight } from '../../runtime/lib/ship-preflight.mjs';
import { createInitialRun } from '../../runtime/lib/state-machine.mjs';
import { ensureStore, readKey } from '../../runtime/lib/store.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

test('Ship check receipt is short-lived, revision-bound, signed, and candidate-exact', () => {
  const repo = makeRepo('hard-eng-check-receipt-');
  fs.writeFileSync(path.join(repo, 'pass.mjs'), "process.stdout.write('pass\\n');\n");
  fs.writeFileSync(path.join(repo, 'package.json'), `${JSON.stringify({ private: true, scripts: { test: 'node pass.mjs' } })}\n`);
  const store = ensureStore(repo);
  const run = createInitialRun({
    repoId: store.repoId,
    checkoutId: store.checkoutId,
    taskHash: 'a'.repeat(64),
    objective: 'Sign exact Ship proof',
    intent: {
      kind: 'direct', digest: 'b'.repeat(64), acceptance: ['checks pass'], scope: ['fixture'],
      non_goals: [], justification: 'Bounded receipt fixture',
    },
    now: NOW,
    runId: 'he-check-receipt',
  });
  run.phase = 'Ship';
  run.cursor = { step: 'preflight' };
  run.support_tools = [
    { tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: 'c'.repeat(64), runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
    { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
  ];
  const preflight = runShipPreflight(repo, run, { allowedUntracked: ['package.json', 'pass.mjs'] });
  const report = runCheckRegistry(repo, buildCheckRegistry(repo), { allowedUntracked: ['package.json', 'pass.mjs'] });
  const receipt = signCheckReceipt(readKey(store), { run, report, preflight }, { now: NOW });
  const verified = verifyCheckReceipt(receipt, {
    key: readKey(store), run, repoId: store.repoId, checkoutId: store.checkoutId, now: NOW + 1,
  });
  assert.equal(verified.status, 'PASS');
  assert.equal(verified.candidate.fingerprint, report.candidate.fingerprint);
  assert.doesNotMatch(JSON.stringify(receipt), new RegExp(repo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  assert.throws(() => verifyCheckReceipt({ ...receipt, registry_digest: 'f'.repeat(64) }, {
    key: readKey(store), run, repoId: store.repoId, checkoutId: store.checkoutId, now: NOW + 1,
  }), /signature/i);
  assert.throws(() => verifyCheckReceipt(receipt, {
    key: readKey(store), run: { ...run, revision: run.revision + 1 },
    repoId: store.repoId, checkoutId: store.checkoutId, now: NOW + 1,
  }), /revision/i);
  assert.throws(() => verifyCheckReceipt(receipt, {
    key: readKey(store), run, repoId: store.repoId, checkoutId: store.checkoutId, now: NOW + 10 * 60_000,
  }), /expired/i);
  assert.throws(() => signCheckReceipt(readKey(store), {
    run, report, preflight,
  }, { now: NOW, ttlMs: 10 * 60_000 + 1 }), /TTL|ten minutes/i);
});

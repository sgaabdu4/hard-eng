import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyCheckReceipt } from '../../runtime/lib/check-receipt.mjs';
import { runCommand } from '../../runtime/he.mjs';
import { createInitialRun } from '../../runtime/lib/state-machine.mjs';
import { createRun, ensureStore, readKey } from '../../runtime/lib/store.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { nextFor } from '../../runtime/lib/lifecycle.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

function fixture() {
  const repo = makeRepo('hard-eng-he-check-');
  fs.writeFileSync(path.join(repo, 'pass.mjs'), "process.stdout.write('pass\\n');\n");
  fs.writeFileSync(path.join(repo, 'package.json'), `${JSON.stringify({ private: true, scripts: { test: 'node pass.mjs' } })}\n`);
  return { repo, allowed: ['package.json', 'pass.mjs'] };
}

test('he check --all is the one unsigned local and CI registry gate', () => {
  const { repo, allowed } = fixture();
  const argv = ['check', '--repo', repo, '--all', ...allowed.flatMap((file) => ['--allow-untracked', file])];
  const report = runCommand(argv);
  assert.equal(report.status, 'PASS');
  assert.deepEqual(report.results.map((result) => result.id), ['git.diff-check', 'package.test']);
  assert.equal(report.receipt, undefined);
  assert.throws(() => runCommand(['check', '--repo', repo, '--id', 'missing']), /unknown check/i);
});

test('he ship reuses the same registry and emits a signed receipt without mutating run state', () => {
  const { repo, allowed } = fixture();
  const store = ensureStore(repo);
  const run = createInitialRun({
    repoId: store.repoId, checkoutId: store.checkoutId, taskHash: 'a'.repeat(64),
    objective: 'Prepare exact Ship candidate', runId: 'he-cli-ship',
    intent: {
      kind: 'direct', digest: 'b'.repeat(64), acceptance: ['checks pass'], scope: ['fixture'],
      non_goals: [], justification: 'Bounded CLI fixture',
    },
    now: NOW,
  });
  run.phase = 'Ship';
  run.cursor = { step: 'preflight' };
  run.next = nextFor(run.phase, run.cursor);
  run.support_tools = [
    { tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: 'c'.repeat(64), runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
    { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
  ];
  createRun(store, run);
  const argv = ['ship', '--repo', repo, '--run', run.run_id, ...allowed.flatMap((file) => ['--allow-untracked', file])];
  const result = runCommand(argv, { now: NOW + 1 });
  assert.equal(result.status, 'PASS');
  assert.equal(result.report.registry_digest, runCommand([
    'check', '--repo', repo, '--all', ...allowed.flatMap((file) => ['--allow-untracked', file]),
  ]).registry_digest);
  assert.equal(verifyCheckReceipt(result.receipt, {
    key: readKey(store), run, repoId: store.repoId, checkoutId: store.checkoutId, now: NOW + 2,
  }).candidate.fingerprint, result.report.candidate.fingerprint);
  assert.equal(runCommand(['status', '--repo', repo, '--run', run.run_id]).revision, 1);
});

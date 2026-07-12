import test from 'node:test';
import assert from 'node:assert/strict';
import { applyEvent, createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';

const base = {
  repoId: '1'.repeat(64),
  checkoutId: '2'.repeat(64),
  taskHash: '3'.repeat(64),
  objective: 'Build the definitive state machine',
  now: '2026-07-12T00:00:00.000Z',
};

function proof(id, kind, result, candidate) {
  return {
    id,
    kind,
    name: `${kind} state fixture`,
    result,
    source: { kind: kind === 'review' ? 'review' : 'command', reference: `fixture:${id}` },
    evidence_digest: 'e'.repeat(64),
    candidate_fingerprint: candidate,
  };
}

function sections() {
  return Object.fromEntries(Array.from({ length: 11 }, (_, index) => [String(index + 1), {
    heading: `Section ${index + 1}`, line: index + 3, digest: String((index + 1) % 10).repeat(64),
  }]));
}

function recordSupport(run) {
  let next = applyEvent(run, {
    type: 'support.recorded',
    receipt: { tool: 'codebase-memory', operation: 'get_architecture', status: 'pass', evidence_digest: 'a'.repeat(64), runtime_observed: true },
  });
  next = applyEvent(next, {
    type: 'support.recorded',
    receipt: { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true },
  });
  return next;
}

test('Plan enters Build:red only through typed acceptance', () => {
  let run = createInitialRun({ ...base, runId: 'run-plan', intent: { kind: 'plan', digest: '4'.repeat(64) } });
  assert.equal(run.phase, 'Plan');
  assert.equal(run.cursor.step, 'discover');

  run = applyEvent(run, { type: 'plan.prototype-ready', at: '2026-07-12T00:01:00.000Z' });
  assert.throws(() => applyEvent(run, { type: 'plan.ready-for-approval' }), /support|Codebase Memory/i);
  run = recordSupport(run);
  run = applyEvent(run, { type: 'plan.ready-for-approval', at: '2026-07-12T00:02:00.000Z' });
  run = applyEvent(run, {
    type: 'plan.accepted',
    at: '2026-07-12T00:03:00.000Z',
    plan: {
      path: 'plan.md', digest: '5'.repeat(64), approver: 'user',
      slice_ids: ['S1'], acceptance_ids: ['P1'], sections: sections(),
      ui: { applicable: false, reason: 'not applicable — state fixture' },
    },
  });

  assert.equal(run.phase, 'Build');
  assert.deepEqual(run.cursor, { step: 'red', slice: 1 });
  assert.equal(run.plan.digest, '5'.repeat(64));
});

test('Plan readiness requires an actual Codebase Memory graph or impact operation', () => {
  let run = createInitialRun({ ...base, runId: 'run-support-health-only', intent: { kind: 'plan', digest: '4'.repeat(64) } });
  run = applyEvent(run, { type: 'plan.prototype-ready' });
  run = applyEvent(run, {
    type: 'support.recorded',
    receipt: {
      tool: 'codebase-memory', operation: 'list_projects', status: 'pass',
      evidence_digest: 'a'.repeat(64), runtime_observed: true,
    },
  });
  run = applyEvent(run, {
    type: 'support.recorded',
    receipt: {
      tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable',
      reason_code: 'no-large-output', runtime_observed: true,
    },
  });
  assert.throws(() => applyEvent(run, { type: 'plan.ready-for-approval' }), /graph|impact|structural/i);
});

test('Plan slice cardinality is binding and cannot be skipped', () => {
  let run = createInitialRun({ ...base, runId: 'run-planned-slices', intent: { kind: 'plan', digest: '4'.repeat(64) } });
  run = recordSupport(run);
  run = applyEvent(run, { type: 'plan.ready-for-approval' });
  run = applyEvent(run, {
    type: 'plan.accepted',
    plan: {
      path: 'plan.md', digest: '5'.repeat(64), approver: 'user',
      slice_ids: ['S1', 'S2'], acceptance_ids: ['P1', 'P2'], sections: sections(),
      ui: { applicable: false, reason: 'not applicable — state fixture' },
    },
  });
  run = applyEvent(run, { type: 'build.red-proven', proof: proof('planned-red-1', 'red', 'fail-expected', 'a'.repeat(64)) });
  run = applyEvent(run, { type: 'build.implemented', candidate_fingerprint: 'b'.repeat(64) });
  run = applyEvent(run, { type: 'build.verify-passed', proof: proof('planned-verify-1', 'verify', 'pass', 'b'.repeat(64)) });
  run = applyEvent(run, { type: 'build.review-passed', proof: proof('planned-review-1', 'review', 'pass', 'b'.repeat(64)) });
  assert.throws(() => applyEvent(run, {
    type: 'build.all-slices-proven', candidate_fingerprint: 'b'.repeat(64),
  }), /remaining|final planned slice|S2/i);
  run = applyEvent(run, { type: 'build.next-slice' });
  assert.deepEqual(run.cursor, { step: 'red', slice: 2, candidate_fingerprint: 'b'.repeat(64) });
});

test('Direct intent starts at Build:red and cannot hide Plan-triggering risk', () => {
  const run = createInitialRun({
    ...base,
    runId: 'run-direct',
    intent: {
      kind: 'direct',
      digest: '6'.repeat(64),
      acceptance: ['focused regression passes'],
      scope: ['runtime/lib/store.mjs'],
      non_goals: ['UI'],
      justification: 'Small mechanical fix with resolved behavior',
    },
  });
  assert.equal(run.phase, 'Build');
  assert.deepEqual(run.cursor, { step: 'red', slice: 1 });

  assert.throws(() => createInitialRun({
    ...base,
    runId: 'run-risky-direct',
    intent: { kind: 'direct', digest: '7'.repeat(64), triggers: ['schema'] },
  }), /Plan/i);
});

test('Build enforces red, implement, verify, review, and Ship order', () => {
  let run = createInitialRun({
    ...base,
    runId: 'run-build',
    intent: { kind: 'direct', digest: '8'.repeat(64), acceptance: ['test'], scope: ['lib'], non_goals: [], justification: 'bounded' },
  });

  assert.throws(() => applyEvent(run, { type: 'build.implemented' }), /red/i);
  assert.throws(() => applyEvent(run, {
    type: 'build.red-proven', proof: proof('unsupported-red', 'red', 'fail-expected', 'a'.repeat(64)),
  }), /support|Codebase Memory/i);
  run = recordSupport(run);
  run = applyEvent(run, { type: 'build.red-proven', proof: proof('proof-red', 'red', 'fail-expected', 'a'.repeat(64)) });
  run = applyEvent(run, { type: 'build.implemented', candidate_fingerprint: 'b'.repeat(64) });
  run = applyEvent(run, {
    type: 'build.verify-failed',
    hypothesis_digest: 'c'.repeat(64),
    proof: proof('proof-failed', 'verify', 'fail', 'b'.repeat(64)),
  });
  assert.equal(run.cursor.step, 'implement');
  run = applyEvent(run, { type: 'build.implemented', candidate_fingerprint: 'd'.repeat(64) });
  run = applyEvent(run, { type: 'build.verify-passed', proof: proof('proof-pass', 'verify', 'pass', 'd'.repeat(64)) });
  run = applyEvent(run, { type: 'build.review-passed', proof: proof('proof-review', 'review', 'pass', 'd'.repeat(64)) });
  run = applyEvent(run, { type: 'build.all-slices-proven', candidate_fingerprint: 'd'.repeat(64) });
  assert.equal(run.phase, 'Ship');
  assert.equal(run.cursor.step, 'preflight');
});

test('Learn requires typed provenance and returns to its recorded boundary', () => {
  let run = createInitialRun({
    ...base,
    runId: 'run-learn',
    intent: { kind: 'direct', digest: '9'.repeat(64), acceptance: ['test'], scope: ['lib'], non_goals: [], justification: 'bounded' },
  });

  assert.throws(() => applyEvent(run, { type: 'finding.admitted', finding: { fingerprint: 'miss' } }), /provenance/i);
  run = applyEvent(run, {
    type: 'finding.admitted',
    finding: {
      id: 'finding-1',
      fingerprint: 'a'.repeat(64),
      severity: 'high',
      action: 'manual',
      source_stage: 'Build',
      source: { kind: 'test', reference: 'tests/state/store.test.mjs' },
      occurrences: 2,
      occurrence_evidence: ['b'.repeat(64), 'c'.repeat(64)],
      affected_owner: 'store',
      immediate_repair: 'Reject stale revision',
      admission_reason: 'repeated',
      proposed_guard: 'CAS regression test',
    },
  });
  assert.equal(run.cursor.step, 'learn');
  run = applyEvent(run, {
    type: 'learn.guard-proven',
    finding_id: 'finding-1',
    tree_changed: false,
    guard: {
      owner_kind: 'test',
      owner: 'tests/state/state-machine.test.mjs',
      bad_fixture_digest: 'd'.repeat(64),
      fail_before: { evidence_digest: 'e'.repeat(64), result: 'fail-expected' },
      pass_after: { evidence_digest: 'f'.repeat(64), result: 'pass', candidate_fingerprint: '1'.repeat(64) },
      consolidated_rules: [],
    },
  });
  assert.equal(run.phase, 'Build');
  assert.equal(run.cursor.step, 'red');
});

test('support-tool receipts are bounded metadata and never raw output', () => {
  let run = createInitialRun({ ...base, runId: 'run-support', intent: { kind: 'plan', digest: 'a'.repeat(64) } });
  assert.throws(() => applyEvent(run, {
    type: 'support.recorded',
    receipt: { tool: 'codebase-memory', operation: 'not-applicable', status: 'not-applicable', runtime_observed: true },
  }), /mandatory|not-applicable/i);
  assert.throws(() => applyEvent(run, {
    type: 'support.recorded',
    receipt: { tool: 'codebase-memory', operation: 'get_architecture', status: 'pass', runtime_observed: true },
  }), /evidence digest/i);
  run = applyEvent(run, {
    type: 'support.recorded',
    receipt: {
      tool: 'codebase-memory', operation: 'get_architecture', status: 'pass', evidence_digest: 'b'.repeat(64), runtime_observed: true,
    },
  });
  assert.deepEqual(run.support_tools[0].tool, 'codebase-memory');
  assert.equal(run.cursor.step, 'discover');
  run = applyEvent(run, {
    type: 'support.recorded',
    receipt: { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true },
  });
  assert.equal(run.support_tools[1].reason_code, 'no-large-output');
  assert.throws(() => applyEvent(run, {
    type: 'support.recorded',
    receipt: { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'convenient-skip', runtime_observed: true },
  }), /reason code/i);
  assert.throws(() => applyEvent(run, {
    type: 'support.recorded',
    receipt: {
      tool: 'context-mode', operation: 'ctx_search', status: 'pass', evidence_digest: 'c'.repeat(64), runtime_observed: true, raw_output: 'forbidden',
    },
  }), /unknown field/i);
});

test('external actions are journaled before execution and clear only on matching not-applied proof', () => {
  let run = createInitialRun({
    ...base,
    runId: 'run-external-action',
    intent: { kind: 'direct', digest: 'a'.repeat(64), acceptance: ['test'], scope: ['owner'], non_goals: [], justification: 'bounded' },
  });
  run = applyEvent(run, {
    type: 'external-action.prepared',
    action: {
      intent: 'write external fixture', precondition_fingerprint: 'b'.repeat(64),
      idempotency_key: 'c'.repeat(64), reconciliation_command: 'he doctor',
    },
  });
  assert.equal(run.interruption.observed_result, 'not-observed');
  assert.throws(() => applyEvent(run, {
    type: 'external-action.prepared', action: { intent: 'second action' },
  }), /pending reconciliation/i);
  assert.throws(() => applyEvent(createInitialRun({
    ...base,
    runId: 'run-unsafe-reconciliation',
    intent: { kind: 'direct', digest: 'a'.repeat(64), acceptance: ['test'], scope: ['owner'], non_goals: [], justification: 'bounded' },
  }), {
    type: 'external-action.prepared',
    action: {
      intent: 'unsafe', precondition_fingerprint: 'b'.repeat(64), idempotency_key: 'c'.repeat(64),
      reconciliation_command: 'git status; rm -rf .',
    },
  }), /simple read-only invocation/i);
  assert.throws(() => applyEvent(run, {
    type: 'external-action.not-applied', idempotency_key: 'd'.repeat(64),
    observed_result: 'not applied', evidence_digest: 'e'.repeat(64),
  }), /identity/i);
  run = applyEvent(run, {
    type: 'external-action.not-applied', idempotency_key: 'c'.repeat(64),
    observed_result: 'external state proves no write occurred', evidence_digest: 'e'.repeat(64),
  });
  assert.equal(run.interruption, null);
  assert.equal(run.cursor.step, 'red');
});

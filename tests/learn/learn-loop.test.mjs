import test from 'node:test';
import assert from 'node:assert/strict';
import { applyEvent, createInitialRun } from '../../runtime/lib/state-machine.mjs';

const digest = (character) => character.repeat(64);

function buildRun() {
  return createInitialRun({
    repoId: digest('1'),
    checkoutId: digest('2'),
    taskHash: digest('3'),
    objective: 'Compound one proven gap',
    intent: {
      kind: 'direct', digest: digest('4'), acceptance: ['guard passes'], scope: ['runtime'],
      non_goals: [], justification: 'Bounded fixture',
    },
    now: '2026-07-12T00:00:00.000Z',
    runId: 'he-learn-loop',
  });
}

function finding(overrides = {}) {
  return {
    id: 'finding-repeat',
    fingerprint: digest('a'),
    severity: 'high',
    action: 'manual',
    source_stage: 'Build',
    source: { kind: 'test', reference: 'fixture:repeat' },
    occurrences: 2,
    occurrence_evidence: [digest('b'), digest('c')],
    affected_owner: 'runtime/schema',
    immediate_repair: 'Reject the malformed event',
    admission_reason: 'repeated',
    proposed_guard: 'Add the narrow schema fixture',
    ...overrides,
  };
}

function guard(overrides = {}) {
  return {
    owner_kind: 'test',
    owner: 'tests/learn/learn-loop.test.mjs',
    bad_fixture_digest: digest('d'),
    fail_before: { evidence_digest: digest('e'), result: 'fail-expected' },
    pass_after: { evidence_digest: digest('f'), result: 'pass', candidate_fingerprint: digest('9') },
    consolidated_rules: [],
    ...overrides,
  };
}

test('Learn requires admitted provenance and fail-before/pass-after guard proof', () => {
  const source = buildRun();
  assert.throws(() => applyEvent(source, {
    type: 'finding.admitted', finding: finding({ occurrence_evidence: [] }), at: '2026-07-12T00:00:01.000Z',
  }), /occurrence evidence/i);

  let run = applyEvent(source, {
    type: 'finding.admitted', finding: finding(), at: '2026-07-12T00:00:01.000Z',
  });
  assert.deepEqual([run.phase, run.cursor.step], ['Build', 'learn']);
  assert.throws(() => applyEvent(run, {
    type: 'learn.guard-proven', finding_id: 'finding-repeat', tree_changed: true,
    guard: guard({ fail_before: null }), at: '2026-07-12T00:00:02.000Z',
  }), /fail-before|guard proof/i);

  run = applyEvent(run, {
    type: 'learn.guard-proven', finding_id: 'finding-repeat', tree_changed: true,
    guard: guard(), at: '2026-07-12T00:00:03.000Z',
  });
  assert.deepEqual([run.phase, run.cursor.step, run.cursor.slice], ['Build', 'verify', 1]);
  assert.equal(run.findings[0].admission, 'closed');
  assert.equal(run.findings[0].guard.result, 'proven');
  assert.equal(run.candidate, null);
  assert.ok(run.proof.every((item) => item.fresh === false));
});

test('a no-tree guard returns to the exact recorded boundary', () => {
  let run = buildRun();
  run.cursor = { step: 'review', slice: 3, candidate_fingerprint: digest('8') };
  run = applyEvent(run, {
    type: 'finding.admitted', finding: finding({ id: 'finding-critical', admission_reason: 'critical', occurrences: 1 }),
    at: '2026-07-12T00:00:01.000Z',
  });
  run = applyEvent(run, {
    type: 'learn.guard-proven', finding_id: 'finding-critical', tree_changed: false,
    guard: guard({ pass_after: { evidence_digest: digest('f'), result: 'pass', candidate_fingerprint: digest('8') } }),
    at: '2026-07-12T00:00:02.000Z',
  });
  assert.deepEqual(run.cursor, { step: 'review', slice: 3, candidate_fingerprint: digest('8') });
});

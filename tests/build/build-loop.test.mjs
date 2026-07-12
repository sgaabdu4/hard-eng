import test from 'node:test';
import assert from 'node:assert/strict';
import { applyEvent, createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';
import { recordSupport } from '../fixtures/support-fixture.mjs';

const digest = (character) => character.repeat(64);
const at = (second) => `2026-07-12T00:00:${String(second).padStart(2, '0')}.000Z`;

function directRun() {
  return recordSupport(createInitialRun({
    repoId: digest('1'),
    checkoutId: digest('2'),
    taskHash: digest('3'),
    objective: 'Prove one bounded vertical slice',
    intent: {
      kind: 'direct',
      digest: digest('4'),
      acceptance: ['observable fixture passes'],
      scope: ['runtime owner'],
      non_goals: ['unrelated cleanup'],
      justification: 'No Plan trigger applies',
    },
    now: at(0),
    runId: 'he-build-loop',
  }));
}

function proof(kind, result, candidate, suffix = kind) {
  return {
    id: `proof-${suffix}`,
    kind,
    name: `${kind} fixture`,
    result,
    source: { kind: kind === 'review' ? 'review' : 'command', reference: `fixture:${suffix}` },
    evidence_digest: digest('e'),
    candidate_fingerprint: candidate,
  };
}

test('Build requires red, implementation, fresh verification, and review for each slice', () => {
  let run = directRun();
  assert.throws(() => applyEvent(run, { type: 'build.implemented', at: at(1), candidate_fingerprint: digest('5') }), /transition|red/i);
  assert.throws(() => applyEvent(run, {
    type: 'build.candidate-drift', at: at(1), candidate_fingerprint: digest('5'), reason: 'Premature drift',
  }), /transition|red/i);

  run = applyEvent(run, { type: 'build.red-proven', at: at(1), proof: proof('red', 'fail-expected', digest('5')) });
  assert.equal(run.cursor.step, 'implement');
  assert.equal(run.proof.at(-1).fresh, true);

  run = applyEvent(run, { type: 'build.implemented', at: at(2), candidate_fingerprint: digest('6') });
  assert.equal(run.cursor.step, 'verify');
  assert.equal(run.proof[0].fresh, false);

  run = applyEvent(run, { type: 'build.verify-passed', at: at(3), proof: proof('verify', 'pass', digest('6')) });
  assert.equal(run.cursor.step, 'review');
  assert.throws(() => applyEvent(run, {
    type: 'build.review-passed', at: at(4), proof: proof('review', 'pass', digest('7')),
  }), /candidate fingerprint/i);

  run = applyEvent(run, { type: 'build.review-passed', at: at(4), proof: proof('review', 'pass', digest('6')) });
  assert.equal(run.cursor.step, 'slice-proven');
  assert.throws(() => applyEvent(run, {
    type: 'build.all-slices-proven', at: at(5), candidate_fingerprint: digest('7'),
  }), /fresh|candidate/i);
  run = applyEvent(run, { type: 'build.all-slices-proven', at: at(5), candidate_fingerprint: digest('6') });
  assert.deepEqual([run.phase, run.cursor.step], ['Ship', 'preflight']);
});

test('failed verification returns to the same slice and stops a third unchanged hypothesis', () => {
  let run = directRun();
  run = applyEvent(run, { type: 'build.red-proven', at: at(1), proof: proof('red', 'fail-expected', digest('5')) });
  run = applyEvent(run, { type: 'build.implemented', at: at(2), candidate_fingerprint: digest('6') });

  for (const attempt of [1, 2]) {
    const candidate = digest(String(5 + attempt));
    run = applyEvent(run, {
      type: 'build.verify-failed',
      at: at(2 + attempt),
      hypothesis_digest: digest('a'),
      proof: proof('verify', 'fail', candidate, `failed-${attempt}`),
    });
    assert.equal(run.cursor.slice, 1);
    assert.equal(run.cursor.repair.attempts, attempt);
    run = applyEvent(run, { type: 'build.implemented', at: at(4 + attempt), candidate_fingerprint: digest(String(6 + attempt)) });
  }

  assert.throws(() => applyEvent(run, {
    type: 'build.verify-failed',
    at: at(7),
    hypothesis_digest: digest('a'),
    proof: proof('verify', 'fail', digest('8'), 'failed-3'),
  }), /two repair attempts|unchanged hypothesis/i);

  run = applyEvent(run, {
    type: 'build.verify-failed',
    at: at(8),
    hypothesis_digest: digest('b'),
    proof: proof('verify', 'fail', digest('8'), 'new-hypothesis'),
  });
  assert.equal(run.cursor.repair.attempts, 1);
});

test('a discovered Plan trigger exits Direct Build before more implementation', () => {
  const run = applyEvent(directRun(), {
    type: 'build.plan-triggered',
    at: at(1),
    intent_digest: digest('9'),
    reason: 'Material product decision discovered',
  });
  assert.deepEqual([run.phase, run.cursor.step, run.intent.kind], ['Plan', 'discover', 'plan']);
  assert.equal(run.candidate, null);
  assert.equal(run.proof.length, 0);
});

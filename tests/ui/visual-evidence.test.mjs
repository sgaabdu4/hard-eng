import test from 'node:test';
import assert from 'node:assert/strict';
import { digestValue } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';
import { validateVisualEvidence } from '../../plugins/hard-eng/runtime/lib/evidence.mjs';
import { applyEvent, createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';

const digest = (character) => character.repeat(64);
const runId = 'he-visual-evidence';

function pack(overrides = {}) {
  return {
    kind: 'final',
    applicability: 'applicable',
    candidate_fingerprint: digest('7'),
    approved_direction_digest: digest('8'),
    scenario: {
      role: 'member',
      data_fixture: 'sanitized-seed-v1',
      route: '/fixture',
      viewport_or_device: '1440x900',
      environment: 'local deterministic fixture',
    },
    baseline: {
      status: 'captured',
      artifacts: [{
        kind: 'screenshot', path: `.hard-eng/evidence/${runId}/before.png`, digest: digest('a'),
      }],
    },
    implementation: {
      artifacts: [
        { kind: 'screenshot', path: `.hard-eng/evidence/${runId}/after.png`, digest: digest('b') },
        { kind: 'video', path: `.hard-eng/evidence/${runId}/flow.mp4`, digest: digest('c') },
      ],
    },
    requires_video: true,
    known_gaps: [],
    ...overrides,
  };
}

function buildAtReview() {
  const run = createInitialRun({
    repoId: digest('1'), checkoutId: digest('2'), taskHash: digest('3'),
    objective: 'Review a coded UI milestone', runId,
    intent: {
      kind: 'direct', digest: digest('4'), acceptance: ['coded flow approved'], scope: ['UI'],
      non_goals: [], justification: 'Fixture is fully decided', review_cadence: 'meaningful-milestones',
    },
    now: '2026-07-12T00:00:00.000Z',
  });
  run.cursor = { step: 'review', slice: 1, candidate_fingerprint: digest('7') };
  return run;
}

test('visual evidence proves comparable baseline, final screenshots, and required video', () => {
  const result = validateVisualEvidence(pack(), { runId, final: true });
  assert.equal(result.video_present, true);
  assert.equal(result.candidate_fingerprint, digest('7'));
  assert.equal(result.evidence_digest, digestValue(pack()));
  assert.throws(() => validateVisualEvidence(pack({
    implementation: { artifacts: [{
      kind: 'screenshot', path: `.hard-eng/evidence/${runId}/after.png`, digest: digest('b'),
    }] },
  }), { runId, final: true }), /video/i);
  assert.throws(() => validateVisualEvidence(pack({
    baseline: { status: 'captured', artifacts: [{ kind: 'screenshot', path: '../private.png', digest: digest('a') }] },
  }), { runId, final: true }), /run-owned|path/i);
});

test('greenfield and unavailable-video cases require explicit reasons', () => {
  const greenfield = pack({ baseline: { status: 'not-applicable', reason: 'Greenfield interface has no prior coded screen' } });
  assert.equal(validateVisualEvidence(greenfield, { runId, final: true }).baseline_status, 'not-applicable');
  assert.throws(() => validateVisualEvidence(pack({ baseline: { status: 'not-applicable', reason: '' } }), {
    runId, final: true,
  }), /baseline.*reason/i);
  assert.throws(() => validateVisualEvidence(pack({
    requires_video: false,
    video_unavailable_reason: '',
    implementation: { artifacts: [{
      kind: 'screenshot', path: `.hard-eng/evidence/${runId}/after.png`, digest: digest('b'),
    }] },
  }), {
    runId, final: true, videoExpected: true,
  }), /unavailable.*reason|video/i);
});

test('Build blocks at a visual milestone and routes feedback to the right boundary', () => {
  const evidence = pack({ kind: 'milestone', requires_video: false });
  let run = applyEvent(buildAtReview(), {
    type: 'build.visual-milestone',
    evidence_id: 'visual-milestone-1',
    evidence,
    at: '2026-07-12T00:00:01.000Z',
  });
  assert.equal(run.cursor.step, 'await-user-review');
  const evidenceDigest = digestValue(evidence);
  assert.throws(() => applyEvent(run, {
    type: 'build.user-reviewed', approver: 'user', decision: 'approved', evidence_digest: digest('f'),
  }), /evidence digest/i);
  run = applyEvent(run, {
    type: 'build.user-reviewed', approver: 'user', decision: 'implementation-defect', evidence_digest: evidenceDigest,
  });
  assert.equal(run.cursor.step, 'implement');

  run.cursor = { step: 'review', slice: 1, candidate_fingerprint: digest('7') };
  run = applyEvent(run, { type: 'build.visual-milestone', evidence_id: 'visual-milestone-2', evidence });
  run = applyEvent(run, {
    type: 'build.user-reviewed',
    approver: 'user',
    decision: 'plan-change',
    evidence_digest: evidenceDigest,
    intent_digest: digest('9'),
  });
  assert.deepEqual([run.phase, run.cursor.step, run.intent.kind], ['Plan', 'discover', 'plan']);
  assert.equal(run.proof.length, 0);
});

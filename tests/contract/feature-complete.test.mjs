import test from 'node:test';
import assert from 'node:assert/strict';
import { digestValue } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';
import { applyEvent, createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';
import { recordSupport } from '../fixtures/support-fixture.mjs';

const digest = (character) => character.repeat(64);
const commit = (character) => character.repeat(40);
const runId = 'he-feature-complete';

function proof(id, kind, result, candidate) {
  return {
    id, kind, name: `${kind} journey proof`, result,
    source: { kind: kind === 'review' ? 'review' : 'command', reference: `journey:${id}` },
    evidence_digest: digest('e'), candidate_fingerprint: candidate,
  };
}

function visual(kind, candidate, requiresVideo) {
  const artifacts = [{
    kind: 'screenshot', path: `.hard-eng/evidence/${runId}/${kind}.png`, digest: digest('8'),
  }];
  if (requiresVideo) artifacts.push({
    kind: 'video', path: `.hard-eng/evidence/${runId}/${kind}.mp4`, digest: digest('9'),
  });
  return {
    kind, applicability: 'applicable', candidate_fingerprint: candidate,
    approved_direction_digest: digest('7'),
    scenario: {
      role: 'member', data_fixture: 'seed-v1', route: '/journey',
      viewport_or_device: '1440x900', environment: 'local fixture',
    },
    baseline: { status: 'not-applicable', reason: 'Greenfield journey has no coded predecessor' },
    implementation: { artifacts }, requires_video: requiresVideo, known_gaps: [],
  };
}

function candidate() {
  const facts = {
    base_commit: commit('1'), head: commit('2'), origin_main: commit('1'), branch: 'feature/journey',
    tree_fingerprint: digest('3'), tracked_diff_digest: digest('4'),
    untracked_manifest_digest: digest('5'), remote: { name: 'origin', url_digest: digest('6') },
  };
  return { ...facts, fingerprint: digestValue(facts) };
}

function sections() {
  return Object.fromEntries(Array.from({ length: 11 }, (_, index) => [String(index + 1), {
    heading: `Section ${index + 1}`, line: index + 3, digest: String((index + 1) % 10).repeat(64),
  }]));
}

test('one UI feature travels Plan → Build↔Verify → Ship → Complete with explicit reviews', () => {
  let run = createInitialRun({
    repoId: digest('a'), checkoutId: digest('b'), taskHash: digest('c'), runId,
    objective: 'Complete the accepted UI journey', intent: { kind: 'plan', digest: digest('d') },
    now: '2026-07-12T00:00:00.000Z',
  });
  run = applyEvent(run, { type: 'plan.prototype-ready' });
  run = recordSupport(run);
  run = applyEvent(run, { type: 'plan.ready-for-approval' });
  run = applyEvent(run, {
    type: 'plan.accepted',
    plan: {
      path: 'plan.md', digest: digest('f'), approver: 'user',
      slice_ids: ['S1', 'S2'], acceptance_ids: ['P1', 'P2'], sections: sections(),
      ui: {
        applicable: true,
        baseline: { applicable: false, reason: 'not applicable — greenfield fixture' },
        design_owner: 'fixture token proposal', exploration: 'constrained',
        prototype: { path: `.hard-eng/prototypes/${runId}/flow.html`, digest: digest('6') },
        direction: 'Fixture direction — user-approved', direction_boards: [],
        states: ['happy', 'loading', 'empty', 'validation', 'permission', 'error'],
        cadence: 'meaningful-milestones', coded_options: 'direction already constrained',
      },
    },
  });

  run = applyEvent(run, { type: 'build.red-proven', proof: proof('red-s1', 'red', 'fail-expected', digest('1')) });
  run = applyEvent(run, { type: 'build.implemented', candidate_fingerprint: digest('2') });
  run = applyEvent(run, { type: 'build.verify-passed', proof: proof('verify-s1', 'verify', 'pass', digest('2')) });
  const milestone = visual('milestone', digest('2'), false);
  run = applyEvent(run, { type: 'build.visual-milestone', evidence_id: 'visual-s1', evidence: milestone });
  run = applyEvent(run, {
    type: 'build.user-reviewed', approver: 'user', decision: 'approved', evidence_digest: digestValue(milestone),
  });
  run = applyEvent(run, { type: 'build.review-passed', proof: proof('review-s1', 'review', 'pass', digest('2')) });
  run = applyEvent(run, { type: 'build.next-slice' });

  run = applyEvent(run, { type: 'build.red-proven', proof: proof('red-s2', 'red', 'fail-expected', digest('3')) });
  run = applyEvent(run, { type: 'build.implemented', candidate_fingerprint: digest('4') });
  run = applyEvent(run, { type: 'build.verify-passed', proof: proof('verify-s2', 'verify', 'pass', digest('4')) });
  run = applyEvent(run, { type: 'build.review-passed', proof: proof('review-s2', 'review', 'pass', digest('4')) });
  run = applyEvent(run, { type: 'build.all-slices-proven', candidate_fingerprint: digest('4') });

  const identity = candidate();
  const finalEvidence = visual('final', identity.fingerprint, true);
  run = applyEvent(run, {
    type: 'ship.candidate-green',
    check: {
      preflight_digest: digest('0'), registry_digest: digest('e'),
      results_digest: digest('f'), candidate: identity,
    },
    evidence: finalEvidence,
  });
  run = applyEvent(run, {
    type: 'ship.candidate-approved', approver: 'user',
    candidate_fingerprint: identity.fingerprint, evidence_digest: digestValue(finalEvidence),
  });
  run = applyEvent(run, {
    type: 'external-action.prepared',
    action: {
      intent: 'publish', precondition_fingerprint: identity.fingerprint,
      idempotency_key: digest('a'), reconciliation_command: 'git fetch origin',
      publication: { mode: 'branch', remote_ref: 'refs/remotes/origin/journey' },
      publication_preflight: (() => {
        const facts = {
          mode: 'branch', remote_ref: 'refs/remotes/origin/journey',
          remote_url_digest: identity.remote.url_digest, remote_head_before: null,
          protections: { status: 'not-applicable', observer: 'github', evidence_digest: digest('2') },
        };
        return { ...facts, evidence_digest: digestValue(facts) };
      })(),
    },
  });
  run = applyEvent(run, {
    type: 'ship.published-current',
    external_action: {
      idempotency_key: digest('a'), observed_result: 'remote ref contains the exact commit',
      evidence_digest: digest('b'),
    },
    publication: {
      mode: 'branch', commit: commit('9'), parent: identity.head, tree: commit('8'),
      tree_fingerprint: identity.tree_fingerprint, candidate_fingerprint: identity.fingerprint,
      remote_ref: 'refs/remotes/origin/journey',
      remote_head: commit('9'), current: true,
      remote_url_digest: identity.remote.url_digest, remote_observation_digest: digest('b'),
      ci: { status: 'pass', commit: commit('9'), observer: 'github', evidence_digest: digest('1') },
      protections: { status: 'not-applicable', observer: 'github', evidence_digest: digest('2') },
      rollback: { strategy: 'revert-commit', target_commit: commit('9'), evidence_digest: digest('3') },
    },
  });
  assert.equal(run.cursor.step, 'await-publication-approval');
  run = applyEvent(run, {
    type: 'ship.publication-approved', approver: 'user', commit: commit('9'),
    evidence_digest: run.publication.evidence_digest,
  });
  assert.deepEqual([run.phase, run.cursor.step, run.candidate.approval], ['Complete', 'complete', 'approved']);
  assert.equal(run.proof.find((item) => item.id === 'visual-s1').approval, 'approved');
});

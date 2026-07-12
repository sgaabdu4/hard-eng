import test from 'node:test';
import assert from 'node:assert/strict';
import { digestValue } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';
import { applyEvent, createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';
import { validatePublication } from '../../plugins/hard-eng/runtime/lib/ship.mjs';

const digest = (character) => character.repeat(64);
const commit = (character) => character.repeat(40);

function candidate() {
  const facts = {
    base_commit: commit('1'),
    head: commit('2'),
    origin_main: commit('1'),
    branch: 'feature/fixture',
    tree_fingerprint: digest('3'),
    tracked_diff_digest: digest('4'),
    untracked_manifest_digest: digest('5'),
    remote: { name: 'origin', url_digest: digest('6') },
  };
  return { ...facts, fingerprint: digestValue(facts) };
}

function shipRun({ userVisible = false } = {}) {
  const run = createInitialRun({
    repoId: digest('a'), checkoutId: digest('b'), taskHash: digest('c'),
    objective: 'Publish one exact candidate', runId: 'he-ship-state',
    intent: {
      kind: 'direct', digest: digest('d'), acceptance: ['candidate is current'], scope: ['fixture'],
      non_goals: [], justification: 'Bounded fixture', user_visible: userVisible,
    },
    now: '2026-07-12T00:00:00.000Z',
  });
  run.phase = 'Ship';
  run.cursor = { step: 'preflight' };
  return run;
}

function check(candidateIdentity = candidate()) {
  return {
    preflight_digest: digest('0'),
    registry_digest: digest('e'),
    results_digest: digest('f'),
    candidate: candidateIdentity,
  };
}

function evidence(candidateFingerprint) {
  const runId = 'he-ship-state';
  return {
    kind: 'final',
    applicability: 'applicable',
    candidate_fingerprint: candidateFingerprint,
    approved_direction_digest: digest('7'),
    scenario: {
      role: 'member', data_fixture: 'seed-v1', route: '/fixture',
      viewport_or_device: '1440x900', environment: 'local fixture',
    },
    baseline: { status: 'not-applicable', reason: 'Greenfield fixture has no coded predecessor' },
    implementation: { artifacts: [{
      kind: 'screenshot', path: `${'.hard-eng/evidence/he-ship-state'}/after.png`, digest: digest('8'),
    }] },
    requires_video: false,
    known_gaps: [],
  };
}

function publication(candidateIdentity) {
  return {
    mode: 'branch',
    commit: commit('9'),
    parent: candidateIdentity.head,
    tree: commit('8'),
    tree_fingerprint: candidateIdentity.tree_fingerprint,
    candidate_fingerprint: candidateIdentity.fingerprint,
    remote_ref: 'refs/remotes/origin/fixture',
    remote_head: commit('9'),
    remote_url_digest: candidateIdentity.remote.url_digest,
    remote_observation_digest: digest('b'),
    current: true,
    ci: { status: 'pass', commit: commit('9'), observer: 'github', evidence_digest: digest('1') },
    protections: { status: 'not-applicable', observer: 'github', evidence_digest: digest('2') },
    rollback: { strategy: 'revert-commit', target_commit: commit('9'), evidence_digest: digest('3') },
  };
}

function prPublication(candidateIdentity, overrides = {}) {
  const pullRequest = {
    number: 42,
    state: 'open',
    draft: false,
    head_commit: commit('9'),
    head_ref: 'feature/fixture',
    base_ref: 'main',
    unresolved_review_threads: 0,
  };
  const value = {
    ...publication(candidateIdentity),
    mode: 'pr',
    pr_number: 42,
    remote_ref: 'refs/remotes/origin/feature/fixture',
    external_action_digest: digest('e'),
    pull_request: { ...pullRequest, evidence_digest: digestValue(pullRequest) },
    ...overrides,
  };
  return { ...value, preflight: publicationPreflight(candidateIdentity, value) };
}

function publicationPreflight(candidateIdentity, value = publication(candidateIdentity)) {
  const protections = {
    status: 'not-applicable',
    observer: 'github',
    evidence_digest: digestValue({ mode: value.mode, branch: value.remote_ref.split('/').at(-1) }),
  };
  const facts = {
    mode: value.mode,
    remote_ref: value.remote_ref,
    ...(value.mode === 'pr' ? { pr_number: value.pr_number } : {}),
    remote_url_digest: candidateIdentity.remote.url_digest,
    remote_head_before: null,
    protections,
  };
  return { ...facts, evidence_digest: digestValue(facts) };
}

function preparePublication(run, candidateIdentity) {
  const value = publication(candidateIdentity);
  return applyEvent(run, {
    type: 'external-action.prepared',
    action: {
      intent: 'publish', precondition_fingerprint: candidateIdentity.fingerprint,
      idempotency_key: digest('a'), reconciliation_command: 'git fetch origin',
      publication: { mode: value.mode, remote_ref: value.remote_ref },
      publication_preflight: publicationPreflight(candidateIdentity, value),
    },
  });
}

function published(candidateIdentity, value = publication(candidateIdentity)) {
  return {
    type: 'ship.published-current',
    publication: value,
    external_action: {
      idempotency_key: digest('a'), observed_result: 'remote ref contains the exact commit',
      evidence_digest: digest('b'),
    },
  };
}

test('non-visual Ship records exact check proof and completes only on current publication', () => {
  const identity = candidate();
  let run = applyEvent(shipRun(), {
    type: 'ship.candidate-green',
    check: check(identity),
    evidence: { applicability: 'not-applicable', reason: 'No user-visible interface changed' },
    at: '2026-07-12T00:00:01.000Z',
  });
  assert.equal(run.cursor.step, 'publish');
  assert.equal(run.candidate.fingerprint, identity.fingerprint);
  assert.equal(run.proof.at(-1).kind, 'check');
  assert.throws(() => applyEvent(run, published(identity)), /external-action journal/i);
  assert.throws(() => applyEvent(run, {
    type: 'external-action.prepared',
    action: {
      intent: 'publish', precondition_fingerprint: digest('0'),
      idempotency_key: digest('a'), reconciliation_command: 'git fetch origin',
    },
  }), /precondition/i);
  run = preparePublication(run, identity);
  assert.throws(() => applyEvent(run, published(identity, {
    ...publication(identity), remote_ref: 'refs/remotes/origin/main',
  })), /branch publication cannot target main/i);
  assert.throws(() => applyEvent(run, published(identity, {
    ...publication(identity), remote_head: commit('7'),
  })), /current|commit/i);
  assert.throws(() => applyEvent(run, published(identity, {
    ...publication(identity), tree_fingerprint: digest('0'),
  })), /tree/i);
  run = applyEvent(run, published(identity));
  assert.deepEqual([run.phase, run.cursor.step, run.publication.approval], ['Ship', 'await-publication-approval', 'pending']);
  assert.throws(() => applyEvent(run, {
    type: 'ship.publication-approved', approver: 'user', commit: commit('9'), evidence_digest: digest('0'),
  }), /evidence digest/i);
  run = applyEvent(run, {
    type: 'ship.publication-approved', approver: 'user', commit: commit('9'),
    evidence_digest: run.publication.evidence_digest,
  });
  assert.deepEqual([run.phase, run.cursor.step, run.lease.reconciliation], ['Complete', 'complete', 'released']);
});

test('user-visible Ship requires final evidence and exact candidate approval before publication', () => {
  const identity = candidate();
  const visual = evidence(identity.fingerprint);
  let run = applyEvent(shipRun({ userVisible: true }), {
    type: 'ship.candidate-green', check: check(identity), evidence: visual,
  });
  assert.equal(run.cursor.step, 'await-candidate-approval');
  assert.throws(() => applyEvent(run, {
    type: 'ship.published-current', publication: publication(identity),
  }), /transition|approval/i);
  assert.throws(() => applyEvent(run, {
    type: 'ship.candidate-approved', approver: 'user',
    candidate_fingerprint: identity.fingerprint, evidence_digest: digest('0'),
  }), /evidence digest/i);
  run = applyEvent(run, {
    type: 'ship.candidate-approved', approver: 'user',
    candidate_fingerprint: identity.fingerprint, evidence_digest: digestValue(visual),
  });
  assert.equal(run.cursor.step, 'publish');
  run = preparePublication(run, identity);
  run = applyEvent(run, published(identity));
  assert.equal(run.cursor.step, 'await-publication-approval');
  run = applyEvent(run, {
    type: 'ship.publication-approved', approver: 'user', commit: commit('9'),
    evidence_digest: run.publication.evidence_digest,
  });
  assert.equal(run.phase, 'Complete');
});

test('PR publication requires an exact open head, resolved threads, and candidate parent', () => {
  const identity = candidate();
  assert.equal(validatePublication(prPublication(identity), identity), true);
  assert.throws(() => validatePublication(prPublication(identity, {
    parent: commit('0'),
  }), identity), /parent/i);
  assert.throws(() => validatePublication(prPublication(identity, {
    pull_request: {
      ...prPublication(identity).pull_request,
      unresolved_review_threads: 1,
    },
  }), identity), /review thread|digest/i);
  assert.throws(() => validatePublication(prPublication(identity, {
    remote_ref: 'refs/remotes/origin/main',
  }), identity), /pull request.*main|head branch/i);
});

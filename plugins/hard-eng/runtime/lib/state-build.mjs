import { clone } from './canonical.mjs';
import { validateVisualEvidence } from './evidence.mjs';
import {
  markAllProofStale,
  markProofFreshness,
  recordProof,
  requireFreshSliceProof,
} from './proof.mjs';
import { assertDigest, requireSupportPlane, transitionError } from './state-transition.mjs';

function applyDrift(run, event, slice) {
  if (!['implement', 'verify', 'review', 'slice-proven', 'await-user-review'].includes(run.cursor.step)) {
    transitionError(run, event);
  }
  assertDigest(event.candidate_fingerprint, 'Drifted candidate fingerprint');
  if (typeof event.reason !== 'string' || !event.reason.trim() || event.reason.length > 240) {
    throw new Error('Candidate drift requires a bounded reason.');
  }
  markProofFreshness(run, event.candidate_fingerprint);
  run.candidate = null;
  run.cursor = { step: 'verify', slice, candidate_fingerprint: event.candidate_fingerprint };
}

function returnToPlan(run, event) {
  assertDigest(event.intent_digest, 'Plan intent digest');
  if (typeof event.reason !== 'string' || !event.reason.trim()) throw new Error('Plan trigger requires a bounded reason.');
  run.intent = { kind: 'plan', digest: event.intent_digest };
  run.phase = 'Plan';
  run.cursor = { step: 'discover' };
  run.plan = null;
  run.candidate = null;
  run.proof = [];
  run.support_tools = [];
}

function applyRed(run, event, timestamp, slice) {
  if (run.cursor.step !== 'red') transitionError(run, event);
  requireSupportPlane(run, 'Build red proof');
  const stored = recordProof(run, event.proof, {
    kind: 'red', result: 'fail-expected', timestamp,
    candidateFingerprint: event.proof.candidate_fingerprint,
  });
  run.cursor = { step: 'implement', slice, candidate_fingerprint: stored.candidate_fingerprint };
}

function applyImplementation(run, event, slice) {
  if (run.cursor.step !== 'implement') transitionError(run, event);
  assertDigest(event.candidate_fingerprint, 'Implementation candidate fingerprint');
  if (run.cursor.repair && event.candidate_fingerprint === run.cursor.repair.last_failure_fingerprint) {
    throw new Error('An unchanged failed candidate cannot be retried as implementation.');
  }
  markProofFreshness(run, event.candidate_fingerprint);
  run.candidate = null;
  run.cursor = {
    step: 'verify', slice, candidate_fingerprint: event.candidate_fingerprint,
    ...(run.cursor.repair ? { repair: clone(run.cursor.repair) } : {}),
  };
}

function applyVerificationFailure(run, event, timestamp, slice) {
  if (run.cursor.step !== 'verify') transitionError(run, event);
  assertDigest(event.hypothesis_digest, 'Root-cause hypothesis digest');
  recordProof(run, event.proof, {
    kind: 'verify', result: 'fail', timestamp,
    candidateFingerprint: run.cursor.candidate_fingerprint,
  });
  const previous = run.cursor.repair;
  const attempts = previous?.hypothesis_digest === event.hypothesis_digest ? previous.attempts + 1 : 1;
  if (attempts > 2) throw new Error('Two repair attempts exhausted for the unchanged root-cause hypothesis.');
  run.cursor = {
    step: 'implement', slice, candidate_fingerprint: run.cursor.candidate_fingerprint,
    repair: {
      hypothesis_digest: event.hypothesis_digest,
      attempts,
      last_failure_fingerprint: event.proof.candidate_fingerprint,
    },
  };
}

function applyVerificationPass(run, event, timestamp, slice) {
  if (run.cursor.step !== 'verify') transitionError(run, event);
  const stored = recordProof(run, event.proof, {
    kind: 'verify', result: 'pass', timestamp,
    candidateFingerprint: run.cursor.candidate_fingerprint,
  });
  run.cursor = { step: 'review', slice, candidate_fingerprint: stored.candidate_fingerprint };
}

function applyReview(run, event, timestamp, slice) {
  if (run.cursor.step !== 'review') transitionError(run, event);
  const stored = recordProof(run, event.proof, {
    kind: 'review', result: 'pass', timestamp,
    candidateFingerprint: run.cursor.candidate_fingerprint,
  });
  run.cursor = { step: 'slice-proven', slice, candidate_fingerprint: stored.candidate_fingerprint };
}

function applyNextSlice(run, event, slice) {
  if (run.cursor.step !== 'slice-proven') transitionError(run, event);
  const total = run.plan?.slice_ids?.length ?? 1;
  if (slice >= total) throw new Error('No remaining planned slice; declare all slices proven.');
  run.cursor = { step: 'red', slice: slice + 1, candidate_fingerprint: run.cursor.candidate_fingerprint };
}

function applyVisualMilestone(run, event, timestamp, slice) {
  if (!['review', 'slice-proven'].includes(run.cursor.step)) transitionError(run, event);
  const visual = validateVisualEvidence(event.evidence, {
    runId: run.run_id,
    final: false,
    candidateFingerprint: run.cursor.candidate_fingerprint,
  });
  const stored = recordProof(run, {
    id: event.evidence_id,
    kind: 'visual',
    name: 'Coded visual milestone',
    result: 'pass',
    source: { kind: 'artifact', reference: `evidence:${event.evidence_id}` },
    evidence_digest: visual.evidence_digest,
    candidate_fingerprint: visual.candidate_fingerprint,
    visual,
    approval: 'pending',
  }, {
    kind: 'visual', result: 'pass', timestamp,
    candidateFingerprint: run.cursor.candidate_fingerprint,
  });
  run.cursor = {
    step: 'await-user-review', slice, return_step: run.cursor.step,
    candidate_fingerprint: run.cursor.candidate_fingerprint,
    visual_proof_id: stored.id,
  };
}

function applyUserReview(run, event, slice) {
  if (run.cursor.step !== 'await-user-review' || event.approver !== 'user') transitionError(run, event);
  const proof = run.proof.find((item) => item.id === run.cursor.visual_proof_id && item.kind === 'visual');
  if (!proof || proof.evidence_digest !== event.evidence_digest) {
    throw new Error('Visual review evidence digest does not match the pending milestone.');
  }
  if (!['approved', 'implementation-defect', 'plan-change'].includes(event.decision)) {
    throw new Error('Visual review decision is invalid.');
  }
  proof.approval = event.decision;
  proof.approved_by = 'user';
  if (event.decision === 'approved') {
    run.cursor = { step: run.cursor.return_step, slice, candidate_fingerprint: run.cursor.candidate_fingerprint };
  } else if (event.decision === 'implementation-defect') {
    markAllProofStale(run);
    run.candidate = null;
    run.cursor = { step: 'implement', slice, candidate_fingerprint: run.cursor.candidate_fingerprint };
  } else {
    assertDigest(event.intent_digest, 'Revised Plan intent digest');
    markAllProofStale(run);
    run.intent = { kind: 'plan', digest: event.intent_digest };
    run.phase = 'Plan';
    run.cursor = { step: 'discover' };
    run.plan = null;
    run.candidate = null;
    run.proof = [];
    run.support_tools = [];
  }
}

function applyAllSlices(run, event, slice) {
  if (run.cursor.step !== 'slice-proven') transitionError(run, event);
  const total = run.plan?.slice_ids?.length ?? 1;
  if (slice !== total) throw new Error(`Build has remaining planned slices; final planned slice is S${total}.`);
  if (event.candidate_fingerprint !== run.cursor.candidate_fingerprint) {
    throw new Error('All slices proven candidate fingerprint is stale.');
  }
  requireFreshSliceProof(run, { slice, candidateFingerprint: event.candidate_fingerprint });
  run.phase = 'Ship';
  run.cursor = { step: 'preflight' };
}

export function applyBuildEvent(run, event, timestamp) {
  const slice = run.cursor.slice ?? 1;
  switch (event.type) {
    case 'build.candidate-drift': applyDrift(run, event, slice); break;
    case 'build.plan-triggered': returnToPlan(run, event); break;
    case 'build.red-proven': applyRed(run, event, timestamp, slice); break;
    case 'build.implemented': applyImplementation(run, event, slice); break;
    case 'build.verify-failed': applyVerificationFailure(run, event, timestamp, slice); break;
    case 'build.verify-passed': applyVerificationPass(run, event, timestamp, slice); break;
    case 'build.review-passed': applyReview(run, event, timestamp, slice); break;
    case 'build.next-slice': applyNextSlice(run, event, slice); break;
    case 'build.visual-milestone': applyVisualMilestone(run, event, timestamp, slice); break;
    case 'build.user-reviewed': applyUserReview(run, event, slice); break;
    case 'build.all-slices-proven': applyAllSlices(run, event, slice); break;
    default: transitionError(run, event);
  }
}

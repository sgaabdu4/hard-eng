import { clone, digestValue } from './canonical.mjs';
import { recordProof } from './proof.mjs';
import {
  publicationEvidenceDigest,
  validateCandidateEvidence,
  validatePublication,
  validateShipCheck,
} from './ship.mjs';
import { assertDigest, transitionError } from './state-transition.mjs';

function applyCandidate(run, event, timestamp) {
  if (run.findings.some((finding) => finding.admission === 'open')) {
    throw new Error('Ship candidate is blocked by an admitted finding.');
  }
  const check = validateShipCheck(event.check);
  const userVisible = run.plan?.ui?.applicable === true || run.intent.user_visible === true;
  const evidence = validateCandidateEvidence(event.evidence, {
    runId: run.run_id,
    candidateFingerprint: check.candidate.fingerprint,
    userVisible,
  });
  recordProof(run, {
    id: `ship-check-${run.revision}`,
    kind: 'check',
    name: 'Canonical Ship check registry',
    result: 'pass',
    source: { kind: 'command', reference: 'he check --all' },
    evidence_digest: check.results_digest,
    candidate_fingerprint: check.candidate.fingerprint,
  }, { kind: 'check', result: 'pass', timestamp });
  run.candidate = {
    ...clone(check.candidate),
    check: {
      registry_digest: check.registry_digest,
      results_digest: check.results_digest,
      preflight_digest: check.preflight_digest,
    },
    user_visible: userVisible,
    evidence,
    approval: userVisible ? 'pending' : 'not-required',
  };
  run.cursor = userVisible ? { step: 'await-candidate-approval' } : { step: 'publish' };
}

function applyCandidateApproval(run, event, timestamp) {
  if (event.approver !== 'user') throw new Error('Candidate approval requires the user.');
  if (event.candidate_fingerprint !== run.candidate?.fingerprint) throw new Error('Candidate approval fingerprint is stale.');
  if (event.evidence_digest !== run.candidate?.evidence?.evidence_digest) throw new Error('Candidate approval evidence digest is stale.');
  run.candidate.approval = 'approved';
  run.candidate.approved_by = 'user';
  run.candidate.approved_at = timestamp;
  run.cursor = { step: 'publish' };
}

function applyPublication(run, event) {
  if (run.findings.some((finding) => finding.admission === 'open')) throw new Error('Complete is blocked by an admitted finding.');
  if (run.candidate?.user_visible && run.candidate.approval !== 'approved') throw new Error('Complete requires explicit candidate approval.');
  const external = event.external_action;
  if (
    run.interruption?.intent !== 'publish'
    || external?.idempotency_key !== run.interruption.idempotency_key
    || typeof external?.observed_result !== 'string'
    || !external.observed_result.trim()
    || external.observed_result === 'unknown'
    || external.observed_result.length > 240
  ) throw new Error('Publication requires the matching observed external-action journal.');
  assertDigest(external.evidence_digest, 'Publication external-action evidence');
  const publication = {
    ...clone(event.publication ?? {}),
    preflight: clone(run.interruption.publication_preflight),
    external_action_digest: digestValue(external),
  };
  validatePublication(publication, run.candidate);
  run.publication = {
    ...publication,
    approval: 'pending',
    evidence_digest: publicationEvidenceDigest(publication),
  };
  run.interruption = null;
  run.cursor = { step: 'await-publication-approval' };
}

function applyPublicationApproval(run, event, timestamp) {
  if (
    event.approver !== 'user'
    || event.commit !== run.publication.commit
    || event.evidence_digest !== run.publication.evidence_digest
  ) throw new Error('Publication approval requires the exact observed commit and evidence digest from the user.');
  run.publication.approval = 'approved';
  run.publication.approved_by = 'user';
  run.publication.approved_at = timestamp;
  validatePublication(run.publication, run.candidate, { requireApproval: true });
  run.phase = 'Complete';
  run.cursor = { step: 'complete' };
  run.lease.reconciliation = 'released';
}

export function applyShipEvent(run, event, timestamp) {
  if (event.type === 'ship.candidate-green' && run.cursor.step === 'preflight') {
    applyCandidate(run, event, timestamp);
  } else if (event.type === 'ship.candidate-approved' && run.cursor.step === 'await-candidate-approval') {
    applyCandidateApproval(run, event, timestamp);
  } else if (event.type === 'ship.published-current' && run.cursor.step === 'publish') {
    applyPublication(run, event);
  } else if (event.type === 'ship.publication-approved' && run.cursor.step === 'await-publication-approval') {
    applyPublicationApproval(run, event, timestamp);
  } else {
    transitionError(run, event);
  }
}

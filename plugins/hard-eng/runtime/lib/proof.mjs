import { clone } from './canonical.mjs';
import { validateEvidenceSummary } from './candidate.mjs';

const proofKinds = new Set(['red', 'verify', 'review', 'visual', 'e2e', 'check', 'ci', 'guard']);
const proofResults = new Set(['fail-expected', 'fail', 'pass', 'approved']);
const sourceKinds = new Set(['command', 'artifact', 'review', 'user', 'ci']);

function assertKeys(value, allowed, label) {
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
}

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

export function validateProof(proof, { stored = true } = {}) {
  if (!proof || typeof proof !== 'object' || Array.isArray(proof)) throw new Error('Typed proof is required.');
  const allowed = new Set([
    'id', 'kind', 'name', 'result', 'source', 'evidence_digest', 'candidate_fingerprint',
    'visual', 'approval', ...(stored ? ['stage', 'slice', 'fresh', 'recorded_at', 'approved_by'] : []),
  ]);
  assertKeys(proof, allowed, 'Proof');
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(proof.id ?? '')) throw new Error('Proof ID is invalid.');
  if (!proofKinds.has(proof.kind)) throw new Error('Proof kind is invalid.');
  if (typeof proof.name !== 'string' || !proof.name.trim() || proof.name.length > 120) throw new Error('Proof name is invalid.');
  if (!proofResults.has(proof.result)) throw new Error('Proof result is invalid.');
  if (!proof.source || !sourceKinds.has(proof.source.kind)) throw new Error('Proof source kind is invalid.');
  assertKeys(proof.source, new Set(['kind', 'reference']), 'Proof source');
  if (typeof proof.source.reference !== 'string' || !proof.source.reference.trim() || proof.source.reference.length > 240) {
    throw new Error('Proof source reference is invalid.');
  }
  assertDigest(proof.evidence_digest, 'Proof evidence digest');
  assertDigest(proof.candidate_fingerprint, 'Proof candidate fingerprint');
  if (stored) {
    if (typeof proof.fresh !== 'boolean') throw new Error('Stored proof freshness is required.');
    if (!['Plan', 'Build', 'Ship'].includes(proof.stage)) throw new Error('Stored proof stage is invalid.');
    if (typeof proof.recorded_at !== 'string') throw new Error('Stored proof timestamp is required.');
  }
  if (proof.approval !== undefined && !['pending', 'approved', 'implementation-defect', 'plan-change'].includes(proof.approval)) {
    throw new Error('Proof approval is invalid.');
  }
  if (proof.approved_by !== undefined && proof.approved_by !== 'user') throw new Error('Proof approver is invalid.');
  if (proof.visual !== undefined) validateEvidenceSummary(proof.visual);
  return true;
}

export function markProofFreshness(run, candidateFingerprint) {
  assertDigest(candidateFingerprint, 'Candidate fingerprint');
  run.proof = run.proof.map((item) => ({
    ...item,
    fresh: item.fresh === true && item.candidate_fingerprint === candidateFingerprint,
  }));
}

export function markAllProofStale(run) {
  run.proof = run.proof.map((item) => ({ ...item, fresh: false }));
}

export function recordProof(run, proof, { kind, result, timestamp, candidateFingerprint = null } = {}) {
  validateProof(proof, { stored: false });
  if (proof.kind !== kind || proof.result !== result) {
    throw new Error(`Proof for ${kind} must record result ${result}.`);
  }
  const current = candidateFingerprint ?? run.cursor.candidate_fingerprint ?? null;
  if (current && proof.candidate_fingerprint !== current) {
    throw new Error('Proof candidate fingerprint does not match the current Build candidate.');
  }
  markProofFreshness(run, proof.candidate_fingerprint);
  const stored = {
    ...clone(proof),
    stage: run.phase,
    slice: run.cursor.slice ?? null,
    fresh: true,
    recorded_at: timestamp,
  };
  validateProof(stored);
  run.proof.push(stored);
  return stored;
}

export function requireFreshSliceProof(run, { slice, candidateFingerprint }) {
  assertDigest(candidateFingerprint, 'Candidate fingerprint');
  const has = (kind) => run.proof.some((proof) => (
    proof.stage === 'Build'
    && proof.slice === slice
    && proof.kind === kind
    && proof.result === 'pass'
    && proof.fresh === true
    && proof.candidate_fingerprint === candidateFingerprint
  ));
  if (!has('verify') || !has('review')) {
    throw new Error('All slices proven requires fresh verify and review proof for the current candidate fingerprint.');
  }
}

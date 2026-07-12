import { digestValue } from './canonical.mjs';
import { validateCandidate } from './candidate.mjs';
import { validateVisualEvidence } from './evidence.mjs';

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function assertCommit(value, label) {
  if (!/^[a-f0-9]{40,64}$/i.test(value ?? '')) throw new Error(`${label} must be a Git object ID.`);
}

function assertKeys(value, allowed, label) {
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
}

export function validateShipCheck(check) {
  if (!check || typeof check !== 'object' || Array.isArray(check)) throw new Error('Ship check proof is required.');
  assertDigest(check.registry_digest, 'Ship check registry digest');
  assertDigest(check.results_digest, 'Ship check results digest');
  assertDigest(check.preflight_digest, 'Ship preflight digest');
  validateCandidate(check.candidate);
  return check;
}

export function validateCandidateEvidence(evidence, { runId, candidateFingerprint, userVisible } = {}) {
  if (userVisible) return validateVisualEvidence(evidence, {
    runId,
    final: true,
    candidateFingerprint,
  });
  if (!evidence || evidence.applicability !== 'not-applicable') {
    throw new Error('Non-visual candidate requires a not-applicable evidence record.');
  }
  if (typeof evidence.reason !== 'string' || !evidence.reason.trim() || evidence.reason.length > 240) {
    throw new Error('Non-visual candidate requires a bounded not-applicable reason.');
  }
  return {
    applicability: 'not-applicable',
    reason_digest: digestValue(evidence.reason),
    evidence_digest: digestValue(evidence),
  };
}

export function publicationEvidenceDigest(publication) {
  const {
    approval: ignoredApproval,
    evidence_digest: ignoredEvidence,
    approved_by: ignoredApprover,
    approved_at: ignoredApprovedAt,
    ...evidence
  } = publication;
  return digestValue(evidence);
}

export function validatePublicationPreflight(preflight, candidate, {
  mode = preflight?.mode,
  remoteRef = preflight?.remote_ref,
  prNumber = preflight?.pr_number,
  commit = preflight?.commit,
} = {}) {
  if (!preflight || typeof preflight !== 'object' || Array.isArray(preflight)) {
    throw new Error('Publication preparation receipt is required.');
  }
  assertKeys(preflight, new Set([
    'mode', 'remote_ref', 'pr_number', 'remote_url_digest', 'remote_head_before',
    'protections', 'commit', 'commit_message_digest', 'commit_message_evidence_digest',
    'evidence_digest',
  ]), 'Publication preparation');
  if (!['branch', 'pr', 'direct-main'].includes(preflight.mode) || preflight.mode !== mode) {
    throw new Error('Publication preparation mode is invalid or stale.');
  }
  if (preflight.remote_ref !== remoteRef || preflight.remote_url_digest !== candidate?.remote?.url_digest) {
    throw new Error('Publication preparation ref or remote is stale.');
  }
  assertDigest(preflight.remote_url_digest, 'Publication preparation remote URL');
  assertCommit(preflight.commit, 'Publication preparation commit');
  if (preflight.commit !== commit) {
    throw new Error('Publication preparation commit is stale.');
  }
  assertDigest(preflight.commit_message_digest, 'Publication preparation commit message');
  assertDigest(preflight.commit_message_evidence_digest, 'Publication preparation commit-message evidence');
  const protections = preflight.protections;
  if (!protections || typeof protections !== 'object' || Array.isArray(protections)) {
    throw new Error('Publication preparation protection evidence is required.');
  }
  assertKeys(protections, new Set(['status', 'observer', 'evidence_digest']), 'Publication preparation protections');
  assertDigest(protections.evidence_digest, 'Publication preparation protection evidence');
  if (preflight.mode === 'direct-main') {
    assertCommit(preflight.remote_head_before, 'Publication preparation remote head');
    if (
      preflight.remote_ref !== 'refs/remotes/origin/main'
      || preflight.remote_head_before !== candidate.origin_main
      || preflight.remote_head_before !== candidate.head
      || protections.status !== 'captured'
      || protections.observer !== 'github'
    ) throw new Error('Direct-main preparation is not bound to current origin/main protections.');
  } else if (
    preflight.remote_head_before !== null
    || protections.status !== 'not-applicable'
    || !['github', 'local-git'].includes(protections.observer)
  ) throw new Error('Branch/PR publication preparation evidence is invalid.');
  if (preflight.mode === 'pr') {
    if (!Number.isSafeInteger(preflight.pr_number) || preflight.pr_number <= 0 || preflight.pr_number !== prNumber) {
      throw new Error('PR publication preparation number is invalid or stale.');
    }
  } else if (preflight.pr_number !== undefined) {
    throw new Error('Non-PR publication preparation cannot contain a pull request number.');
  }
  assertDigest(preflight.evidence_digest, 'Publication preparation evidence');
  const { evidence_digest: ignored, ...evidence } = preflight;
  if (preflight.evidence_digest !== digestValue(evidence)) throw new Error('Publication preparation evidence digest is stale.');
  return true;
}

export function validatePublication(publication, candidate, { requireApproval = false } = {}) {
  if (!publication || typeof publication !== 'object' || Array.isArray(publication)) throw new Error('Typed publication proof is required.');
  assertKeys(publication, new Set([
    'mode', 'commit', 'parent', 'tree', 'tree_fingerprint', 'candidate_fingerprint',
    'remote_ref', 'remote_head', 'current', 'ci', 'protections', 'rollback',
    'remote_url_digest', 'remote_observation_digest',
    'pr_number', 'pull_request', 'preflight',
    'external_action_digest', 'approval', 'evidence_digest', 'approved_by', 'approved_at',
  ]), 'Publication');
  if (!['branch', 'pr', 'direct-main'].includes(publication.mode)) throw new Error('Publication mode is invalid.');
  for (const field of ['commit', 'parent', 'tree', 'remote_head']) assertCommit(publication[field], `Publication ${field}`);
  if (publication.current !== true || publication.remote_head !== publication.commit) {
    throw new Error('Published commit is not current at the remote head.');
  }
  if (
    typeof publication.remote_ref !== 'string'
    || !/^refs\/remotes\/origin\/[A-Za-z0-9._/-]+$/.test(publication.remote_ref)
    || publication.remote_ref.includes('..')
    || publication.remote_ref.endsWith('/')
  ) throw new Error('Publication remote ref is invalid.');
  const branch = publication.remote_ref.slice('refs/remotes/origin/'.length);
  if (publication.mode === 'direct-main' && branch !== 'main') throw new Error('Direct-main publication must target origin/main.');
  if (publication.mode === 'branch' && branch === 'main') throw new Error('Branch publication cannot target main.');
  if (publication.mode === 'pr' && branch === 'main') throw new Error('Pull request publication cannot use main as its head branch.');
  assertDigest(publication.remote_url_digest, 'Publication remote URL evidence');
  assertDigest(publication.remote_observation_digest, 'Publication remote observation');
  validatePublicationPreflight(publication.preflight, candidate, {
    mode: publication.mode,
    remoteRef: publication.remote_ref,
    prNumber: publication.pr_number,
    commit: publication.commit,
  });
  if (publication.remote_url_digest !== publication.preflight.remote_url_digest) {
    throw new Error('Publication remote differs from its prepared remote.');
  }
  if (publication.candidate_fingerprint !== candidate.fingerprint) throw new Error('Publication candidate fingerprint is stale.');
  assertDigest(publication.external_action_digest, 'Publication external action digest');
  if (publication.tree_fingerprint !== candidate.tree_fingerprint) throw new Error('Published tree does not match the approved candidate tree.');
  if (publication.parent !== candidate.head) {
    throw new Error('Published commit parent does not match the approved candidate HEAD.');
  }
  if (publication.ci?.status !== 'pass' || publication.ci.commit !== publication.commit) {
    throw new Error('Canonical CI does not prove the published commit.');
  }
  assertKeys(publication.ci, new Set(['status', 'commit', 'observer', 'evidence_digest']), 'Publication CI');
  if (!['github', 'local-git'].includes(publication.ci.observer)) throw new Error('Publication CI observer is invalid.');
  assertDigest(publication.ci.evidence_digest, 'Publication CI evidence');
  if (!['restored', 'not-applicable'].includes(publication.protections?.status)) {
    throw new Error('Publication protection status is invalid.');
  }
  assertKeys(publication.protections, new Set([
    'status', 'observer', 'before_evidence_digest', 'evidence_digest',
  ]), 'Publication protections');
  if (publication.protections.observer !== publication.ci.observer) throw new Error('Publication observers disagree.');
  assertDigest(publication.protections.evidence_digest, 'Publication protection evidence');
  if (publication.mode === 'direct-main' && publication.protections.status !== 'restored') {
    throw new Error('Direct-main publication requires restored branch protections.');
  }
  if (publication.mode === 'direct-main') {
    if (
      publication.protections.before_evidence_digest !== publication.preflight.protections.evidence_digest
      || publication.protections.evidence_digest !== publication.protections.before_evidence_digest
    ) throw new Error('Direct-main publication protections do not match the prepared protection/rules state.');
  } else if (publication.protections.before_evidence_digest !== undefined) {
    throw new Error('Non-main publication cannot claim a protection restoration snapshot.');
  }
  if (publication.mode === 'pr') {
    if (!Number.isSafeInteger(publication.pr_number) || publication.pr_number <= 0) {
      throw new Error('PR publication requires a positive pull request number.');
    }
    const pull = publication.pull_request;
    if (!pull || typeof pull !== 'object' || Array.isArray(pull)) throw new Error('PR publication evidence is required.');
    assertKeys(pull, new Set([
      'number', 'state', 'draft', 'head_commit', 'head_ref', 'base_ref',
      'unresolved_review_threads', 'evidence_digest',
    ]), 'Publication pull request');
    if (
      pull.number !== publication.pr_number
      || pull.state !== 'open'
      || pull.draft !== false
      || pull.head_commit !== publication.commit
      || pull.head_ref !== branch
      || typeof pull.base_ref !== 'string'
      || !pull.base_ref
      || pull.unresolved_review_threads !== 0
      || publication.ci.observer !== 'github'
      || publication.protections.status !== 'not-applicable'
    ) throw new Error('PR publication is not an open, ready, exact-head pull request with resolved review threads.');
    assertDigest(pull.evidence_digest, 'Publication pull request evidence');
    const { evidence_digest: ignored, ...pullEvidence } = pull;
    if (pull.evidence_digest !== digestValue(pullEvidence)) throw new Error('Publication pull request evidence digest is stale.');
  } else if (publication.pr_number !== undefined || publication.pull_request !== undefined) {
    throw new Error('Non-PR publication cannot contain pull request evidence.');
  }
  if (publication.rollback?.strategy !== 'revert-commit' || publication.rollback.target_commit !== publication.commit) {
    throw new Error('Publication requires an exact revert-commit rollback target.');
  }
  assertKeys(publication.rollback, new Set(['strategy', 'target_commit', 'evidence_digest']), 'Publication rollback');
  assertDigest(publication.rollback.evidence_digest, 'Publication rollback evidence');
  const hasStoredApproval = publication.approval !== undefined
    || publication.evidence_digest !== undefined
    || publication.approved_by !== undefined
    || publication.approved_at !== undefined;
  if (hasStoredApproval) {
    if (!['pending', 'approved'].includes(publication.approval)) throw new Error('Publication approval state is invalid.');
    assertDigest(publication.evidence_digest, 'Publication observation evidence');
    if (publication.evidence_digest !== publicationEvidenceDigest(publication)) {
      throw new Error('Publication observation evidence digest is stale.');
    }
    if (publication.approval === 'pending') {
      if (publication.approved_by !== undefined || publication.approved_at !== undefined) {
        throw new Error('Pending publication cannot contain approval metadata.');
      }
    } else if (publication.approved_by !== 'user' || !Number.isFinite(Date.parse(publication.approved_at))) {
      throw new Error('Approved publication requires explicit user approval metadata.');
    }
  }
  if (requireApproval && publication.approval !== 'approved') {
    throw new Error('Complete requires explicit approval of the publication observation.');
  }
  return true;
}

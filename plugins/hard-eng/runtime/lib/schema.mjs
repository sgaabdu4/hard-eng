import { canonicalJson, assertNoAbsolutePaths, isPlainObject } from './canonical.mjs';
import { validateFinding } from './findings.mjs';
import { validateProof } from './proof.mjs';
import { validateCandidate } from './candidate.mjs';
import { validatePublication, validatePublicationPreflight } from './ship.mjs';
import { nextFor } from './lifecycle.mjs';

export const RUN_SCHEMA = 'hard-eng/run/v1';
export const SESSION_SCHEMA = 'hard-eng/session/v1';
export const MAX_RUN_BYTES = 64 * 1024;

const phases = new Set(['Plan', 'Build', 'Ship', 'Complete']);
const reviewCadences = new Set(['every-vertical-slice', 'meaningful-milestones', 'final-candidate']);
const cursorSteps = {
  Plan: new Set(['discover', 'prototype', 'ready-for-approval']),
  Build: new Set(['red', 'implement', 'verify', 'review', 'slice-proven', 'await-user-review', 'learn']),
  Ship: new Set(['preflight', 'await-candidate-approval', 'publish', 'await-publication-approval', 'learn']),
  Complete: new Set(['complete']),
};
const runKeys = new Set([
  'schema', 'run_id', 'repo_id', 'checkout_id', 'lease', 'objective', 'intent',
  'phase', 'cursor', 'plan', 'candidate', 'proof', 'findings', 'publication',
  'support_tools', 'next', 'revision', 'created_at', 'updated_at', 'interruption',
]);
const sessionKeys = new Set([
  'schema', 'repo_id', 'task_hash', 'run_id', 'binding_revision', 'revoked',
  'pending', 'replays', 'updated_at',
]);
const forbiddenIdentityKeys = /^(?:session_id|turn_id|tool_use_id|transcript_path|prompt|store_root|cwd|password|secret|credential|auth_token)$/i;
const secretLikeValue = /(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|\bsk-[A-Za-z0-9_-]{20,}|\bgh[pousr]_[A-Za-z0-9]{20,}|\bxox[baprs]-[A-Za-z0-9-]{20,}|\bAKIA[A-Z0-9]{16}\b|\bBearer\s+[A-Za-z0-9._-]{20,})/;

function assertAllowedKeys(value, allowed, label) {
  for (const key of Object.keys(value)) {
    if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
  }
}

function assertNoRawIdentityKeys(value, trail = []) {
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertNoRawIdentityKeys(child, [...trail, String(index)]));
    return;
  }
  if (!isPlainObject(value)) return;
  for (const [key, child] of Object.entries(value)) {
    if (forbiddenIdentityKeys.test(key)) throw new Error(`Checkpoint contains forbidden raw identity field ${[...trail, key].join('.')}.`);
    assertNoRawIdentityKeys(child, [...trail, key]);
  }
}

function assertNoSecretLikeStrings(value, trail = []) {
  if (typeof value === 'string') {
    if (secretLikeValue.test(value)) throw new Error(`Checkpoint contains a secret-like value at ${trail.join('.') || '<root>'}.`);
    return;
  }
  if (Array.isArray(value)) {
    value.forEach((child, index) => assertNoSecretLikeStrings(child, [...trail, String(index)]));
    return;
  }
  if (isPlainObject(value)) {
    for (const [key, child] of Object.entries(value)) assertNoSecretLikeStrings(child, [...trail, key]);
  }
}

function assertDigest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function assertRelativePath(value, label) {
  if (typeof value !== 'string' || value.length === 0 || value.startsWith('/') || /^[A-Za-z]:[\\/]/.test(value)) {
    throw new Error(`${label} must be relative; absolute paths are forbidden.`);
  }
}

function validateIntent(intent) {
  if (!isPlainObject(intent) || !['plan', 'direct'].includes(intent.kind)) throw new Error('Intent kind must be plan or direct.');
  assertAllowedKeys(intent, intent.kind === 'direct'
    ? new Set([
        'kind', 'digest', 'acceptance', 'scope', 'non_goals', 'justification',
        'review_cadence', 'user_visible', 'user_invocation_evidence',
        'risks',
      ])
    : new Set(['kind', 'digest']), 'Intent');
  assertDigest(intent.digest, 'Intent digest');
  if (intent.kind === 'direct') {
    if (Array.isArray(intent.triggers) && intent.triggers.length > 0) throw new Error('Direct intent has a Plan trigger.');
    for (const field of ['acceptance', 'scope', 'non_goals']) {
      if (!Array.isArray(intent[field])) throw new Error(`Direct intent requires ${field}.`);
    }
    if (!intent.acceptance.length || !intent.scope.length || typeof intent.justification !== 'string' || !intent.justification.trim()) {
      throw new Error('Direct intent requires bounded acceptance, scope, and Plan-bypass justification.');
    }
    if (!Array.isArray(intent.risks) || intent.risks.some((risk) => typeof risk !== 'string' || risk.length > 80)) {
      throw new Error('Direct intent risk disposition is invalid.');
    }
    if (!reviewCadences.has(intent.review_cadence)) throw new Error('Direct intent review cadence is invalid.');
    if (intent.user_invocation_evidence !== 'explicit-hard-eng-state-start') {
      throw new Error('Direct intent requires bounded user-invocation evidence.');
    }
  }
}

function validTimestamp(value) {
  return typeof value === 'string' && !Number.isNaN(Date.parse(value));
}

function validateLease(run) {
  const lease = run.lease;
  if (!isPlainObject(lease)) throw new Error('Run lease is required.');
  assertAllowedKeys(lease, new Set([
    'task_hash', 'checkout_id', 'heartbeat_at', 'expires_at', 'reconciliation', 'takeover',
  ]), 'Lease');
  assertDigest(lease.task_hash, 'Lease task hash');
  assertDigest(lease.checkout_id, 'Lease checkout ID');
  if (lease.checkout_id !== run.checkout_id) throw new Error('Lease checkout does not match the run checkout.');
  if (!validTimestamp(lease.heartbeat_at) || !validTimestamp(lease.expires_at)) throw new Error('Lease timestamps are invalid.');
  if (!['clean', 'released'].includes(lease.reconciliation)) throw new Error('Lease reconciliation state is invalid.');
  if (run.phase === 'Complete' ? lease.reconciliation !== 'released' : lease.reconciliation !== 'clean') {
    throw new Error('Lease reconciliation does not match the lifecycle phase.');
  }
  if (lease.takeover !== undefined && lease.takeover !== null) {
    assertAllowedKeys(lease.takeover, new Set([
      'approver_kind', 'approved_revision', 'previous_task_hash', 'approved_at',
    ]), 'Lease takeover');
    if (lease.takeover.approver_kind !== 'user' || !Number.isInteger(lease.takeover.approved_revision) || lease.takeover.approved_revision < 1) {
      throw new Error('Lease takeover approval is invalid.');
    }
    assertDigest(lease.takeover.previous_task_hash, 'Lease takeover previous task hash');
    if (!validTimestamp(lease.takeover.approved_at)) throw new Error('Lease takeover timestamp is invalid.');
  }
}

function validatePlanCheckpoint(plan) {
  if (!isPlainObject(plan)) throw new Error('Plan checkpoint must be typed.');
  assertAllowedKeys(plan, new Set([
    'path', 'digest', 'sections', 'slice_ids', 'acceptance_ids', 'ui',
    'acceptance_revision', 'approver_kind', 'accepted_at',
  ]), 'Plan checkpoint');
  assertRelativePath(plan.path, 'Plan checkpoint path');
  if (plan.path !== 'plan.md') throw new Error('Plan checkpoint path must be plan.md.');
  assertDigest(plan.digest, 'Plan digest');
  if (!isPlainObject(plan.sections) || !isPlainObject(plan.ui)) throw new Error('Plan section and UI summaries must be typed.');
  const sectionIds = Object.keys(plan.sections);
  if (sectionIds.length !== 11 || sectionIds.some((id, index) => id !== String(index + 1))) {
    throw new Error('Plan checkpoint must contain exactly eleven ordered section summaries.');
  }
  for (const [id, section] of Object.entries(plan.sections)) {
    if (!isPlainObject(section)) throw new Error(`Plan section ${id} summary is invalid.`);
    assertAllowedKeys(section, new Set(['heading', 'line', 'digest']), `Plan section ${id}`);
    if (typeof section.heading !== 'string' || !section.heading.trim() || section.heading.length > 160 || !Number.isInteger(section.line) || section.line < 1) {
      throw new Error(`Plan section ${id} summary is invalid.`);
    }
    assertDigest(section.digest, `Plan section ${id} digest`);
  }
  if (!Array.isArray(plan.slice_ids) || plan.slice_ids.length === 0) throw new Error('Plan checkpoint requires slices.');
  plan.slice_ids.forEach((id, index) => {
    if (id !== `S${index + 1}`) throw new Error('Plan checkpoint slice IDs must be contiguous.');
  });
  if (!Array.isArray(plan.acceptance_ids) || plan.acceptance_ids.length === 0 || plan.acceptance_ids.some((id) => !/^P\d+$/.test(id))) {
    throw new Error('Plan checkpoint acceptance IDs are invalid.');
  }
  if (new Set(plan.acceptance_ids).size !== plan.acceptance_ids.length) throw new Error('Plan checkpoint acceptance IDs must be unique.');
  if (plan.ui.applicable === false) {
    assertAllowedKeys(plan.ui, new Set(['applicable', 'reason']), 'Plan UI summary');
    if (typeof plan.ui.reason !== 'string' || !plan.ui.reason.trim() || plan.ui.reason.length > 500) {
      throw new Error('Plan UI not-applicable summary requires a bounded reason.');
    }
  } else if (plan.ui.applicable === true) {
    assertAllowedKeys(plan.ui, new Set([
      'applicable', 'baseline', 'design_owner', 'exploration', 'prototype', 'direction',
      'direction_boards', 'states', 'cadence', 'coded_options',
    ]), 'Plan UI summary');
    if (!isPlainObject(plan.ui.baseline) || !isPlainObject(plan.ui.prototype)) throw new Error('Plan UI artifact summaries are invalid.');
    if (!['existing-system', 'imagegen', 'constrained'].includes(plan.ui.exploration)) throw new Error('Plan UI exploration is invalid.');
    if (!reviewCadences.has(plan.ui.cadence)) throw new Error('Plan UI review cadence is invalid.');
    for (const field of ['design_owner', 'direction', 'coded_options']) {
      if (typeof plan.ui[field] !== 'string' || !plan.ui[field].trim() || plan.ui[field].length > 500) throw new Error(`Plan UI ${field} is invalid.`);
    }
    if (!Array.isArray(plan.ui.states) || !Array.isArray(plan.ui.direction_boards)) throw new Error('Plan UI state/direction summaries are invalid.');
    for (const state of ['happy', 'loading', 'empty', 'validation', 'permission', 'error']) {
      if (!plan.ui.states.includes(state)) throw new Error(`Plan UI summary is missing ${state}.`);
    }
  } else {
    throw new Error('Plan UI applicability is invalid.');
  }
  if (!Number.isInteger(plan.acceptance_revision) || plan.acceptance_revision < 1 || plan.approver_kind !== 'user' || !validTimestamp(plan.accepted_at)) {
    throw new Error('Plan checkpoint acceptance proof is invalid.');
  }
}

function validateNext(run) {
  if (!isPlainObject(run.next)) throw new Error('Next-action contract is required.');
  assertAllowedKeys(run.next, new Set(['owner', 'action']), 'Next action');
  const expected = nextFor(run.phase, run.cursor);
  if (run.next.owner !== expected.owner || run.next.action !== expected.action) {
    throw new Error('Next-action contract does not match the lifecycle cursor.');
  }
}

function validateCursor(run) {
  const cursor = run.cursor;
  let allowed = new Set(['step']);
  if (run.phase === 'Build') {
    if (cursor.step === 'learn') allowed = new Set(['step', 'finding_id', 'return_boundary']);
    else if (cursor.step === 'await-user-review') {
      allowed = new Set(['step', 'slice', 'return_step', 'candidate_fingerprint', 'visual_proof_id']);
    } else if (['implement', 'verify'].includes(cursor.step)) {
      allowed = new Set(['step', 'slice', 'candidate_fingerprint', 'repair']);
    } else {
      allowed = new Set(['step', 'slice', 'candidate_fingerprint']);
    }
  } else if (run.phase === 'Ship' && cursor.step === 'learn') {
    allowed = new Set(['step', 'finding_id', 'return_boundary']);
  }
  assertAllowedKeys(cursor, allowed, 'Cursor');
  if (run.phase === 'Build' && cursor.step !== 'learn') {
    if (!Number.isInteger(cursor.slice) || cursor.slice < 1) throw new Error('Build cursor slice is invalid.');
    if (cursor.candidate_fingerprint !== undefined) assertDigest(cursor.candidate_fingerprint, 'Build candidate fingerprint');
  }
  if (cursor.repair !== undefined) {
    assertAllowedKeys(cursor.repair, new Set(['hypothesis_digest', 'attempts', 'last_failure_fingerprint']), 'Repair cursor');
    assertDigest(cursor.repair.hypothesis_digest, 'Repair hypothesis digest');
    assertDigest(cursor.repair.last_failure_fingerprint, 'Repair failure fingerprint');
    if (![1, 2].includes(cursor.repair.attempts)) throw new Error('Repair attempt count is invalid.');
  }
}

function validateInterruption(interruption, candidate) {
  if (interruption === undefined || interruption === null) return;
  if (!isPlainObject(interruption)) throw new Error('Interruption record must be typed.');
  assertAllowedKeys(interruption, new Set([
    'intent', 'precondition_fingerprint', 'idempotency_key', 'observed_result',
    'reconciliation_command', 'prepared_at', 'publication_preflight',
  ]), 'Interruption');
  for (const field of ['intent', 'precondition_fingerprint', 'idempotency_key', 'observed_result', 'reconciliation_command', 'prepared_at']) {
    if (interruption[field] === undefined || interruption[field] === null || interruption[field] === '') {
      throw new Error(`Interruption record requires ${field}.`);
    }
  }
  for (const field of ['intent', 'observed_result', 'reconciliation_command']) {
    if (typeof interruption[field] !== 'string' || interruption[field].length > 240) throw new Error(`Interruption ${field} must be bounded.`);
  }
  if (/[\r\n;&|`$<>]/.test(interruption.reconciliation_command)) {
    throw new Error('Interruption reconciliation command must be one simple read-only invocation.');
  }
  assertDigest(interruption.precondition_fingerprint, 'Interruption precondition fingerprint');
  assertDigest(interruption.idempotency_key, 'Interruption idempotency key');
  if (!validTimestamp(interruption.prepared_at)) throw new Error('Interruption prepared timestamp is invalid.');
  if (interruption.intent === 'publish') {
    validatePublicationPreflight(interruption.publication_preflight, candidate);
  } else if (interruption.publication_preflight !== undefined) {
    throw new Error('Only a publication interruption may contain publication preparation evidence.');
  }
}

export function validateSupportReceipt(receipt) {
  if (!isPlainObject(receipt)) throw new Error('Support-tool receipt must be typed.');
  const allowed = new Set([
    'tool', 'operation', 'status', 'evidence_digest', 'reason_code', 'fallback_reason', 'recorded_at',
    'runtime_observed',
  ]);
  assertAllowedKeys(receipt, allowed, 'Support-tool receipt');
  if (!['codebase-memory', 'context-mode'].includes(receipt.tool)) throw new Error('Support-tool receipt has an unknown tool.');
  if (receipt.runtime_observed !== true) throw new Error('Support-tool receipt must be runtime-observed by Hard Eng.');
  const operations = receipt.tool === 'codebase-memory'
    ? new Set([
        'list_projects', 'index_repository', 'search_graph', 'trace_path',
        'detect_changes', 'get_architecture',
      ])
    : new Set(['search', 'not-applicable']);
  if (!['pass', 'not-applicable', 'fallback'].includes(receipt.status)) throw new Error('Support-tool receipt status is invalid.');
  if (receipt.tool === 'codebase-memory' && receipt.status === 'not-applicable') {
    throw new Error('Codebase Memory is mandatory for every Hard Eng run and cannot be marked not-applicable.');
  }
  if (!operations.has(receipt.operation)) throw new Error('Support-tool receipt operation is invalid.');
  if (receipt.status === 'pass') {
    assertDigest(receipt.evidence_digest, 'Support-tool evidence digest');
    if (receipt.reason_code !== undefined || receipt.fallback_reason !== undefined) {
      throw new Error('Passing support-tool receipts cannot carry fallback fields.');
    }
  } else if (receipt.status === 'fallback') {
    assertDigest(receipt.evidence_digest, 'Support-tool failure evidence digest');
    if (typeof receipt.fallback_reason !== 'string' || !receipt.fallback_reason.trim() || receipt.fallback_reason.length > 240) {
      throw new Error('Support-tool fallback requires a bounded reason.');
    }
    if (receipt.reason_code !== undefined) throw new Error('Fallback support-tool receipts cannot carry a not-applicable reason code.');
  } else if (receipt.tool !== 'context-mode' || receipt.operation !== 'not-applicable' || receipt.reason_code !== 'no-large-output') {
    throw new Error('Context Mode not-applicable requires the exact no-large-output reason code.');
  } else if (receipt.evidence_digest !== undefined || receipt.fallback_reason !== undefined) {
    throw new Error('Not-applicable Context Mode receipts cannot carry evidence or fallback fields.');
  }
  if (!validTimestamp(receipt.recorded_at)) throw new Error('Support-tool receipt timestamp is required.');
  return true;
}

export function validateRun(run) {
  if (!isPlainObject(run) || run.schema !== RUN_SCHEMA) throw new Error(`Run schema must be ${RUN_SCHEMA}.`);
  assertAllowedKeys(run, runKeys, 'Run');
  // Reject raw identity and secret material before nested schema validation so
  // an attacker cannot disguise a forbidden field as an ordinary shape error.
  assertNoRawIdentityKeys(run);
  assertNoSecretLikeStrings(run);
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(run.run_id ?? '')) throw new Error('Run ID is invalid.');
  assertDigest(run.repo_id, 'Repository ID');
  assertDigest(run.checkout_id, 'Checkout ID');
  if (typeof run.objective !== 'string' || !run.objective.trim() || run.objective.length > 240) {
    throw new Error('Objective must be present and at most 240 characters.');
  }
  validateIntent(run.intent);
  if (!phases.has(run.phase)) throw new Error('Run phase is invalid.');
  if (!isPlainObject(run.cursor) || !cursorSteps[run.phase]?.has(run.cursor.step)) {
    throw new Error(`Cursor ${run.cursor?.step ?? '<missing>'} is invalid for phase ${run.phase}.`);
  }
  validateCursor(run);
  validateLease(run);
  if (run.plan) validatePlanCheckpoint(run.plan);
  if (run.candidate) validateCandidate(run.candidate);
  if (!Array.isArray(run.proof) || !Array.isArray(run.findings)) throw new Error('Proof and findings must be arrays.');
  for (const proof of run.proof) validateProof(proof);
  for (const finding of run.findings) validateFinding(finding);
  if (!Array.isArray(run.support_tools) || run.support_tools.length > 16) throw new Error('Support-tool receipt ledger is invalid.');
  for (const receipt of run.support_tools) validateSupportReceipt(receipt);
  validateInterruption(run.interruption, run.candidate);
  validateNext(run);
  if (Object.keys(run.publication).length > 0) {
    validatePublication(run.publication, run.candidate, { requireApproval: run.phase === 'Complete' });
  }
  if (!Number.isInteger(run.revision) || run.revision < 1) throw new Error('Revision must be a positive integer.');
  assertNoAbsolutePaths(run);
  const size = Buffer.byteLength(canonicalJson(run));
  if (size >= MAX_RUN_BYTES) throw new Error(`Checkpoint exceeds the 64 KiB limit (${size} bytes).`);
  return true;
}

export function validateSession(session) {
  if (!isPlainObject(session) || session.schema !== SESSION_SCHEMA) throw new Error(`Session schema must be ${SESSION_SCHEMA}.`);
  assertAllowedKeys(session, sessionKeys, 'Session');
  assertDigest(session.repo_id, 'Session repository ID');
  assertDigest(session.task_hash, 'Session task hash');
  if (session.run_id !== null && !/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(session.run_id ?? '')) {
    throw new Error('Session run ID is invalid.');
  }
  if (!Array.isArray(session.replays) || session.replays.length > 16) throw new Error('Session replay ledger is invalid.');
  assertNoAbsolutePaths(session);
  assertNoRawIdentityKeys(session);
  assertNoSecretLikeStrings(session);
  if (Buffer.byteLength(canonicalJson(session)) >= 32 * 1024) throw new Error('Session binding exceeds 32 KiB.');
  return true;
}

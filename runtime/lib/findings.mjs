import { clone } from './canonical.mjs';

const admissionReasons = new Set(['repeated', 'escaped-defect', 'critical', 'high-leverage']);
const severities = new Set(['critical', 'high', 'medium', 'low']);
const actions = new Set(['auto-fix', 'ask-user', 'manual', 'informational']);
const guardOwners = new Set(['test', 'linter', 'scanner', 'schema', 'ci', 'documentation', 'skill-reference']);

function digest(value, label) {
  if (!/^[a-f0-9]{64}$/i.test(value ?? '')) throw new Error(`${label} must be a SHA-256 digest.`);
}

function assertKeys(value, allowed, label) {
  for (const key of Object.keys(value)) if (!allowed.has(key)) throw new Error(`${label} contains unknown field ${key}.`);
}

export function validateFinding(finding) {
  if (!finding || typeof finding !== 'object') throw new Error('Finding provenance is required.');
  assertKeys(finding, new Set([
    'id', 'fingerprint', 'severity', 'action', 'source_stage', 'source', 'occurrences',
    'occurrence_evidence', 'affected_owner', 'immediate_repair', 'admission_reason',
    'proposed_guard', 'admission', 'return_boundary', 'guard',
  ]), 'Finding');
  const required = [
    'id', 'fingerprint', 'severity', 'action', 'source_stage', 'source', 'occurrences',
    'occurrence_evidence', 'affected_owner', 'immediate_repair', 'admission_reason', 'proposed_guard',
  ];
  for (const field of required) {
    if (finding[field] === undefined || finding[field] === null || finding[field] === '') {
      throw new Error(`Finding provenance is missing ${field}.`);
    }
  }
  if (!/^[a-zA-Z0-9][a-zA-Z0-9._-]{2,80}$/.test(finding.id)) throw new Error('Finding ID is invalid.');
  if (!finding.source.kind || !finding.source.reference) throw new Error('Finding provenance requires a typed source.');
  assertKeys(finding.source, new Set(['kind', 'reference']), 'Finding source');
  digest(finding.fingerprint, 'Finding fingerprint');
  if (!severities.has(finding.severity)) throw new Error('Finding severity is unsupported.');
  if (!actions.has(finding.action)) throw new Error('Finding action is unsupported.');
  if (!Number.isInteger(finding.occurrences) || finding.occurrences < 1) throw new Error('Finding occurrence count is invalid.');
  if (!Array.isArray(finding.occurrence_evidence) || finding.occurrence_evidence.length < finding.occurrences) {
    throw new Error('Finding occurrence evidence does not prove every occurrence.');
  }
  finding.occurrence_evidence.forEach((value) => digest(value, 'Finding occurrence evidence'));
  if (!admissionReasons.has(finding.admission_reason)) throw new Error('Finding admission reason is unsupported.');
  if (finding.admission_reason === 'repeated' && finding.occurrences < 2) {
    throw new Error('Repeated finding admission requires at least two occurrences.');
  }
  if (finding.admission !== undefined && !['open', 'closed'].includes(finding.admission)) throw new Error('Finding admission is invalid.');
  if (finding.guard !== undefined && finding.guard !== null) validateGuard(finding.guard);
  return true;
}

export function validateGuard(guard) {
  if (!guard || typeof guard !== 'object' || Array.isArray(guard)) throw new Error('Learn guard proof is required.');
  assertKeys(guard, new Set([
    'owner_kind', 'owner', 'bad_fixture_digest', 'fail_before', 'pass_after',
    'consolidated_rules', 'result', 'tree_changed', 'proven_at',
  ]), 'Learn guard');
  if (!guardOwners.has(guard.owner_kind)) throw new Error('Learn guard owner is invalid.');
  if (typeof guard.owner !== 'string' || !guard.owner.trim() || guard.owner.length > 240) throw new Error('Learn guard owner is invalid.');
  digest(guard.bad_fixture_digest, 'Learn bad fixture digest');
  if (!guard.fail_before || guard.fail_before.result !== 'fail-expected') throw new Error('Learn guard requires fail-before proof.');
  if (!guard.pass_after || guard.pass_after.result !== 'pass') throw new Error('Learn guard requires pass-after proof.');
  assertKeys(guard.fail_before, new Set(['evidence_digest', 'result']), 'Learn fail-before proof');
  assertKeys(guard.pass_after, new Set(['evidence_digest', 'result', 'candidate_fingerprint']), 'Learn pass-after proof');
  digest(guard.fail_before.evidence_digest, 'Learn fail-before evidence');
  digest(guard.pass_after.evidence_digest, 'Learn pass-after evidence');
  digest(guard.pass_after.candidate_fingerprint, 'Learn repaired candidate fingerprint');
  if (!Array.isArray(guard.consolidated_rules)) throw new Error('Learn guard must record stale-rule consolidation.');
  if (guard.result !== undefined && guard.result !== 'proven') throw new Error('Learn guard result is invalid.');
  if (guard.tree_changed !== undefined && typeof guard.tree_changed !== 'boolean') throw new Error('Learn guard tree-change flag is invalid.');
  return true;
}

export function admitFinding(finding, returnBoundary) {
  validateFinding(finding);
  return {
    ...clone(finding),
    admission: 'open',
    return_boundary: clone(returnBoundary),
    guard: null,
  };
}

export function findingCounts(findings = []) {
  return {
    blocking: findings.filter((finding) => finding.admission === 'open').length,
    admitted: findings.filter((finding) => finding.admission === 'open').length,
  };
}

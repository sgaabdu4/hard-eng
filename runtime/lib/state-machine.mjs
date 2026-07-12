import { randomId } from './crypto.mjs';
import { clone } from './canonical.mjs';
import { admitFinding, validateGuard } from './findings.mjs';
import { nextFor } from './lifecycle.mjs';
import { markAllProofStale } from './proof.mjs';
import { RUN_SCHEMA, validateRun, validateSupportReceipt } from './schema.mjs';
import { validatePublicationPreflight } from './ship.mjs';
import { validateDirectContract } from './route.mjs';
import { applyPlanEvent } from './state-plan.mjs';
import { applyBuildEvent } from './state-build.mjs';
import { applyShipEvent } from './state-ship.mjs';
import { assertDigest, transitionError } from './state-transition.mjs';

const directIntentKeys = new Set([
  'kind', 'digest', 'acceptance', 'scope', 'non_goals', 'justification',
  'review_cadence', 'user_visible', 'risks',
]);

function iso(value) {
  return typeof value === 'string' ? value : new Date(value ?? Date.now()).toISOString();
}

export function createInitialRun({ repoId, checkoutId, taskHash, objective, intent, now, runId }) {
  const timestamp = iso(now);
  if (intent?.kind === 'direct' && Array.isArray(intent.triggers) && intent.triggers.length > 0) {
    throw new Error('Direct intent has a Plan trigger.');
  }
  if (intent?.kind === 'direct') {
    for (const key of Object.keys(intent)) {
      if (!directIntentKeys.has(key)) throw new Error(`Direct intent contains an unknown or Plan-only field: ${key}.`);
    }
  }
  const normalizedIntent = intent?.kind === 'direct'
    ? {
        kind: 'direct',
        digest: intent.digest,
        acceptance: clone(intent.acceptance),
        scope: clone(intent.scope),
        non_goals: clone(intent.non_goals),
        justification: intent.justification,
        review_cadence: intent.review_cadence ?? 'final-candidate',
        user_visible: intent.user_visible === true,
        risks: clone(intent.risks ?? []),
        user_invocation_evidence: 'explicit-hard-eng-state-start',
      }
    : { kind: intent?.kind, digest: intent?.digest };
  const phase = normalizedIntent?.kind === 'direct' ? 'Build' : 'Plan';
  if (phase === 'Build') validateDirectContract({ objective: String(objective ?? '').trim(), ...normalizedIntent });
  const cursor = phase === 'Build' ? { step: 'red', slice: 1 } : { step: 'discover' };
  const run = {
    schema: RUN_SCHEMA,
    run_id: runId ?? randomId('he'),
    repo_id: repoId,
    checkout_id: checkoutId,
    lease: {
      task_hash: taskHash,
      checkout_id: checkoutId,
      heartbeat_at: timestamp,
      expires_at: new Date(Date.parse(timestamp) + 30 * 60_000).toISOString(),
      reconciliation: 'clean',
    },
    objective: String(objective ?? '').trim(),
    intent: normalizedIntent,
    phase,
    cursor,
    plan: null,
    candidate: null,
    proof: [],
    findings: [],
    support_tools: [],
    publication: {},
    next: nextFor(phase, cursor),
    revision: 1,
    created_at: timestamp,
    updated_at: timestamp,
  };
  validateRun(run);
  return run;
}

function finish(run, timestamp) {
  run.updated_at = timestamp;
  run.next = nextFor(run.phase, run.cursor);
  validateRun(run);
  return run;
}

function applyFinding(run, event, timestamp) {
  if (!['Build', 'Ship'].includes(run.phase) || run.cursor.step === 'learn') transitionError(run, event);
  const returnBoundary = { phase: run.phase, cursor: clone(run.cursor) };
  const finding = admitFinding(event.finding, returnBoundary);
  if (finding.source_stage !== run.phase) throw new Error('Finding source stage does not match the current lifecycle phase.');
  run.findings.push(finding);
  run.cursor = { step: 'learn', finding_id: finding.id, return_boundary: returnBoundary };
  return finish(run, timestamp);
}

function applyLearn(run, event, timestamp) {
  if (run.cursor.step !== 'learn') transitionError(run, event);
  const finding = run.findings.find((item) => item.id === event.finding_id && item.admission === 'open');
  if (!finding) throw new Error('Admitted finding is not open.');
  validateGuard(event.guard);
  finding.admission = 'closed';
  finding.guard = {
    ...clone(event.guard),
    result: 'proven',
    tree_changed: Boolean(event.tree_changed),
    proven_at: timestamp,
  };
  if (event.tree_changed) {
    markAllProofStale(run);
    run.phase = 'Build';
    run.cursor = {
      step: 'verify',
      slice: finding.return_boundary.cursor.slice ?? 1,
      candidate_fingerprint: event.guard.pass_after.candidate_fingerprint,
    };
    run.candidate = null;
    run.proof = [];
  } else {
    run.phase = finding.return_boundary.phase;
    run.cursor = clone(finding.return_boundary.cursor);
  }
  return finish(run, timestamp);
}

function prepareExternalAction(run, event, timestamp) {
  if (run.interruption) throw new Error('An external action is already pending reconciliation.');
  const action = event.action;
  if (action?.intent === 'publish') {
    if (
      run.phase !== 'Ship'
      || run.cursor.step !== 'publish'
      || action.precondition_fingerprint !== run.candidate?.fingerprint
    ) throw new Error('Publication external-action precondition does not match the approved candidate.');
    validatePublicationPreflight(action.publication_preflight, run.candidate, {
      mode: action.publication?.mode,
      remoteRef: action.publication?.remote_ref,
      prNumber: action.publication?.pr_number,
      commit: action.publication?.commit,
    });
  } else if (action?.publication !== undefined || action?.publication_preflight !== undefined) {
    throw new Error('Only a publication action may contain publication preparation evidence.');
  }
  run.interruption = {
    intent: action?.intent,
    precondition_fingerprint: action?.precondition_fingerprint,
    idempotency_key: action?.idempotency_key,
    observed_result: 'not-observed',
    reconciliation_command: action?.reconciliation_command,
    prepared_at: timestamp,
    ...(action?.intent === 'publish' ? {
      publication_preflight: clone(action.publication_preflight),
    } : {}),
  };
}

function reconcileNotApplied(run, event) {
  if (!run.interruption || event.idempotency_key !== run.interruption.idempotency_key) {
    throw new Error('External action reconciliation identity does not match.');
  }
  if (typeof event.observed_result !== 'string' || !event.observed_result.trim() || event.observed_result.length > 240) {
    throw new Error('External action reconciliation requires a bounded observed result.');
  }
  assertDigest(event.evidence_digest, 'External action reconciliation evidence');
  run.interruption = null;
}

function recordSupport(run, event, timestamp) {
  const receipt = { ...clone(event.receipt), recorded_at: event.receipt?.recorded_at ?? timestamp };
  validateSupportReceipt(receipt);
  run.support_tools = [...run.support_tools, receipt].slice(-16);
}

function validateQuestionIds(value) {
  if (
    !Array.isArray(value)
    || value.length < 1
    || value.length > 3
    || new Set(value).size !== value.length
    || value.some((id) => !/^[a-z0-9][a-z0-9._-]{1,63}$/.test(id))
  ) throw new Error('Clarification requires one to three unique bounded question IDs.');
}

function requireClarification(run, event, timestamp) {
  if (run.cursor.step === 'await-user-clarification') {
    throw new Error('Run is already in a clarification hold.');
  }
  if (!/^[a-z0-9][a-z0-9-]{1,63}$/.test(event.reason_code ?? '')) {
    throw new Error('Clarification reason code is invalid.');
  }
  validateQuestionIds(event.question_ids);
  assertDigest(event.conflict_digest, 'Clarification conflict digest');
  assertDigest(event.candidate_fingerprint, 'Clarification candidate fingerprint');
  const planDigest = run.plan?.digest ?? null;
  if (!Object.hasOwn(event, 'plan_digest') || event.plan_digest !== planDigest) {
    throw new Error('Clarification plan digest does not match the current boundary.');
  }
  const returnBoundary = { phase: run.phase, cursor: clone(run.cursor) };
  run.cursor = {
    step: 'await-user-clarification',
    reason_code: event.reason_code,
    question_ids: clone(event.question_ids),
    conflict_digest: event.conflict_digest,
    plan_digest: planDigest,
    candidate_fingerprint: event.candidate_fingerprint,
    source_revision: run.revision,
    return_boundary: returnBoundary,
  };
  return finish(run, timestamp);
}

function answerClarification(run, event, timestamp) {
  if (run.cursor.step !== 'await-user-clarification') transitionError(run, event);
  if (event.approver !== 'user') throw new Error('Clarification requires an explicit user answer.');
  assertDigest(event.answer_digest, 'Clarification answer digest');
  validateQuestionIds(event.question_ids);
  if (JSON.stringify(event.question_ids) !== JSON.stringify(run.cursor.question_ids)) {
    throw new Error('Clarification question identity does not match the hold.');
  }
  if (
    !Object.hasOwn(event, 'plan_digest')
    || event.plan_digest !== run.cursor.plan_digest
    || event.candidate_fingerprint !== run.cursor.candidate_fingerprint
  ) throw new Error('Clarification answer does not reconcile the held plan and candidate.');
  const boundary = clone(run.cursor.return_boundary);
  run.phase = boundary.phase;
  run.cursor = boundary.cursor;
  return finish(run, timestamp);
}

export function applyEvent(source, event) {
  const run = clone(source);
  const timestamp = iso(event?.at);
  if (!event?.type) throw new Error('Typed event is required.');
  if (run.phase === 'Complete') throw new Error('Complete runs are immutable.');
  if (run.cursor.step === 'await-user-clarification' && event.type !== 'clarification.answered') {
    throw new Error('Run is in a clarification hold; candidate and lifecycle mutation are blocked.');
  }

  if (event.type === 'clarification.required') return requireClarification(run, event, timestamp);
  if (event.type === 'clarification.answered') return answerClarification(run, event, timestamp);
  if (event.type === 'external-action.prepared') prepareExternalAction(run, event, timestamp);
  else if (event.type === 'external-action.not-applied') reconcileNotApplied(run, event);
  else if (event.type === 'support.recorded') recordSupport(run, event, timestamp);
  else if (event.type === 'finding.admitted') return applyFinding(run, event, timestamp);
  else if (event.type === 'learn.guard-proven') return applyLearn(run, event, timestamp);
  else if (run.phase === 'Plan') applyPlanEvent(run, event, timestamp);
  else if (run.phase === 'Build') applyBuildEvent(run, event, timestamp);
  else if (run.phase === 'Ship') applyShipEvent(run, event, timestamp);
  else transitionError(run, event);

  return finish(run, timestamp);
}

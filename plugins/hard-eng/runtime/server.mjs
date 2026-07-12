#!/usr/bin/env node
import readline from 'node:readline';
import { pathToFileURL } from 'node:url';
import { applyEvent, createInitialRun } from './lib/state-machine.mjs';
import { fingerprintCandidate, fingerprintCommitTree } from './lib/candidate.mjs';
import { verifyCheckReceipt } from './lib/check-receipt.mjs';
import { validateVisualEvidence } from './lib/evidence.mjs';
import { renderCapsule } from './lib/capsule.mjs';
import { peekEnvelope, replayKey, verifyEnvelope } from './lib/envelope.mjs';
import { validatePlanFile } from './lib/plan.mjs';
import {
  createRun,
  listRuns,
  readKey,
  readRun,
  readSession,
  resolveStore,
  storeFromRoot,
  updateRun,
  withLock,
  writeSession,
} from './lib/store.mjs';
import { SESSION_SCHEMA } from './lib/schema.mjs';
import { git } from './lib/git.mjs';
import { redactErrorMessage } from './lib/redact.mjs';
import {
  observePublicationPreparation,
  observeRemotePublication,
} from './lib/publication-observer.mjs';
import { observeSupportReceipt } from './lib/support-observer.mjs';

const ACTIONS = ['start', 'status', 'resume', 'event'];

export const toolDefinition = {
  name: 'state',
  description: 'Start, inspect, resume, or advance one exact Hard Eng run. State is local to the Git worktree family. Use only typed actions; never invent lifecycle transitions.',
  inputSchema: {
    type: 'object',
    additionalProperties: false,
    required: ['action'],
    properties: {
      action: { type: 'string', enum: ACTIONS },
      payload: { type: 'object', additionalProperties: true },
      _he: { type: 'object', description: 'Reserved signed binding envelope. Do not set or modify this field.' },
    },
  },
};

function newSession(payload, runId, now) {
  return {
    schema: SESSION_SCHEMA,
    repo_id: payload.repo_id,
    task_hash: payload.task_hash,
    run_id: runId,
    binding_revision: 1,
    revoked: false,
    pending: null,
    replays: [],
    updated_at: new Date(now).toISOString(),
  };
}

function resultFor(run) {
  const openFindings = run.findings.filter((finding) => finding.admission === 'open').length;
  return {
    status: 'bound',
    run_id: run.run_id,
    phase: run.phase,
    cursor: run.cursor,
    intent: { kind: run.intent.kind, digest: run.intent.digest },
    findings: { open: openFindings },
    next: run.next,
    revision: run.revision,
    capsule: renderCapsule(run),
    ...(run.interruption ? { interruption: {
      intent: run.interruption.intent,
      precondition_fingerprint: run.interruption.precondition_fingerprint,
      idempotency_key: run.interruption.idempotency_key,
      observed_result: run.interruption.observed_result,
      reconciliation_command: run.interruption.reconciliation_command,
      ...(run.interruption.publication_preflight ? {
        publication_preflight: run.interruption.publication_preflight,
      } : {}),
    } } : {}),
  };
}

function replayResult(session, key) {
  return session?.replays.find((entry) => entry.key === key)?.result ?? null;
}

function writePending(store, session, key, action, now) {
  const next = session ?? newSession({ repo_id: store.repoId, task_hash: key.taskHash }, null, now);
  if (next.pending) throw new Error('A pending Hard Eng action requires reconciliation.');
  next.pending = { key: key.value, action, started_at: new Date(now).toISOString() };
  next.updated_at = new Date(now).toISOString();
  writeSession(store, next);
  return next;
}

function completeSession(store, session, key, result, runId, now) {
  session.run_id = runId;
  session.pending = null;
  session.binding_revision += 1;
  session.updated_at = new Date(now).toISOString();
  session.replays = [...session.replays, { key, result }].slice(-16);
  writeSession(store, session);
}

function clearPending(store, session, now) {
  if (!session) return;
  session.pending = null;
  session.updated_at = new Date(now).toISOString();
  writeSession(store, session);
}

function startRun(store, verified, args, now) {
  const existing = listRuns(store).find((run) => run.phase !== 'Complete' && run.checkout_id === verified.checkout_id);
  if (existing) throw new Error('This checkout already has a non-complete Hard Eng writer run.');
  const run = createInitialRun({
    repoId: verified.repo_id,
    checkoutId: verified.checkout_id,
    taskHash: verified.task_hash,
    objective: args.payload?.objective,
    intent: args.payload?.intent,
    now,
  });
  createRun(store, run);
  return run;
}

function resumeRun(store, verified, args, now) {
  const runId = args.payload?.run_id;
  const expected = args.payload?.expected_revision;
  const current = readRun(store, runId);
  if (!current || current.phase === 'Complete') throw new Error('Requested run is unavailable or complete.');
  if (current.repo_id !== verified.repo_id) throw new Error('Requested run belongs to another repository family.');
  if (current.revision !== expected) throw new Error('Requested run revision is stale.');
  const changesTask = current.lease.task_hash !== verified.task_hash;
  const takeover = args.payload?.takeover;
  if (changesTask && !(
    takeover?.approved === true
    && takeover.approver === 'user'
    && takeover.approved_revision === expected
  )) {
    throw new Error('A different task owns this run; explicit user-approved takeover at the current revision is required.');
  }
  const previousTask = current.lease.task_hash;
  const resumed = updateRun(store, runId, expected, (run) => ({
    ...run,
    checkout_id: verified.checkout_id,
    lease: {
      ...run.lease,
      task_hash: verified.task_hash,
      checkout_id: verified.checkout_id,
      heartbeat_at: new Date(now).toISOString(),
      expires_at: new Date(now + 30 * 60_000).toISOString(),
      reconciliation: 'clean',
      takeover: changesTask ? {
        approver_kind: 'user',
        approved_revision: expected,
        previous_task_hash: previousTask,
        approved_at: new Date(now).toISOString(),
      } : run.lease.takeover ?? null,
    },
    updated_at: new Date(now).toISOString(),
  }));
  if (previousTask !== verified.task_hash) {
    const previousSession = readSession(store, previousTask);
    if (previousSession) {
      previousSession.revoked = true;
      previousSession.updated_at = new Date(now).toISOString();
      writeSession(store, previousSession);
    }
  }
  return resumed;
}

function applyRunEvent(store, verified, args, now, supportObserver) {
  const runId = args.payload?.run_id;
  const expected = args.payload?.expected_revision;
  const current = readRun(store, runId);
  if (!current) throw new Error('Bound run was not found.');
  if (current.lease.task_hash !== verified.task_hash) throw new Error('Bound task no longer owns the run lease.');
  if (current.plan && current.phase !== 'Plan') {
    const currentPlan = validatePlanFile(verified.checkout_root, { runId, requireAccepted: true });
    if (currentPlan.digest !== current.plan.digest) throw new Error('Accepted plan digest changed; Plan reconciliation is required.');
  }
  let event = args.payload?.event;
  if (event?.type === 'support.recorded') {
    event = { ...event, receipt: supportObserver(verified.checkout_root, event.receipt, { now }) };
  }
  if (event?.type === 'plan.ready-for-approval') {
    validatePlanFile(verified.checkout_root, { runId, requireAccepted: false });
  }
  if (event?.type === 'plan.accepted') {
    if (event.plan?.approver !== 'user') throw new Error('Plan acceptance requires explicit user approval.');
    const accepted = validatePlanFile(verified.checkout_root, { runId, requireAccepted: true });
    event = {
      ...event,
      plan: {
        path: 'plan.md',
        digest: accepted.digest,
        sections: accepted.sections,
        slice_ids: accepted.slice_ids,
        acceptance_ids: accepted.acceptance_ids,
        ui: accepted.ui,
        approver: 'user',
      },
    };
  }
  if (event?.type === 'external-action.prepared' && event.action?.intent === 'publish') {
    const publication = event.action.publication;
    const publicationPreflight = observePublicationPreparation(
      verified.checkout_root,
      publication,
      current.candidate,
    );
    event = {
      ...event,
      action: {
        ...event.action,
        publication_preflight: publicationPreflight,
      },
    };
  }
  if (current.phase === 'Build' && event?.type?.startsWith('build.')) {
    const currentCandidate = fingerprintCandidate(verified.checkout_root, { allowAllUntracked: true });
    if (['build.red-proven', 'build.verify-failed', 'build.verify-passed', 'build.review-passed'].includes(event.type)) {
      event = {
        ...event,
        proof: { ...event.proof, candidate_fingerprint: currentCandidate.fingerprint },
      };
    } else if (['build.implemented', 'build.all-slices-proven', 'build.candidate-drift'].includes(event.type)) {
      event = { ...event, candidate_fingerprint: currentCandidate.fingerprint };
    } else if (event.type === 'build.visual-milestone') {
      event = {
        ...event,
        evidence: { ...event.evidence, candidate_fingerprint: currentCandidate.fingerprint },
      };
      validateVisualEvidence(event.evidence, {
        repo: verified.checkout_root,
        runId,
        final: false,
        candidateFingerprint: currentCandidate.fingerprint,
      });
    }
  }
  if (event?.type === 'ship.candidate-green') {
    const receipt = verifyCheckReceipt(event.check_receipt, {
      key: readKey(store),
      run: current,
      repoId: verified.repo_id,
      checkoutId: verified.checkout_id,
      now,
    });
    const currentCandidate = fingerprintCandidate(verified.checkout_root, { allowAllUntracked: true });
    if (currentCandidate.fingerprint !== receipt.candidate.fingerprint) {
      throw new Error('Ship candidate changed after the signed check receipt; rerun the registry.');
    }
    if (current.plan?.ui?.applicable === true || current.intent.user_visible === true) {
      validateVisualEvidence(event.evidence, {
        repo: verified.checkout_root,
        runId,
        final: true,
        candidateFingerprint: receipt.candidate.fingerprint,
      });
    }
    event = {
      ...event,
      check_receipt: undefined,
      check: {
        registry_digest: receipt.registry_digest,
        results_digest: receipt.results_digest,
        preflight_digest: receipt.preflight_digest,
        candidate: receipt.candidate,
      },
    };
    delete event.check_receipt;
  }
  function verifyLocalPublication(publication) {
    const commit = git(verified.checkout_root, ['rev-parse', '--verify', `${publication?.commit}^{commit}`]).trim();
    if (commit !== publication.commit) throw new Error('Publication commit is not the exact local Git commit.');
    const tree = git(verified.checkout_root, ['rev-parse', `${commit}^{tree}`]).trim();
    if (tree !== publication.tree) throw new Error('Publication tree does not match the local Git commit.');
    const parents = git(verified.checkout_root, ['show', '-s', '--format=%P', commit]).trim().split(/\s+/).filter(Boolean);
    if (parents[0] !== publication.parent) throw new Error('Publication parent does not match the local Git commit.');
    if (fingerprintCommitTree(verified.checkout_root, commit) !== current.candidate?.tree_fingerprint) {
      throw new Error('Published Git tree does not match the approved candidate tree.');
    }
    return observeRemotePublication(verified.checkout_root, publication, {
      preflight: publication?.preflight ?? current.interruption?.publication_preflight,
    });
  }
  if (event?.type === 'ship.published-current') {
    event = { ...event, publication: verifyLocalPublication(event.publication) };
  }
  if (event?.type === 'ship.publication-approved') {
    const observed = verifyLocalPublication(current.publication);
    if (
      observed.remote_url_digest !== current.publication.remote_url_digest
      || observed.remote_observation_digest !== current.publication.remote_observation_digest
    ) throw new Error('Live origin observation changed after publication evidence was recorded.');
  }
  return updateRun(store, runId, expected, (run) => {
    const applied = applyEvent(run, { ...event, at: event?.at ?? new Date(now).toISOString() });
    return {
      ...applied,
      lease: {
        ...applied.lease,
        heartbeat_at: new Date(now).toISOString(),
        expires_at: new Date(now + 30 * 60_000).toISOString(),
      },
    };
  });
}

export function handleStateAction(args, { now = Date.now(), supportObserver = observeSupportReceipt } = {}) {
  if (!args || !ACTIONS.includes(args.action)) throw new Error('State action is invalid.');
  const untrusted = peekEnvelope(args._he);
  const store = storeFromRoot(untrusted.store_root);
  if (!store.exists) throw new Error('Hard Eng store is unavailable.');
  const key = readKey(store);
  const verified = verifyEnvelope(args._he, { key, action: args.action, args, now });
  if (verified.repo_id !== store.repoId) throw new Error('Envelope repository identity does not match the store.');
  const checkoutStore = resolveStore(verified.checkout_root, { create: false });
  if (
    checkoutStore.root !== store.root
    || checkoutStore.repoId !== verified.repo_id
    || checkoutStore.checkoutId !== verified.checkout_id
  ) throw new Error('Envelope checkout identity does not match the repository family.');

  const session = readSession(store, verified.task_hash);
  if (args.action === 'status') {
    if (!session || session.revoked || !session.run_id) return { status: 'unbound' };
    const run = readRun(store, session.run_id);
    return !run
      || run.phase === 'Complete'
      || run.repo_id !== verified.repo_id
      || run.checkout_id !== verified.checkout_id
      || run.lease.task_hash !== verified.task_hash
      || run.lease.checkout_id !== verified.checkout_id
      ? { status: 'unbound' }
      : resultFor(run);
  }

  const idempotency = replayKey(verified);
  const replay = replayResult(session, idempotency);
  if (replay) return replay;
  const lockId = `session-${verified.task_hash.slice(0, 32)}`;

  return withLock(store, lockId, { owner: verified.task_hash, action: args.action, time: new Date(now).toISOString() }, () => {
    const latestSession = readSession(store, verified.task_hash);
    const repeated = replayResult(latestSession, idempotency);
    if (repeated) return repeated;
    let pending = latestSession ?? newSession(verified, args.payload?.run_id ?? null, now);
    const runIdsBefore = args.action === 'start' ? new Set(listRuns(store).map((run) => run.run_id)) : null;
    const expectedRevision = args.payload?.expected_revision ?? null;
    pending = writePending(store, pending, { value: idempotency, taskHash: verified.task_hash }, args.action, now);
    try {
      let run;
      if (args.action === 'start') {
        if (latestSession?.run_id && !latestSession.revoked) throw new Error('This task is already bound to a run.');
        run = startRun(store, verified, args, now);
      } else if (args.action === 'resume') {
        run = resumeRun(store, verified, args, now);
      } else {
        if (!latestSession?.run_id || latestSession.revoked || latestSession.run_id !== args.payload?.run_id) {
          throw new Error('The task is not bound to the requested run.');
        }
        run = applyRunEvent(store, verified, args, now, supportObserver);
      }
      const result = resultFor(run);
      completeSession(store, pending, idempotency, result, run.run_id, now);
      return result;
    } catch (error) {
      const sideEffectObserved = args.action === 'start'
        ? listRuns(store).some((run) => !runIdsBefore.has(run.run_id))
        : (() => {
            const current = readRun(store, args.payload?.run_id);
            return current !== null && current.revision !== expectedRevision;
          })();
      if (!sideEffectObserved) clearPending(store, pending, now);
      throw error;
    }
  });
}

function response(id, result) {
  process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id, result })}\n`);
}

function errorResponse(id, error) {
  process.stdout.write(`${JSON.stringify({ jsonrpc: '2.0', id, error: { code: -32000, message: redactErrorMessage(error) } })}\n`);
}

function serve() {
  const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
  input.on('line', (line) => {
    if (!line.trim()) return;
    if (Buffer.byteLength(line) > 128 * 1024) {
      errorResponse(null, new Error('MCP request exceeds 128 KiB.'));
      return;
    }
    let message;
    try {
      message = JSON.parse(line);
    } catch {
      errorResponse(null, new Error('Invalid JSON-RPC request.'));
      return;
    }
    if (message.method === 'notifications/initialized') return;
    try {
      if (message.method === 'initialize') {
        response(message.id, {
          protocolVersion: message.params?.protocolVersion ?? '2024-11-05',
          capabilities: { tools: { listChanged: false } },
          serverInfo: { name: 'hard-eng', version: '1.0.0' },
        });
      } else if (message.method === 'tools/list') {
        response(message.id, { tools: [toolDefinition] });
      } else if (message.method === 'tools/call') {
        if (message.params?.name !== 'state') throw new Error('Unknown Hard Eng tool.');
        try {
          const result = handleStateAction(message.params.arguments);
          response(message.id, {
            content: [{ type: 'text', text: JSON.stringify(result) }],
            structuredContent: result,
            isError: false,
          });
        } catch (error) {
          response(message.id, {
            content: [{ type: 'text', text: redactErrorMessage(error) }],
            isError: true,
          });
        }
      } else if (message.id !== undefined) {
        throw new Error(`Unsupported MCP method: ${message.method}.`);
      }
    } catch (error) {
      errorResponse(message.id ?? null, error);
    }
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) serve();

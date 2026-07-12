import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeLinkedWorktree, makeRepo } from '../fixtures/repo-fixture.mjs';
import { handleHook } from '../../plugins/hard-eng/runtime/hook.mjs';
import { handleStateAction as baseHandleStateAction, toolDefinition } from '../../plugins/hard-eng/runtime/server.mjs';
import { peekEnvelope } from '../../plugins/hard-eng/runtime/lib/envelope.mjs';
import { readRun, readSession, resolveStore, updateRun, writeSession } from '../../plugins/hard-eng/runtime/lib/store.mjs';
import { supportEvents } from '../fixtures/support-fixture.mjs';
import { publicationEvidenceDigest } from '../../plugins/hard-eng/runtime/lib/ship.mjs';
import { digestValue } from '../../plugins/hard-eng/runtime/lib/canonical.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

function handleStateAction(args, options = {}) {
  return baseHandleStateAction(args, {
    ...options,
    supportObserver: (repo, receipt, { now }) => ({
      tool: receipt.tool,
      operation: receipt.operation,
      status: receipt.status,
      runtime_observed: true,
      ...(receipt.status === 'pass' ? { evidence_digest: receipt.evidence_digest ?? 'd'.repeat(64) } : {}),
      ...(receipt.reason_code ? { reason_code: receipt.reason_code } : {}),
      ...(receipt.fallback_reason ? { fallback_reason: receipt.fallback_reason } : {}),
      recorded_at: new Date(now).toISOString(),
    }),
  });
}

function authorize(repo, sessionId, args, toolUseId = 'tool-1', now = NOW) {
  const output = handleHook('pre-tool-use', {
    session_id: sessionId,
    turn_id: 'turn-1',
    tool_use_id: toolUseId,
    cwd: repo,
    hook_event_name: 'PreToolUse',
    tool_name: 'mcp__hard_eng__state',
    tool_input: args,
  }, { now });
  return output.hookSpecificOutput.updatedInput;
}

test('MCP exposes exactly one compact state tool', () => {
  assert.equal(toolDefinition.name, 'state');
  assert.deepEqual(toolDefinition.inputSchema.required, ['action']);
  assert.deepEqual(toolDefinition.inputSchema.properties.action.enum, ['start', 'status', 'resume', 'event']);
  assert.match(toolDefinition.inputSchema.properties._he.description, /do not set/i);
  assert.ok(JSON.stringify(toolDefinition).length < 1_600, 'state tool schema/description must stay compact');
});

test('start binds exact task, replay is idempotent, and unrelated tasks see only unbound', () => {
  const repo = makeRepo();
  const startArgs = {
    action: 'start',
    payload: {
      objective: 'Implement exact continuity',
      intent: { kind: 'plan', digest: 'a'.repeat(64) },
    },
  };
  const authorized = authorize(repo, 'session-a', startArgs);
  const first = handleStateAction(authorized, { now: NOW + 1 });
  const replay = handleStateAction(authorized, { now: NOW + 2 });
  assert.equal(first.status, 'bound');
  assert.deepEqual(replay, first);

  const store = resolveStore(repo, { create: false });
  assert.equal(fs.readdirSync(store.runsDir).filter((name) => name.endsWith('.json')).length, 1);
  assert.doesNotMatch(JSON.stringify(first), /session-a|\/private\/|\/Users\//);

  const unrelated = handleStateAction(authorize(repo, 'session-b', { action: 'status' }, 'tool-2'), { now: NOW + 3 });
  assert.deepEqual(unrelated, { status: 'unbound' });
  const sessionStart = handleHook('session-start', {
    session_id: 'session-b', cwd: repo, hook_event_name: 'SessionStart', source: 'resume',
  }, { now: NOW + 4 });
  assert.equal(sessionStart, null);
});

test('same Git-common family resumes explicitly across a native worktree', () => {
  const repo = makeRepo();
  const linked = makeLinkedWorktree(repo);
  const start = handleStateAction(authorize(repo, 'session-a', {
    action: 'start',
    payload: { objective: 'Handoff safely', intent: { kind: 'plan', digest: 'b'.repeat(64) } },
  }), { now: NOW + 1 });

  assert.throws(() => handleStateAction(authorize(linked, 'session-b', {
    action: 'resume', payload: { run_id: start.run_id, expected_revision: start.revision },
  }, 'tool-resume-denied'), { now: NOW + 2 }), /approved takeover/i);
  const resume = handleStateAction(authorize(linked, 'session-b', {
    action: 'resume',
    payload: {
      run_id: start.run_id,
      expected_revision: start.revision,
      takeover: { approved: true, approver: 'user', approved_revision: start.revision },
    },
  }, 'tool-resume'), { now: NOW + 3 });
  assert.equal(resume.run_id, start.run_id);
  assert.equal(resume.status, 'bound');
  assert.equal(resolveStore(repo, { create: false }).root, resolveStore(linked, { create: false }).root);
  const revoked = handleStateAction(authorize(repo, 'session-a', { action: 'status' }, 'old-task-status'), { now: NOW + 4 });
  assert.deepEqual(revoked, { status: 'unbound' });

  const store = resolveStore(repo, { create: false });
  const staleStatus = authorize(repo, 'session-a', { action: 'status' }, 'old-task-race');
  const oldHash = peekEnvelope(staleStatus._he).task_hash;
  const staleSession = readSession(store, oldHash);
  writeSession(store, { ...staleSession, revoked: false });
  assert.deepEqual(
    handleStateAction(authorize(repo, 'session-a', { action: 'status' }, 'old-task-reactivated'), { now: NOW + 5 }),
    { status: 'unbound' },
  );
  assert.equal(handleHook('session-start', {
    session_id: 'session-a', cwd: repo, hook_event_name: 'SessionStart', source: 'resume',
  }, { now: NOW + 6 }), null);
});

test('typed mutation replay advances revision once and returns the same result', () => {
  const repo = makeRepo();
  const start = handleStateAction(authorize(repo, 'session-replay', {
    action: 'start',
    payload: {
      objective: 'Replay exactly once',
      intent: {
        kind: 'direct',
        digest: 'f'.repeat(64),
        acceptance: ['focused test'],
        scope: ['state runtime'],
        non_goals: [],
        justification: 'Bounded state fixture',
      },
    },
  }), { now: NOW + 1 });
  let supported = start;
  for (const [index, event] of supportEvents().entries()) {
    const args = authorize(repo, 'session-replay', {
      action: 'event',
      payload: { run_id: start.run_id, expected_revision: supported.revision, event },
    }, `support-replay-${index}`);
    supported = handleStateAction(args, { now: NOW + index + 2 });
  }
  const eventArgs = authorize(repo, 'session-replay', {
    action: 'event',
    payload: {
      run_id: start.run_id,
      expected_revision: supported.revision,
      event: {
        type: 'build.red-proven',
        proof: {
          id: 'proof-red-replay',
          kind: 'red',
          name: 'red fixture',
          result: 'fail-expected',
          source: { kind: 'command', reference: 'fixture:red-replay' },
          evidence_digest: 'a'.repeat(64),
          candidate_fingerprint: 'b'.repeat(64),
        },
      },
    },
  }, 'event-replay');
  const first = handleStateAction(eventArgs, { now: NOW + 2 });
  const replay = handleStateAction(eventArgs, { now: NOW + 3 });
  assert.deepEqual(replay, first);
  assert.equal(first.revision, 4);
  assert.equal(readRun(resolveStore(repo, { create: false }), start.run_id).revision, 4);
});

test('completed runs are inert for status and SessionStart', () => {
  const repo = makeRepo();
  const start = handleStateAction(authorize(repo, 'session-complete', {
    action: 'start', payload: { objective: 'Become inert', intent: { kind: 'plan', digest: 'e'.repeat(64) } },
  }), { now: NOW + 1 });
  const store = resolveStore(repo, { create: false });
  const candidate = {
    base_commit: '1'.repeat(40),
    head: '2'.repeat(40),
    origin_main: '1'.repeat(40),
    branch: 'fixture',
    tree_fingerprint: '3'.repeat(64),
    tracked_diff_digest: '4'.repeat(64),
    untracked_manifest_digest: '5'.repeat(64),
    remote: { name: 'origin', url_digest: '8'.repeat(64) },
    fingerprint: '6'.repeat(64),
    check: {
      preflight_digest: 'c'.repeat(64),
      registry_digest: 'd'.repeat(64),
      results_digest: 'e'.repeat(64),
    },
    user_visible: false,
    evidence: {
      applicability: 'not-applicable',
      reason_digest: 'f'.repeat(64),
      evidence_digest: '0'.repeat(64),
    },
    approval: 'not-required',
  };
  updateRun(store, start.run_id, start.revision, (run) => {
    const preparationFacts = {
      mode: 'branch',
      remote_ref: 'refs/remotes/origin/fixture',
      remote_url_digest: candidate.remote.url_digest,
      remote_head_before: null,
      protections: {
        status: 'not-applicable', observer: 'github', evidence_digest: 'a'.repeat(64),
      },
    };
    const publicationObservation = {
      mode: 'branch',
      commit: '7'.repeat(40),
      parent: candidate.head,
      tree: '8'.repeat(40),
      tree_fingerprint: candidate.tree_fingerprint,
      candidate_fingerprint: candidate.fingerprint,
      external_action_digest: 'c'.repeat(64),
      remote_ref: 'refs/remotes/origin/fixture',
      remote_head: '7'.repeat(40),
      remote_url_digest: candidate.remote.url_digest,
      remote_observation_digest: '9'.repeat(64),
      preflight: { ...preparationFacts, evidence_digest: digestValue(preparationFacts) },
      current: true,
      ci: { status: 'pass', commit: '7'.repeat(40), observer: 'github', evidence_digest: '9'.repeat(64) },
      protections: { status: 'not-applicable', observer: 'github', evidence_digest: 'a'.repeat(64) },
      rollback: { strategy: 'revert-commit', target_commit: '7'.repeat(40), evidence_digest: 'b'.repeat(64) },
    };
    return {
      ...run,
      phase: 'Complete',
      cursor: { step: 'complete' },
      candidate,
      publication: {
        ...publicationObservation,
        approval: 'approved',
        evidence_digest: publicationEvidenceDigest(publicationObservation),
        approved_by: 'user',
        approved_at: '2026-07-12T00:01:00.000Z',
      },
      lease: { ...run.lease, reconciliation: 'released' },
      next: { owner: 'model', action: 'No action' },
      updated_at: '2026-07-12T00:01:00.000Z',
    };
  });
  assert.deepEqual(handleStateAction(authorize(repo, 'session-complete', { action: 'status' }, 'complete-status'), { now: NOW + 2 }), { status: 'unbound' });
  assert.equal(handleHook('session-start', {
    session_id: 'session-complete', cwd: repo, hook_event_name: 'SessionStart', source: 'resume',
  }, { now: NOW + 3 }), null);
  const completed = readRun(store, start.run_id);
  assert.throws(() => handleStateAction(authorize(repo, 'session-complete', {
    action: 'event',
    payload: {
      run_id: completed.run_id,
      expected_revision: completed.revision,
      event: {
        type: 'support.recorded',
        receipt: { tool: 'context-mode', operation: 'search', status: 'pass' },
      },
    },
  }, 'complete-mutation'), { now: NOW + 4 }), /Complete|transition|immutable/i);
});

test('invalid transition and unreconciled interruption fail closed', () => {
  const repo = makeRepo();
  const start = handleStateAction(authorize(repo, 'session-a', {
    action: 'start',
    payload: { objective: 'Fail closed', intent: { kind: 'plan', digest: 'c'.repeat(64) } },
  }), { now: NOW + 1 });

  const invalidArgs = authorize(repo, 'session-a', {
    action: 'event',
    payload: { run_id: start.run_id, expected_revision: start.revision, event: { type: 'build.implemented' } },
  }, 'tool-event');
  assert.throws(() => handleStateAction(invalidArgs, { now: NOW + 2 }), /transition|phase/i);

  const store = resolveStore(repo, { create: false });
  assert.equal(readSession(store, peekEnvelope(invalidArgs._he).task_hash).pending, null);
  const run = readRun(store, start.run_id);
  const runPath = `${store.runsDir}/${start.run_id}.json`;
  fs.writeFileSync(runPath, `${JSON.stringify({
    ...run,
    interruption: {
      intent: 'write external fixture',
      precondition_fingerprint: 'd'.repeat(64),
      idempotency_key: 'e'.repeat(64),
      observed_result: 'unknown',
      reconciliation_command: 'he doctor',
      prepared_at: '2026-07-12T00:00:03.000Z',
    },
  })}\n`, { mode: 0o600 });
  const compact = handleHook('pre-compact', {
    session_id: 'session-a', cwd: repo, hook_event_name: 'PreCompact', trigger: 'auto',
  }, { now: NOW + 3 });
  assert.equal(compact.continue, false);
  assert.match(compact.stopReason, /reconcil/i);
});

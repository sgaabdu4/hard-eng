import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { makePlan, withAcceptedDigest } from '../fixtures/plan-fixture.mjs';
import { handleHook } from '../../plugins/hard-eng/runtime/hook.mjs';
import { handleStateAction } from '../../plugins/hard-eng/runtime/server.mjs';
import { computePlanDigest } from '../../plugins/hard-eng/runtime/lib/plan.mjs';
import { readRun, resolveStore } from '../../plugins/hard-eng/runtime/lib/store.mjs';
import { supportEvents } from '../fixtures/support-fixture.mjs';

function authorize(repo, sessionId, args, toolUseId) {
  return handleHook('pre-tool-use', {
    session_id: sessionId,
    turn_id: `turn-${toolUseId}`,
    tool_use_id: toolUseId,
    cwd: repo,
    hook_event_name: 'PreToolUse',
    tool_name: 'mcp__hard_eng__state',
    tool_input: args,
  }).hookSpecificOutput.updatedInput;
}

test('Plan readiness and acceptance are proven from the one root plan.md, then digest drift blocks Build', () => {
  const repo = makeRepo();
  const session = 'plan-state-session';
  const started = handleStateAction(authorize(repo, session, {
    action: 'start', payload: { objective: 'Validate one plan owner', intent: { kind: 'plan', digest: '0'.repeat(64) } },
  }, 'start'));
  const pending = makePlan({ runId: started.run_id });
  fs.writeFileSync(path.join(repo, 'plan.md'), pending);

  let supported = started;
  for (const [index, event] of supportEvents().entries()) {
    supported = handleStateAction(authorize(repo, session, {
      action: 'event',
      payload: { run_id: started.run_id, expected_revision: supported.revision, event },
    }, `support-${index}`));
  }

  const ready = handleStateAction(authorize(repo, session, {
    action: 'event',
    payload: {
      run_id: started.run_id,
      expected_revision: supported.revision,
      event: { type: 'plan.ready-for-approval' },
    },
  }, 'ready'));
  assert.equal(ready.cursor.step, 'ready-for-approval');

  const digest = computePlanDigest(pending);
  fs.writeFileSync(path.join(repo, 'plan.md'), withAcceptedDigest(pending, digest));
  const accepted = handleStateAction(authorize(repo, session, {
    action: 'event',
    payload: {
      run_id: started.run_id,
      expected_revision: ready.revision,
      event: { type: 'plan.accepted', plan: { approver: 'user' } },
    },
  }, 'accept'));
  assert.equal(accepted.phase, 'Build');
  assert.equal(accepted.intent.digest, digest);
  const checkpoint = readRun(resolveStore(repo, { create: false }), started.run_id);
  assert.equal(Object.keys(checkpoint.plan.sections).length, 11);
  assert.deepEqual(checkpoint.plan.slice_ids, ['S1', 'S2']);
  assert.deepEqual(checkpoint.plan.acceptance_ids, ['P1', 'P2']);

  fs.appendFileSync(path.join(repo, 'plan.md'), '\nPost-approval drift.\n');
  assert.throws(() => handleStateAction(authorize(repo, session, {
    action: 'event',
    payload: {
      run_id: started.run_id,
      expected_revision: accepted.revision,
      event: { type: 'build.red-proven', proof: { name: 'red', result: 'fail-expected' } },
    },
  }, 'drifted-build')), /plan.*digest|reconciliation/i);
});

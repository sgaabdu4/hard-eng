import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { fingerprintCandidate } from '../../plugins/hard-eng/runtime/lib/candidate.mjs';
import { handleHook } from '../../plugins/hard-eng/runtime/hook.mjs';
import { handleStateAction } from '../../plugins/hard-eng/runtime/server.mjs';
import { readRun, resolveStore } from '../../plugins/hard-eng/runtime/lib/store.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';
import { supportEvents } from '../fixtures/support-fixture.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');
const digest = (character) => character.repeat(64);

function authorize(repo, args, toolUseId, now) {
  return handleHook('pre-tool-use', {
    session_id: 'session-build-freshness', turn_id: 'turn-build', tool_use_id: toolUseId,
    cwd: repo, hook_event_name: 'PreToolUse', tool_name: 'mcp__hard_eng__state', tool_input: args,
  }, { now }).hookSpecificOutput.updatedInput;
}

function proof(id, kind, result) {
  return {
    id, kind, name: `${kind} freshness fixture`, result,
    source: { kind: kind === 'review' ? 'review' : 'command', reference: `fixture:${id}` },
    evidence_digest: digest('e'),
    candidate_fingerprint: digest('0'),
  };
}

test('MCP binds Build proof to the real tree and requires explicit drift reconciliation', () => {
  const repo = makeRepo('hard-eng-build-freshness-');
  const start = handleStateAction(authorize(repo, {
    action: 'start',
    payload: {
      objective: 'Keep proof current with the real tree',
      intent: {
        kind: 'direct', digest: digest('a'), acceptance: ['fresh proof'], scope: ['README.md'],
        non_goals: [], justification: 'Bounded tree fixture',
      },
    },
  }, 'start', NOW), { now: NOW + 1 });
  const store = resolveStore(repo, { create: false });
  let serial = 2;
  const event = (body) => {
    const current = readRun(store, start.run_id);
    const args = {
      action: 'event',
      payload: { run_id: current.run_id, expected_revision: current.revision, event: body },
    };
    const now = NOW + serial++;
    return handleStateAction(authorize(repo, args, `event-${serial}`, now), { now: now + 1 });
  };

  for (const support of supportEvents()) event(support);
  event({ type: 'build.red-proven', proof: proof('proof-red-real', 'red', 'fail-expected') });
  const redFingerprint = readRun(store, start.run_id).proof.at(-1).candidate_fingerprint;
  assert.equal(redFingerprint, fingerprintCandidate(repo, { allowAllUntracked: true }).fingerprint);

  fs.appendFileSync(path.join(repo, 'README.md'), 'implementation\n');
  event({ type: 'build.implemented', candidate_fingerprint: digest('0') });
  event({ type: 'build.verify-passed', proof: proof('proof-verify-real', 'verify', 'pass') });
  const verifiedFingerprint = readRun(store, start.run_id).cursor.candidate_fingerprint;

  fs.appendFileSync(path.join(repo, 'README.md'), 'unrelated drift\n');
  assert.throws(() => event({
    type: 'build.review-passed', proof: proof('proof-review-stale', 'review', 'pass'),
  }), /candidate fingerprint|drift/i);
  assert.equal(readRun(store, start.run_id).cursor.candidate_fingerprint, verifiedFingerprint);

  event({ type: 'build.candidate-drift', reason: 'Tree changed after focused verification' });
  assert.equal(readRun(store, start.run_id).cursor.step, 'verify');
  event({ type: 'build.verify-passed', proof: proof('proof-verify-drift', 'verify', 'pass') });
  event({ type: 'build.review-passed', proof: proof('proof-review-current', 'review', 'pass') });
  const shipped = event({ type: 'build.all-slices-proven', candidate_fingerprint: digest('0') });
  assert.deepEqual([shipped.phase, shipped.cursor.step], ['Ship', 'preflight']);
});

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { buildCheckRegistry, runCheckRegistry } from '../../runtime/lib/check-registry.mjs';
import { signCheckReceipt } from '../../runtime/lib/check-receipt.mjs';
import { runShipPreflight } from '../../runtime/lib/ship-preflight.mjs';
import { handleHook } from '../../runtime/hook.mjs';
import { handleStateAction } from '../../runtime/server.mjs';
import { readKey, readRun, resolveStore, updateRun } from '../../runtime/lib/store.mjs';
import { git, makeRepo } from '../fixtures/repo-fixture.mjs';

const NOW = Date.parse('2026-07-12T00:00:00.000Z');

function authorize(repo, sessionId, args, toolUseId, now = NOW) {
  return handleHook('pre-tool-use', {
    session_id: sessionId,
    turn_id: 'turn-ship',
    tool_use_id: toolUseId,
    cwd: repo,
    hook_event_name: 'PreToolUse',
    tool_name: 'mcp__hard_eng__state',
    tool_input: args,
  }, { now }).hookSpecificOutput.updatedInput;
}

test('MCP Ship accepts only a signed current receipt from the exact local registry candidate', () => {
  const repo = makeRepo('hard-eng-ship-server-');
  const remote = fs.mkdtempSync(path.join(os.tmpdir(), 'hard-eng-ship-remote-'));
  git(remote, 'init', '--bare', '-q');
  git(repo, 'remote', 'add', 'origin', remote);
  fs.writeFileSync(path.join(repo, 'pass.mjs'), "process.stdout.write('pass\\n');\n");
  fs.writeFileSync(path.join(repo, 'package.json'), `${JSON.stringify({ private: true, scripts: { test: 'node pass.mjs' } })}\n`);
  const allowedUntracked = ['package.json', 'pass.mjs'];
  const start = handleStateAction(authorize(repo, 'session-ship', {
    action: 'start',
    payload: {
      objective: 'Gate Ship with real local checks',
      intent: {
        kind: 'direct', digest: 'a'.repeat(64), acceptance: ['checks pass'], scope: ['fixture'],
        non_goals: [], justification: 'Bounded server fixture',
      },
    },
  }, 'start-ship'), { now: NOW + 1 });
  const store = resolveStore(repo, { create: false });
  const ship = updateRun(store, start.run_id, start.revision, (run) => ({
    ...run,
    phase: 'Ship',
    cursor: { step: 'preflight' },
    support_tools: [
      { tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: 'c'.repeat(64), runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
      { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
    ],
    next: { owner: 'model', action: 'Run deterministic Ship preflight and candidate proof' },
  }));
  const preflight = runShipPreflight(repo, ship, { allowedUntracked });
  const report = runCheckRegistry(repo, buildCheckRegistry(repo), { allowedUntracked });
  const receipt = signCheckReceipt(readKey(store), { run: ship, report, preflight }, { now: NOW + 2 });
  const event = (checkReceipt) => ({
    action: 'event',
    payload: {
      run_id: ship.run_id,
      expected_revision: ship.revision,
      event: {
        type: 'ship.candidate-green',
        check_receipt: checkReceipt,
        evidence: { applicability: 'not-applicable', reason: 'No user-visible interface changed' },
      },
    },
  });

  assert.throws(() => handleStateAction(authorize(repo, 'session-ship', event({
    ...receipt, signature: 'f'.repeat(64),
  }), 'forged-receipt'), { now: NOW + 3 }), /signature/i);
  assert.equal(readRun(store, ship.run_id).revision, ship.revision);

  fs.appendFileSync(path.join(repo, 'README.md'), 'candidate drift\n');
  assert.throws(() => handleStateAction(authorize(repo, 'session-ship', event(receipt), 'stale-receipt'), {
    now: NOW + 4,
  }), /candidate.*changed|stale/i);

  const freshReport = runCheckRegistry(repo, buildCheckRegistry(repo), { allowedUntracked });
  const freshPreflight = runShipPreflight(repo, ship, { allowedUntracked });
  const freshReceipt = signCheckReceipt(readKey(store), {
    run: ship, report: freshReport, preflight: freshPreflight,
  }, { now: NOW + 5 });
  const accepted = handleStateAction(authorize(repo, 'session-ship', event(freshReceipt), 'fresh-receipt'), {
    now: NOW + 6,
  });
  assert.equal(accepted.cursor.step, 'publish');
  const acceptedRun = readRun(store, ship.run_id);
  assert.equal(acceptedRun.candidate.fingerprint, freshReport.candidate.fingerprint);
  assert.doesNotMatch(JSON.stringify(acceptedRun), /signature|check_receipt/);

  git(repo, 'add', '-A');
  git(repo, 'commit', '-qm', 'Publish — invalid metadata');
  const preparePublication = (commit, idempotencyKey = '4'.repeat(64)) => ({
    action: 'event',
    payload: {
      run_id: acceptedRun.run_id,
      expected_revision: acceptedRun.revision,
      event: {
        type: 'external-action.prepared',
        action: {
          intent: 'publish', precondition_fingerprint: acceptedRun.candidate.fingerprint,
          idempotency_key: idempotencyKey, reconciliation_command: 'git fetch origin',
          publication: { mode: 'branch', remote_ref: 'refs/remotes/origin/fixture', commit },
        },
      },
    },
  });
  assert.throws(() => handleStateAction(authorize(
    repo,
    'session-ship',
    preparePublication(git(repo, 'rev-parse', 'HEAD'), '6'.repeat(64)),
    'reject-commit-message',
  ), { now: NOW + 7 }), /commit message/i);

  git(repo, 'commit', '--amend', '-qm', 'Publish exact candidate');
  const publishedCommit = git(repo, 'rev-parse', 'HEAD');
  const publishedTree = git(repo, 'rev-parse', 'HEAD^{tree}');
  const prepared = handleStateAction(authorize(
    repo,
    'session-ship',
    preparePublication(publishedCommit),
    'prepare-publication',
  ), { now: NOW + 7 });
  assert.equal(prepared.interruption.reconciliation_command, 'git fetch origin');
  assert.equal(prepared.interruption.publication_preflight.mode, 'branch');
  assert.equal(prepared.interruption.publication_preflight.commit, publishedCommit);
  assert.match(prepared.interruption.publication_preflight.commit_message_digest, /^[a-f0-9]{64}$/);
  assert.equal(prepared.interruption.publication_preflight.protections.status, 'not-applicable');
  assert.match(prepared.capsule, /interruption: pending/i);

  git(repo, 'push', '-q', 'origin', 'HEAD:refs/heads/fixture');
  const publication = {
    mode: 'branch', commit: publishedCommit, parent: acceptedRun.candidate.head,
    tree: publishedTree, tree_fingerprint: acceptedRun.candidate.tree_fingerprint,
    candidate_fingerprint: acceptedRun.candidate.fingerprint,
    remote_ref: 'refs/remotes/origin/fixture', remote_head: publishedCommit, current: true,
    ci: { status: 'pass', commit: publishedCommit, evidence_digest: '1'.repeat(64) },
    protections: { status: 'not-applicable', evidence_digest: '2'.repeat(64) },
    rollback: { strategy: 'revert-commit', target_commit: publishedCommit, evidence_digest: '3'.repeat(64) },
  };
  const publicationEvent = (value) => ({
    action: 'event',
    payload: {
      run_id: prepared.run_id,
      expected_revision: prepared.revision,
      event: {
        type: 'ship.published-current', publication: value,
        external_action: {
          idempotency_key: '4'.repeat(64), observed_result: 'remote ref contains the exact commit',
          evidence_digest: '5'.repeat(64),
        },
      },
    },
  });
  assert.throws(() => handleStateAction(authorize(repo, 'session-ship', publicationEvent({
    ...publication, tree: 'f'.repeat(40),
  }), 'forged-publication'), { now: NOW + 8 }), /tree|Git/i);
  const observed = handleStateAction(authorize(
    repo, 'session-ship', publicationEvent(publication), 'current-publication', NOW + 9,
  ), { now: NOW + 10 });
  assert.deepEqual([observed.phase, observed.cursor.step], ['Ship', 'await-publication-approval']);
  const observedRun = readRun(store, ship.run_id);
  const approvalEvent = {
    action: 'event',
    payload: {
      run_id: observedRun.run_id,
      expected_revision: observedRun.revision,
      event: {
        type: 'ship.publication-approved', approver: 'user', commit: publishedCommit,
        evidence_digest: observedRun.publication.evidence_digest,
      },
    },
  };
  git(remote, 'update-ref', 'refs/heads/fixture', acceptedRun.candidate.head);
  assert.throws(() => handleStateAction(authorize(
    repo, 'session-ship', approvalEvent, 'stale-publication-approval', NOW + 11,
  ), { now: NOW + 12 }), /origin|current|observation/i);
  git(remote, 'update-ref', 'refs/heads/fixture', publishedCommit);
  const completed = handleStateAction(authorize(
    repo, 'session-ship', approvalEvent, 'current-publication-approval', NOW + 13,
  ), { now: NOW + 14 });
  assert.equal(completed.phase, 'Complete');
});

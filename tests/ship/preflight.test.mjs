import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { runShipPreflight } from '../../plugins/hard-eng/runtime/lib/ship-preflight.mjs';
import { createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';
import { makeRepo, git } from '../fixtures/repo-fixture.mjs';

const digest = (character) => character.repeat(64);

function run(overrides = {}) {
  const value = createInitialRun({
    repoId: digest('1'), checkoutId: digest('2'), taskHash: digest('3'),
    objective: 'Preflight an exact candidate', runId: 'he-preflight',
    intent: {
      kind: 'direct', digest: digest('4'), acceptance: ['safe candidate'], scope: ['fixture'],
      non_goals: [], justification: 'Bounded preflight fixture',
    },
    now: '2026-07-12T00:00:00.000Z',
  });
  value.phase = 'Ship';
  value.cursor = { step: 'preflight' };
  value.support_tools = [
    { tool: 'codebase-memory', operation: 'detect_changes', status: 'pass', evidence_digest: digest('5'), runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
    { tool: 'context-mode', operation: 'not-applicable', status: 'not-applicable', reason_code: 'no-large-output', runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z' },
  ];
  return Object.assign(value, overrides);
}

test('Ship preflight proves intent, Git safety, and mandatory support-tool disposition without raw output', () => {
  const repo = makeRepo('hard-eng-preflight-pass-');
  fs.appendFileSync(path.join(repo, 'README.md'), 'safe change\n');
  const result = runShipPreflight(repo, run(), { allowedUntracked: [] });
  assert.equal(result.status, 'PASS');
  assert.match(result.digest, /^[a-f0-9]{64}$/);
  assert.equal(result.changed_path_count, 1);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(repo.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));

  const missing = run();
  missing.support_tools = [];
  assert.equal(runShipPreflight(repo, missing).status, 'FAIL');

  const skipped = run();
  skipped.support_tools[0] = {
    tool: 'codebase-memory', operation: 'not-applicable', status: 'not-applicable', runtime_observed: true, recorded_at: '2026-07-12T00:00:00.000Z',
  };
  assert.equal(runShipPreflight(repo, skipped).status, 'FAIL');

  const discoveryOnly = run();
  discoveryOnly.support_tools[0] = {
    tool: 'codebase-memory', operation: 'get_architecture', status: 'pass', evidence_digest: digest('5'), runtime_observed: true,
    recorded_at: '2026-07-12T00:00:00.000Z',
  };
  assert.equal(runShipPreflight(repo, discoveryOnly).status, 'FAIL');
});

test('Ship preflight rejects environment files, secret-like candidate content, generated owners, and Direct deletion', () => {
  let repo = makeRepo('hard-eng-preflight-env-');
  fs.writeFileSync(path.join(repo, '.env.local'), 'SAFE_NAME=value\n');
  let result = runShipPreflight(repo, run(), { allowedUntracked: ['.env.local'] });
  assert.equal(result.status, 'FAIL');
  assert.match(result.findings.map((finding) => finding.code).join(' '), /sensitive-path/);

  repo = makeRepo('hard-eng-preflight-secret-');
  const secret = `ghp_${'A'.repeat(32)}`;
  fs.appendFileSync(path.join(repo, 'README.md'), `${secret}\n`);
  result = runShipPreflight(repo, run());
  assert.equal(result.status, 'FAIL');
  assert.match(result.findings.map((finding) => finding.code).join(' '), /secret-content/);
  assert.doesNotMatch(JSON.stringify(result), new RegExp(secret));

  repo = makeRepo('hard-eng-preflight-generated-');
  fs.mkdirSync(path.join(repo, 'generated'));
  fs.writeFileSync(path.join(repo, 'generated', 'client.js'), 'changed\n');
  git(repo, 'add', 'generated/client.js');
  result = runShipPreflight(repo, run());
  assert.equal(result.status, 'FAIL');
  assert.match(result.findings.map((finding) => finding.code).join(' '), /generated-owner/);

  repo = makeRepo('hard-eng-preflight-delete-');
  fs.unlinkSync(path.join(repo, 'README.md'));
  result = runShipPreflight(repo, run());
  assert.equal(result.status, 'FAIL');
  assert.match(result.findings.map((finding) => finding.code).join(' '), /direct-deletion/);
});

import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { git, makeRepo } from '../fixtures/repo-fixture.mjs';
import { renderCapsule } from '../../plugins/hard-eng/runtime/lib/capsule.mjs';
import { fingerprintCandidate, fingerprintCommitTree } from '../../plugins/hard-eng/runtime/lib/candidate.mjs';
import { createInitialRun } from '../../plugins/hard-eng/runtime/lib/state-machine.mjs';

test('capsule is bounded and contains only current execution facts', () => {
  const run = createInitialRun({
    repoId: '1'.repeat(64),
    checkoutId: '2'.repeat(64),
    taskHash: '3'.repeat(64),
    objective: 'A private objective that must not be rendered',
    intent: { kind: 'direct', digest: '4'.repeat(64), acceptance: ['test'], scope: ['lib'], non_goals: [], justification: 'bounded' },
    now: '2026-07-12T00:00:00.000Z',
    runId: 'run-capsule',
  });
  const capsule = renderCapsule(run);
  assert.ok(capsule.length <= 480, `capsule too large: ${capsule.length} chars`);
  assert.match(capsule, /run-capsule/);
  assert.match(capsule, /Build:red/);
  assert.match(capsule, /revision: 1/);
  assert.doesNotMatch(capsule, /private objective|taskHash|checkout|\/Users\//i);
});

test('candidate fingerprint changes for tracked and allowed untracked content without leaking paths or remotes', () => {
  const repo = makeRepo();
  git(repo, 'remote', 'add', 'origin', 'https://example.invalid/private/repo.git');
  const clean = fingerprintCandidate(repo, { allowedUntracked: [] });

  fs.appendFileSync(path.join(repo, 'README.md'), 'changed\n');
  const tracked = fingerprintCandidate(repo, { allowedUntracked: [] });
  assert.notEqual(tracked.fingerprint, clean.fingerprint);

  fs.writeFileSync(path.join(repo, 'proof.txt'), 'proof\n');
  const untracked = fingerprintCandidate(repo, { allowedUntracked: ['proof.txt'] });
  assert.notEqual(untracked.fingerprint, tracked.fingerprint);
  assert.notEqual(untracked.untracked_manifest_digest, tracked.untracked_manifest_digest);
  assert.doesNotMatch(JSON.stringify(untracked), /example\.invalid|\/private\/|\/Users\//);
});

test('candidate tree fingerprint is content-stable across the publication commit', () => {
  const repo = makeRepo('hard-eng-candidate-tree-');
  fs.appendFileSync(path.join(repo, 'README.md'), 'candidate change\n');
  fs.writeFileSync(path.join(repo, 'proof.txt'), 'bounded proof\n');
  const candidate = fingerprintCandidate(repo, { allowedUntracked: ['proof.txt'] });
  git(repo, 'add', '-A');
  git(repo, 'commit', '-qm', 'publish fixture');
  assert.equal(fingerprintCommitTree(repo, 'HEAD'), candidate.tree_fingerprint);
});

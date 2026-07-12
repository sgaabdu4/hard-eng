import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { sha256 } from '../../runtime/lib/canonical.mjs';
import { validateVisualEvidence } from '../../runtime/lib/evidence.mjs';
import { makeRepo } from '../fixtures/repo-fixture.mjs';

const digest = (character) => character.repeat(64);

test('real visual evidence verifies run-owned image/video bytes and digests', () => {
  const repo = makeRepo('hard-eng-visual-artifacts-');
  const runId = 'he-real-visual';
  const directory = path.join(repo, '.hard-eng', 'evidence', runId);
  fs.mkdirSync(directory, { recursive: true });
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Wl2nfsAAAAASUVORK5CYII=', 'base64');
  const mp4 = Buffer.concat([Buffer.alloc(4), Buffer.from('ftyp'), Buffer.from('isom-fixture')]);
  fs.writeFileSync(path.join(directory, 'after.png'), png);
  fs.writeFileSync(path.join(directory, 'flow.mp4'), mp4);
  const pack = {
    kind: 'final', applicability: 'applicable', candidate_fingerprint: digest('1'),
    approved_direction_digest: digest('2'),
    scenario: {
      role: 'member', data_fixture: 'seed-v1', route: '/fixture',
      viewport_or_device: '1440x900', environment: 'local fixture',
    },
    baseline: { status: 'not-applicable', reason: 'Greenfield fixture' },
    implementation: { artifacts: [
      { kind: 'screenshot', path: `.hard-eng/evidence/${runId}/after.png`, digest: sha256(png) },
      { kind: 'video', path: `.hard-eng/evidence/${runId}/flow.mp4`, digest: sha256(mp4) },
    ] },
    requires_video: true,
    known_gaps: [],
  };
  assert.equal(validateVisualEvidence(pack, { repo, runId, final: true }).video_present, true);
  fs.writeFileSync(path.join(directory, 'flow.mp4'), Buffer.from('not-a-video'));
  assert.throws(() => validateVisualEvidence(pack, { repo, runId, final: true }), /digest|video/i);
});

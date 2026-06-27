#!/usr/bin/env node
import assert from 'node:assert/strict';
import {
  buildEvidenceSection,
  extractHostedVideoMarkdown,
  extractLocalImagePaths,
  extractLocalVideoPaths,
  extractHostedImageMarkdown,
  hasLocalRefs,
  insertEvidenceSection,
  parseArgs,
  parseNoMistakesFixCommits,
  parseNoMistakesStatus,
  reviewThreadRowsFromGraphql,
  sanitizeBody,
  screenshotStatusRows,
  selectVideoUploadPaths,
  videoStatusRows,
} from '../../../integrations/no-mistakes/scripts/repair-pr-evidence.mjs';

assert.equal(parseArgs(['--dry-run']).checkReviewThreads, false);
assert.equal(parseArgs(['--check-review-threads']).checkReviewThreads, true);
assert.equal(parseArgs(['--e2e-video-required']).e2eVideoRequired, true);
assert.deepEqual(parseArgs(['--videos', 'https://github.com/user-attachments/assets/video']).videos, [
  'https://github.com/user-attachments/assets/video',
]);

const body = `## Intent

Uploading Screen Recording 2026-06-22 at 21.37.28.mov...

## Screenshots

![old](https://github.com/user-attachments/assets/old)

## Testing

- Evidence: Desktop (local file: <code>/var/folders/x/no-mistakes-evidence/run/screenshots/desktop.png</code>)
- Video: 2x recap (local file: <code>/tmp/no-mistakes-evidence/run/recaps/login_2x_cursor.mp4</code>)

<details>
<summary>Evidence ledger</summary>

\`\`\`text
{"path":"/Users/example/tmp/no-mistakes-evidence/screenshots/mobile.png","url":"http://127.0.0.1:3000/problems"}
\`\`\`
</details>

## Verification

- npm run build passed locally.
`;

const paths = extractLocalImagePaths(body);
assert.deepEqual(paths, [
  '/var/folders/x/no-mistakes-evidence/run/screenshots/desktop.png',
  '/Users/example/tmp/no-mistakes-evidence/screenshots/mobile.png',
]);
assert.deepEqual(extractLocalVideoPaths(body), [
  '/tmp/no-mistakes-evidence/run/recaps/login_2x_cursor.mp4',
]);
assert.deepEqual(extractHostedImageMarkdown(body), [
  '![old](https://github.com/user-attachments/assets/old)',
]);
assert.deepEqual(extractHostedVideoMarkdown('2x video: [2x recap](https://github.com/user-attachments/assets/vid)'), [
  '[2x recap](https://github.com/user-attachments/assets/vid)',
]);
assert.deepEqual(
  selectVideoUploadPaths([
    '/tmp/no-mistakes-evidence/run/videos/sales-analytics-flow-final.webm',
    '/tmp/no-mistakes-evidence/run/videos/sales-analytics-flow-2x-final.mp4',
  ], true),
  ['/tmp/no-mistakes-evidence/run/videos/sales-analytics-flow-2x-final.mp4'],
);
assert.deepEqual(
  selectVideoUploadPaths(['/tmp/no-mistakes-evidence/run/videos/login_2x_cursor.mp4'], true),
  ['/tmp/no-mistakes-evidence/run/videos/login_2x_cursor.mp4'],
);
assert.deepEqual(
  selectVideoUploadPaths(['/tmp/no-mistakes-evidence/run/videos/raw.webm'], true),
  [],
);
assert.deepEqual(
  selectVideoUploadPaths(['/tmp/no-mistakes-evidence/run/videos/raw.webm'], false),
  ['/tmp/no-mistakes-evidence/run/videos/raw.webm'],
);

const sanitized = sanitizeBody(body);
assert.ok(!hasLocalRefs(sanitized), 'sanitized body must not keep local-only evidence');
assert.ok(!sanitized.includes('Uploading Screen Recording'), 'upload placeholders must be removed');
assert.ok(!sanitized.includes('github.com/user-attachments/assets/old'), 'stale screenshot section must be replaced');

const statusRows = [
  ...screenshotStatusRows({
    screenshots: ['![Desktop board](https://github.com/user-attachments/assets/abc)'],
    uploadError: '',
  }),
  ...videoStatusRows({
    videos: ['[2x E2E video](https://github.com/user-attachments/assets/vid)'],
    localVideos: [],
    required: true,
  }),
  ...parseNoMistakesStatus('run:\n  findings: none\n'),
  ...reviewThreadRowsFromGraphql({
    data: {
      repository: {
        pullRequest: {
          reviewThreads: {
            nodes: [
              {
                isResolved: false,
                path: 'views/problems.ejs',
                line: 114,
                comments: {
                  nodes: [{
                    url: 'https://github.com/a-s-abbas/lmtb/pull/3#discussion_r1',
                    body: 'External player links should use noopener noreferrer.',
                    author: { login: 'copilot-pull-request-reviewer' },
                  }],
                },
              },
            ],
          },
        },
      },
    },
  }),
  ...parseNoMistakesFixCommits(
    'a449a540000000000000000000000000000000000\tno-mistakes(review): Allow Problems board past contribution gate\n',
    'a-s-abbas/lmtb',
  ),
];
const section = buildEvidenceSection({
  screenshots: ['![Desktop board](https://github.com/user-attachments/assets/abc)'],
  videos: ['[2x E2E video](https://github.com/user-attachments/assets/vid)'],
  statusRows,
  uploadError: '',
  e2eVideoRequired: true,
  currentHeadSha: 'a449a540000000000000000000000000000000000',
});
const repaired = insertEvidenceSection(sanitized, section);

assert.ok(repaired.includes('## No-mistakes Evidence'));
assert.ok(repaired.includes('Current head: `a449a540000000000000000000000000000000000`'));
assert.ok(repaired.includes('![Desktop board](https://github.com/user-attachments/assets/abc)'));
assert.ok(repaired.includes('[2x E2E video](https://github.com/user-attachments/assets/vid)'));
assert.ok(repaired.includes('PR screenshots attached'));
assert.ok(repaired.includes('2x E2E video attached'));
assert.ok(repaired.includes('No open no-mistakes findings'));
assert.ok(repaired.includes('copilot-pull-request-reviewer: External player links should use noopener noreferrer.'));
assert.ok(repaired.includes('[views/problems.ejs:114](https://github.com/a-s-abbas/lmtb/pull/3#discussion_r1)'));
assert.ok(repaired.includes('Allow Problems board past contribution gate'));
assert.ok(repaired.includes('[a449a54](https://github.com/a-s-abbas/lmtb/commit/a449a540000000000000000000000000000000000)'));
assert.ok(!hasLocalRefs(repaired), 'repaired body must not contain local refs');
assert.match(repaired.trimEnd(), /<!-- nm-pr-evidence:end -->$/, 'managed evidence must be appended after existing PR content');

assert.deepEqual(
  reviewThreadRowsFromGraphql({
    data: {
      repository: {
        pullRequest: {
          reviewThreads: {
            nodes: [{ isResolved: true }],
          },
        },
      },
    },
  }),
  [{ status: 'Resolved', issue: 'No open GitHub review threads', evidence: '1 thread(s) checked' }],
);

assert.deepEqual(
  screenshotStatusRows({ screenshots: [], uploadError: 'upload denied' }),
  [{ status: 'Open', issue: 'Screenshot upload failed', evidence: 'upload denied' }],
);

assert.deepEqual(
  screenshotStatusRows({ screenshots: [], uploadError: '' }),
  [{
    status: 'Open',
    issue: 'No PR screenshots attached',
    evidence: 'No screenshot artifacts or hosted screenshot links found',
  }],
);

assert.deepEqual(
  videoStatusRows({ videos: [], localVideos: ['/tmp/recap.mp4'], required: true }),
  [{
    status: 'Open',
    issue: '2x E2E video not hosted',
    evidence: '1 local video artifact(s) found; attach a reviewer-openable 2x video link',
  }],
);

assert.deepEqual(
  videoStatusRows({ videos: [], localVideos: ['/tmp/recap.mp4'], required: true, uploadError: 'upload denied' }),
  [{
    status: 'Open',
    issue: '2x E2E video upload failed',
    evidence: 'upload denied',
  }],
);

assert.deepEqual(
  videoStatusRows({ videos: [], localVideos: [], required: true }),
  [{
    status: 'Open',
    issue: 'No 2x E2E video attached',
    evidence: 'UI or phone E2E requires a reviewer-openable 2x video link in PR evidence',
  }],
);

console.log('no-mistakes pr evidence: pass');

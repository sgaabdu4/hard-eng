#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const root = path.join(process.env.HOME, '.agents');
function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) walk(fullPath, out);
    if (entry.isFile()) out.push(fullPath);
  }
  return out;
}

const files = walk(path.join(root, 'skills', 'no-mistakes'))
  .map((file) => fs.readFileSync(file, 'utf8'));
const text = files.join('\n');

const requiredCoverage = [
  'Read `references/axi-workflow.md` before starting',
  'Read `references/pr-evidence.md` before finalizing',
  'Validate-only',
  'Task-first',
  'committed on a feature branch',
  'Never run the pipeline from the default branch',
  'ensure-worktree-ready.sh',
  'push dry-run',
  'explicit refspec',
  'no-mistakes init',
  'no-mistakes doctor',
  'active run',
  'another branch',
  'Pass `--intent` every time',
  'The intent is the user',
  'gate:',
  'auto-fix',
  'no-op',
  'ask-user',
  'no-mistakes axi respond --action fix',
  'no-mistakes axi respond --action approve',
  'no-mistakes axi respond --action skip',
  'Do not manually edit code while the active gate is waiting',
  '--add-finding',
  '--step <name>',
  '--yes',
  'checks-passed',
  'failed` or `cancelled',
  'do not wait for human merge',
  'no-mistakes axi status',
  'no-mistakes axi logs --step <name> --full',
  'no-mistakes axi abort',
  'no-mistakes rerun',
  'Output is TOON',
  'Follow `help` lines',
  'Exit codes',
  'Pipeline findings and fixes',
  'Directory not empty',
  'hosted screenshots',
  'required 2x E2E video links',
  '--e2e-video-required',
  '--videos /path/to/final-2x-video.mp4',
  '--videos "https://github.com/user-attachments/assets/..."',
  'no local paths',
  'append the managed evidence section',
  '--pr 3 --screenshots /path/to/screenshots',
  'gh-image',
  'gh image',
  'GitHub `user-attachments`',
  'Never commit screenshot files for PR evidence',
  'PR screenshots attached',
  'No PR screenshots attached',
  '2x E2E video attached',
  '2x E2E video upload failed',
  'No 2x E2E video attached',
  'Screenshot upload failed',
  'clear screenshot/video and no-mistakes',
  'Only check GitHub review threads after external PR review has run',
  'Only pass `--check-review-threads`',
  '--check-review-threads',
  'GitHub review threads',
  'unresolved GitHub review thread',
  'github.com/user-attachments',
  'findings: none',
];

for (const snippet of requiredCoverage) {
  assert.ok(text.includes(snippet), `missing no-mistakes coverage: ${snippet}`);
}

const personalHomePath = process.env.HOME;
assert.ok(!text.includes(personalHomePath), 'no-mistakes skill files must not contain personal absolute paths');

console.log('no-mistakes migration coverage: pass');

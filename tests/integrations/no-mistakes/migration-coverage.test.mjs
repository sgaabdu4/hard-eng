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

const skillPath = path.join(root, 'skills', 'no-mistakes');
const skillStat = fs.lstatSync(skillPath);
assert.ok(skillStat.isSymbolicLink(), 'Hard Eng must expose no-mistakes through the pinned upstream skill symlink');
assert.equal(
  fs.readlinkSync(skillPath),
  '../vendor/skill-upstreams/no-mistakes/skills/no-mistakes',
  'no-mistakes skill must stay pinned to the vendored upstream submodule',
);
assert.ok(
  fs.existsSync(path.join(root, 'vendor', 'skill-upstreams', 'no-mistakes', 'skills', 'no-mistakes', 'SKILL.md')),
  'vendored upstream no-mistakes skill must exist',
);

const files = walk(path.join(root, 'integrations', 'no-mistakes'))
  .map((file) => fs.readFileSync(file, 'utf8'));
const text = files.join('\n');
const normalizedText = text.replace(/\s+/g, ' ');

const requiredCoverage = [
  'Validate-only',
  'Task-first',
  'commit only that scope on a feature branch',
  'validate the committed branch',
  'Never run the pipeline from the default branch',
  'ensure-worktree-ready.sh',
  'push dry-run',
  'explicit refspec',
  'no-mistakes init',
  'no-mistakes-gate-hook',
  'notify-push',
  'GATE_DIR',
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
  'Screenshots are GitHub `user-attachments` URLs',
  'reviewer-openable 2x video link',
  '--e2e-video-required',
  '--videos /path/to/final-2x-video.mp4',
  '--videos "https://github.com/user-attachments/assets/..."',
  'Never leave local screenshot paths in the PR body',
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
  'Screenshot and required video evidence are tracked',
  'no-mistakes findings are shown as resolved or open',
  'run `--check-review-threads` before final loop-complete',
  'do not call the repo done after known review comments exist',
  '--check-review-threads',
  'GitHub review threads',
  'unresolved GitHub review thread',
  'github.com/user-attachments',
  'findings: none',
];

for (const snippet of requiredCoverage) {
  assert.ok(text.includes(snippet) || normalizedText.includes(snippet), `missing no-mistakes coverage: ${snippet}`);
}

const personalHomePath = process.env.HOME;
assert.ok(!text.includes(personalHomePath), 'no-mistakes integration files must not contain personal absolute paths');

console.log('no-mistakes migration coverage: pass');

#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

const repo = path.resolve(new URL('..', import.meta.url).pathname);

const files = fs.readdirSync(path.join(repo, 'agents'))
  .filter((name) => name.endsWith('.md'))
  .map((name) => path.join('agents', name))
  .sort();

assert.ok(files.length > 0, 'agent prompt contracts must have at least one prompt file');

for (const file of files) {
  const text = fs.readFileSync(path.join(repo, file), 'utf8');

  assert.match(text, /^  - status: done, blocked, failed, or stalled$/m, `${file} must report lifecycle status`);
  assert.match(text, /^  - progress bullets /m, `${file} must report resumable progress`);
  assert.match(text, /^  - lastProgressAt when status is blocked, failed, or stalled$/m, `${file} must report last progress time`);
  assert.match(text, /recovery prompt/i, `${file} must report recovery prompt`);
  assert.match(text, /^  - .*reason.*(?:blocked.*stalled|stalled.*blocked).*$/im, `${file} must request blocked or stalled reason`);
}

console.log('agent-work-prompt-contract-test: pass');

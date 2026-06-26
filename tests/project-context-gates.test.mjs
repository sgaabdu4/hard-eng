#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const repo = path.resolve(new URL('..', import.meta.url).pathname);
const script = path.join(repo, 'scripts', 'check-project-context-gates.mjs');
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'project-context-gates-'));

function write(file, text) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, text);
}

function run(root, args = []) {
  return spawnSync('node', [script, '--require-all', ...args, root], { encoding: 'utf8' });
}

let result = run(tmp);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /PRODUCT\.md is required/);
assert.match(result.stderr, /DESIGN\.md is required/);

const missingOwner = path.join(tmp, 'missing-owner');
write(path.join(missingOwner, 'PRODUCT.md'), '# Product\n\nA real product brief with audience, behavior, and scope.\n');
write(path.join(missingOwner, 'DESIGN.md'), '# Design\n\n## Overview\nReal design context.\n');
result = run(missingOwner);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /Token owner/);

const good = path.join(tmp, 'good');
write(path.join(good, 'PRODUCT.md'), '# Product\n\nA real product brief with audience, behavior, and scope.\n');
write(path.join(good, 'DESIGN.md'), [
  '# Design',
  '',
  '## Overview',
  'A real design brief.',
  '',
  '## Tokens',
  'Token owner: `src/design/tokens.css`',
  '',
  '## Components',
  'Design system: `src/components/ui`',
  '',
  '## States',
  'Ready, blocked, and failure states are visible.',
  '',
].join('\n'));
write(path.join(good, 'src/design/tokens.css'), ':root { --color-bg: white; }\n');
write(path.join(good, 'src/components/ui/.gitkeep'), '');
result = run(good);
assert.equal(result.status, 0, result.stderr);
assert.match(result.stdout, /project-context-gates: pass/);

spawnSync('git', ['init'], { cwd: good, encoding: 'utf8' });
spawnSync('git', ['add', '.'], { cwd: good, encoding: 'utf8' });
spawnSync('git', [
  '-c', 'user.name=Test',
  '-c', 'user.email=test@example.com',
  '-c', 'commit.gpgsign=false',
  'commit',
  '-m',
  'init',
], { cwd: good, encoding: 'utf8' });
result = run(good, ['--require-design-update']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /design\/UI\/token change requires DESIGN\.md update/);
fs.appendFileSync(path.join(good, 'DESIGN.md'), '\nDesign note.\n');
result = run(good, ['--require-design-update']);
assert.equal(result.status, 0, result.stderr);
result = run(good, ['--require-product-update']);
assert.notEqual(result.status, 0);
assert.match(result.stderr, /product change requires PRODUCT\.md update/);
fs.appendFileSync(path.join(good, 'PRODUCT.md'), '\nProduct note.\n');
result = run(good, ['--require-product-update']);
assert.equal(result.status, 0, result.stderr);

console.log('project-context-gates-test: pass');
